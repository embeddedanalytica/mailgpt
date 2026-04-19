"""Sectioned candidate-operation memory reducer."""

from __future__ import annotations

import copy
import difflib
import logging
import re
import uuid
from typing import Any, Dict, List, Optional, Set, Tuple

from sectioned_memory_contract import ContinuitySummary
from sectioned_memory_contract import (
    ACTIVE_CAP_BY_BUCKET,
    BUCKET_FOR_SECTION,
    RETIRED_CAP_PER_SECTION,
    RETIREMENT_NO_LONGER_RELEVANT,
    RETIREMENT_REPLACED,
    SECTION_CONTEXT,
    SECTION_FOR_BUCKET,
    SECTION_GOAL,
    SECTION_PREFERENCE,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    SUBTYPES_BY_SECTION,
    VALID_RETIREMENT_REASONS,
    VALID_SECTIONS,
    VALID_STORAGE_BUCKETS,
    empty_sectioned_memory,
    normalize_fact_key,
    validate_sectioned_memory,
)

logger = logging.getLogger(__name__)

_TEXT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "were", "with",
}

_RETIRE_REASON_SORT = {
    "no_longer_relevant": 0,
    "resolved": 1,
    "completed": 2,
    "replaced_by_newer_active_fact": 3,
}


class SectionedCandidateReducerError(ValueError):
    """Raised when sectioned candidate application fails validation."""


def _is_goal_alias_conflict(existing_fact: Dict[str, Any], *, fact_key: str, summary: str) -> bool:
    """True when a new goal upsert is a close alias of an existing active goal (narrow rec-league case)."""

    if existing_fact.get("section") != SECTION_GOAL:
        return False

    existing_key = str(existing_fact.get("fact_key", ""))
    existing_summary = str(existing_fact.get("summary", ""))
    if not existing_key or not existing_summary:
        return False

    combined_existing = f"{existing_key} {existing_summary}".lower()
    combined_new = f"{fact_key} {summary}".lower()

    rec_markers = ("rec league", "recreational")
    summer_markers = ("summer",)
    basketball_markers = ("basketball",)

    existing_has_rec = any(marker in combined_existing for marker in rec_markers)
    new_has_rec = any(marker in combined_new for marker in rec_markers)
    if not (existing_has_rec and new_has_rec):
        return False

    existing_has_summer = any(marker in combined_existing for marker in summer_markers)
    new_has_summer = any(marker in combined_new for marker in summer_markers)
    if not (existing_has_summer and new_has_summer):
        return False

    existing_has_basketball = any(marker in combined_existing for marker in basketball_markers)
    new_has_basketball = any(marker in combined_new for marker in basketball_markers)
    return existing_has_basketball or new_has_basketball


def _normalize_text_tokens(value: Optional[str]) -> set[str]:
    if not isinstance(value, str):
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", value.lower())
        if len(token) >= 3 and token not in _TEXT_STOPWORDS
    }


def _fact_reference_tokens(fact: Dict[str, Any]) -> set[str]:
    tokens = _normalize_text_tokens(fact.get("summary"))
    tokens.update(_normalize_text_tokens(str(fact.get("fact_key", "")).replace(":", " ")))
    return tokens


def _materially_references_fact(text: str, fact: Dict[str, Any]) -> bool:
    candidate_tokens = _normalize_text_tokens(text)
    fact_tokens = _fact_reference_tokens(fact)
    if not candidate_tokens or not fact_tokens:
        return False
    overlap = candidate_tokens & fact_tokens
    if len(overlap) >= 3:
        return True
    smaller = min(len(candidate_tokens), len(fact_tokens))
    if smaller >= 2 and len(overlap) == smaller:
        return True
    return False


def _drop_superseded_fact_references(text: str, superseded_facts: List[Dict[str, Any]]) -> str:
    if not text or not superseded_facts:
        return text
    segments = [segment.strip(" ,;") for segment in re.split(r"[;()]", text) if segment.strip(" ,;")]
    kept_segments: List[str] = []
    for segment in segments:
        if not any(_materially_references_fact(segment, fact) for fact in superseded_facts):
            kept_segments.append(segment)
    if not kept_segments:
        return ""
    return "; ".join(kept_segments)


def _resolve_retire_target_id(
    *,
    candidate: Dict[str, Any],
    facts_by_id: Dict[str, Dict[str, Any]],
) -> Optional[str]:
    target_id = candidate.get("target_id")
    if isinstance(target_id, str) and target_id in facts_by_id:
        return target_id

    fact_key = candidate.get("fact_key")
    if isinstance(fact_key, str) and fact_key.strip():
        cleaned_key = fact_key.strip()
        for existing_id, fact in facts_by_id.items():
            if fact.get("fact_key") == cleaned_key:
                return existing_id

    summary_tokens = _normalize_text_tokens(candidate.get("summary"))
    if summary_tokens:
        best_match_id: Optional[str] = None
        best_overlap = 0.0
        for existing_id, fact in facts_by_id.items():
            fact_tokens = _normalize_text_tokens(fact.get("summary"))
            if not fact_tokens:
                continue
            overlap = len(summary_tokens & fact_tokens) / max(len(summary_tokens), len(fact_tokens))
            if overlap > best_overlap:
                best_overlap = overlap
                best_match_id = existing_id
        if best_match_id is not None and best_overlap >= 0.5:
            return best_match_id

    if isinstance(target_id, str) and target_id.strip():
        ranked = sorted(
            (
                (existing_id, difflib.SequenceMatcher(a=target_id, b=existing_id).ratio())
                for existing_id in facts_by_id
            ),
            key=lambda item: item[1],
            reverse=True,
        )
        if ranked and ranked[0][1] >= 0.92:
            if len(ranked) == 1 or ranked[0][1] - ranked[1][1] >= 0.02:
                return ranked[0][0]

    return None


def _canonical_supersede_key(section: str, raw: str) -> str:
    raw = str(raw).strip()
    if not raw:
        return ""
    prefix = f"{section}:"
    if raw.startswith(prefix):
        return raw
    return normalize_fact_key(section, raw.removeprefix(prefix))


def _supersedes_resolves_to_initial_active(candidate: Dict[str, Any], memory: Dict[str, Any]) -> bool:
    if candidate.get("action") != "upsert" or candidate.get("target_id"):
        return False
    section = candidate.get("section")
    if not isinstance(section, str) or section not in VALID_SECTIONS:
        return False
    keys = candidate.get("supersedes_fact_keys") or []
    if not keys:
        return False
    bucket = BUCKET_FOR_SECTION[section]
    active = memory[bucket]["active"]
    active_keys = {f.get("fact_key") for f in active if isinstance(f, dict)}
    for raw in keys:
        if not isinstance(raw, str) or not raw.strip():
            continue
        ck = _canonical_supersede_key(section, raw)
        if ck and ck in active_keys:
            return True
    return False


def _partition_candidates(
    candidates: List[Dict[str, Any]],
    initial_memory: Dict[str, Any],
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    pass1: List[Dict[str, Any]] = []
    pass2: List[Dict[str, Any]] = []
    for c in candidates:
        action = c.get("action")
        if action == "confirm":
            pass1.append(c)
        elif action == "retire":
            pass1.append(c)
        elif action == "upsert" and c.get("target_id"):
            pass1.append(c)
        elif action == "upsert" and not c.get("target_id"):
            if _supersedes_resolves_to_initial_active(c, initial_memory):
                pass1.append(c)
            else:
                pass2.append(c)
        else:
            pass2.append(c)
    return pass1, pass2


def _is_low_value_other(fact: Dict[str, Any]) -> bool:
    sec = fact.get("section")
    st = fact.get("subtype")
    return (sec == SECTION_CONTEXT and st == "other") or (
        sec == SECTION_PREFERENCE and st == "other"
    )


def _explains_active_truth(memory_id: str, active_facts: List[Dict[str, Any]]) -> bool:
    return any(memory_id in (f.get("supersedes") or []) for f in active_facts)


def _retire_reason_priority(reason: str) -> int:
    return _RETIRE_REASON_SORT.get(reason, 0)


def _retired_eviction_sort_key(
    fact: Dict[str, Any],
    active_facts: List[Dict[str, Any]],
) -> Tuple[int, int, int, int, str]:
    mid = str(fact.get("memory_id", ""))
    # Plan: 1 if explained by active supersedes, else 0 — evict 0 first (ascending).
    explains_key = 1 if _explains_active_truth(mid, active_facts) else 0
    rr = str(fact.get("retirement_reason") or "")
    rpri = _retire_reason_priority(rr)
    retired_at = int(fact.get("retired_at") or 0)
    last_conf = int(fact.get("last_confirmed_at") or 0)
    return (explains_key, rpri, retired_at, last_conf, mid)


def _enforce_retired_cap(bucket: str, memory: Dict[str, Any]) -> None:
    retired = memory[bucket]["retired"]
    cap = RETIRED_CAP_PER_SECTION
    if len(retired) <= cap:
        return
    active = memory[bucket]["active"]
    # Ascending = weakest first at index 0; remove until within cap.
    retired.sort(key=lambda f: _retired_eviction_sort_key(f, active))
    while len(retired) > cap:
        retired.pop(0)


def _route_retired_fact(
    fact: Dict[str, Any],
    *,
    bucket: str,
    memory: Dict[str, Any],
    protected_ids: Set[str],
) -> None:
    active = memory[bucket]["active"]
    mid = str(fact.get("memory_id", ""))
    if mid in protected_ids or _explains_active_truth(mid, active):
        memory[bucket]["retired"].append(fact)
        _enforce_retired_cap(bucket, memory)
        return
    if _is_low_value_other(fact):
        return
    memory[bucket]["retired"].append(fact)
    _enforce_retired_cap(bucket, memory)


def _build_active_index(memory: Dict[str, Any]) -> Dict[str, Tuple[str, int]]:
    """memory_id -> (bucket, index in active list)."""
    index: Dict[str, Tuple[str, int]] = {}
    for bucket in VALID_STORAGE_BUCKETS:
        for i, f in enumerate(memory[bucket]["active"]):
            mid = f.get("memory_id")
            if isinstance(mid, str):
                index[mid] = (bucket, i)
    return index


def _pop_active(memory: Dict[str, Any], bucket: str, memory_id: str) -> Optional[Dict[str, Any]]:
    lst = memory[bucket]["active"]
    for i, f in enumerate(lst):
        if f.get("memory_id") == memory_id:
            return lst.pop(i)
    return None


def _make_retired_dict(
    active_fact: Dict[str, Any],
    *,
    now_epoch: int,
    retirement_reason: str,
) -> Dict[str, Any]:
    d = dict(active_fact)
    d["status"] = STATUS_RETIRED
    d["retirement_reason"] = retirement_reason
    d["retired_at"] = now_epoch
    return d


def _canonical_key_uniqueness_backstop(memory: Dict[str, Any]) -> None:
    for bucket in VALID_STORAGE_BUCKETS:
        active = memory[bucket]["active"]
        seen_keys: Dict[str, int] = {}
        for i, fact in enumerate(active):
            key = fact.get("fact_key")
            if not isinstance(key, str):
                continue
            if key in seen_keys:
                prev_i = seen_keys[key]
                prev_fact = active[prev_i]
                if int(fact.get("updated_at") or 0) >= int(prev_fact.get("updated_at") or 0):
                    seen_keys[key] = i
            else:
                seen_keys[key] = i
        if len(seen_keys) < len(active):
            keep_indices = set(seen_keys.values())
            memory[bucket]["active"] = [f for i, f in enumerate(active) if i in keep_indices]
            logger.warning(
                "canonical_key_uniqueness_backstop: removed duplicate active facts in %s", bucket
            )


def apply_sectioned_refresh(
    validated_llm_output: Dict[str, Any],
    current_memory: Dict[str, Any],
    now_epoch: int,
) -> Dict[str, Any]:
    """Apply sectioned candidates; return sectioned_memory + continuity_summary dicts."""
    memory = copy.deepcopy(current_memory) if current_memory else empty_sectioned_memory()
    for b in VALID_STORAGE_BUCKETS:
        if b not in memory or not isinstance(memory[b], dict):
            memory[b] = {"active": [], "retired": []}
        if "active" not in memory[b]:
            memory[b]["active"] = []
        if "retired" not in memory[b]:
            memory[b]["retired"] = []

    candidates = validated_llm_output.get("candidates") or []
    if not isinstance(candidates, list):
        candidates = []

    initial_memory = copy.deepcopy(memory)
    pass1, pass2 = _partition_candidates(candidates, initial_memory)
    ordered = pass1 + pass2

    superseded_facts: List[Dict[str, Any]] = []

    for candidate in ordered:
        action = candidate.get("action")
        if action == "upsert" and not candidate.get("target_id"):
            _apply_new_create_upsert(
                candidate,
                memory,
                now_epoch,
                superseded_facts,
            )
        elif action == "upsert" and candidate.get("target_id"):
            _apply_update_upsert(candidate, memory, now_epoch)
        elif action == "confirm":
            _apply_confirm(candidate, memory, now_epoch)
        elif action == "retire":
            _apply_retire(
                candidate,
                memory,
                now_epoch,
                superseded_facts,
            )

    _canonical_key_uniqueness_backstop(memory)

    continuity_raw = validated_llm_output.get("continuity") or {}
    if not isinstance(continuity_raw, dict):
        continuity_raw = {}

    summary = continuity_raw.get("summary") or ""
    last_rec = continuity_raw.get("last_recommendation") or ""
    open_loops = continuity_raw.get("open_loops") or []

    if superseded_facts:
        summary = _drop_superseded_fact_references(str(summary), superseded_facts) or (
            "Current coaching context updated."
        )
        last_rec = _drop_superseded_fact_references(str(last_rec), superseded_facts) or (
            "Use the updated current schedule and constraints going forward."
        )
        if isinstance(open_loops, list):
            open_loops = [
                _drop_superseded_fact_references(str(loop), superseded_facts)
                for loop in open_loops
                if isinstance(loop, str)
            ]
            open_loops = [x for x in open_loops if x.strip()]
        else:
            open_loops = []

    continuity = ContinuitySummary(
        summary=summary if isinstance(summary, str) and summary.strip() else "Current coaching context updated.",
        last_recommendation=(
            last_rec
            if isinstance(last_rec, str) and last_rec.strip()
            else "Use the updated current schedule and constraints going forward."
        ),
        open_loops=open_loops if isinstance(open_loops, list) else [],
        updated_at=now_epoch,
    )

    validated = validate_sectioned_memory(memory)
    return {
        "sectioned_memory": validated,
        "continuity_summary": continuity.to_dict(),
    }


def _section_facts_by_id(memory: Dict[str, Any], bucket: str) -> Dict[str, Dict[str, Any]]:
    return {
        str(f["memory_id"]): dict(f)
        for f in memory[bucket]["active"]
        if isinstance(f, dict) and f.get("memory_id")
    }


def _apply_new_create_upsert(
    candidate: Dict[str, Any],
    memory: Dict[str, Any],
    now_epoch: int,
    superseded_facts: List[Dict[str, Any]],
) -> None:
    section = candidate.get("section")
    if not isinstance(section, str) or section not in VALID_SECTIONS:
        logger.warning("sectioned_reducer: invalid section on new upsert: %r", section)
        return
    bucket = BUCKET_FOR_SECTION[section]
    raw_key = candidate.get("fact_key")
    if not isinstance(raw_key, str) or not raw_key.strip():
        logger.warning("sectioned_reducer: missing fact_key on new upsert")
        return
    summary = candidate.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        logger.warning("sectioned_reducer: missing summary on new upsert")
        return
    subtype = candidate.get("subtype")
    if not isinstance(subtype, str) or subtype not in SUBTYPES_BY_SECTION.get(section, frozenset()):
        logger.warning("sectioned_reducer: invalid subtype %r for section %r", subtype, section)
        return

    canonical_key = normalize_fact_key(section, raw_key)
    active = memory[bucket]["active"]
    cap = ACTIVE_CAP_BY_BUCKET[bucket]

    for f in active:
        if f.get("fact_key") == canonical_key:
            raise SectionedCandidateReducerError(
                f"new-create upsert conflicts with existing fact_key {canonical_key!r}; "
                "use target_id update path"
            )

    if section == SECTION_GOAL:
        for f in active:
            if _is_goal_alias_conflict(f, fact_key=canonical_key, summary=summary):
                raise SectionedCandidateReducerError(
                    "new-create upsert conflicts with existing goal alias "
                    f"{f.get('fact_key')!r}; use target_id update path instead"
                )

    raw_sup = candidate.get("supersedes_fact_keys") or []
    resolved_ids: List[str] = []
    if isinstance(raw_sup, list):
        by_key = {f.get("fact_key"): f for f in active if isinstance(f, dict)}
        for raw in raw_sup:
            if not isinstance(raw, str) or not raw.strip():
                continue
            ck = _canonical_supersede_key(section, raw)
            if ck in by_key:
                resolved_ids.append(str(by_key[ck]["memory_id"]))

    supersede_set = set(resolved_ids)
    net_after = len(active) - len(supersede_set) + 1
    if len(active) >= cap and not supersede_set:
        logger.warning(
            "reject_at_cap: section=%s summary=%r active_count=%d cap=%d",
            section,
            summary[:200],
            len(active),
            cap,
        )
        return
    if len(active) >= cap and supersede_set and net_after > cap:
        logger.warning(
            "reject_at_cap: section=%s summary=%r active_count=%d cap=%d (supersede net overflow)",
            section,
            summary[:200],
            len(active),
            cap,
        )
        return

    protected: Set[str] = set(resolved_ids)

    for mid in resolved_ids:
        fact = _pop_active(memory, bucket, mid)
        if fact is None:
            continue
        superseded_facts.append(dict(fact))
        retired = _make_retired_dict(
            fact,
            now_epoch=now_epoch,
            retirement_reason=RETIREMENT_REPLACED,
        )
        _route_retired_fact(retired, bucket=bucket, memory=memory, protected_ids=protected)

    new_id = str(uuid.uuid4())
    new_fact: Dict[str, Any] = {
        "memory_id": new_id,
        "section": section,
        "subtype": subtype,
        "fact_key": canonical_key,
        "summary": summary,
        "status": STATUS_ACTIVE,
        "supersedes": list(resolved_ids),
        "created_at": now_epoch,
        "updated_at": now_epoch,
        "last_confirmed_at": now_epoch,
    }
    if resolved_ids:
        cleaned = _drop_superseded_fact_references(new_fact["summary"], superseded_facts)
        if cleaned:
            new_fact["summary"] = cleaned

    memory[bucket]["active"].append(new_fact)


def _apply_update_upsert(candidate: Dict[str, Any], memory: Dict[str, Any], now_epoch: int) -> None:
    tid = candidate.get("target_id")
    if not isinstance(tid, str) or not tid.strip():
        raise SectionedCandidateReducerError("upsert target_id required for update")
    idx = _build_active_index(memory)
    if tid not in idx:
        raise SectionedCandidateReducerError(
            f"upsert target_id {tid!r} not found in current active facts"
        )
    bucket, _ = idx[tid]
    lst = memory[bucket]["active"]
    fact = None
    for f in lst:
        if f.get("memory_id") == tid:
            fact = f
            break
    if fact is None:
        raise SectionedCandidateReducerError(f"upsert target_id {tid!r} not found")
    if "summary" in candidate and isinstance(candidate["summary"], str):
        fact["summary"] = candidate["summary"].strip()
    if "subtype" in candidate and isinstance(candidate["subtype"], str):
        st = candidate["subtype"].strip()
        sec = str(fact.get("section", ""))
        allowed = SUBTYPES_BY_SECTION.get(sec, frozenset())
        if st in allowed:
            fact["subtype"] = st
    fact["updated_at"] = now_epoch
    fact["last_confirmed_at"] = now_epoch


def _apply_confirm(candidate: Dict[str, Any], memory: Dict[str, Any], now_epoch: int) -> None:
    tid = candidate.get("target_id")
    if not isinstance(tid, str) or not tid.strip():
        raise SectionedCandidateReducerError("confirm requires target_id")
    idx = _build_active_index(memory)
    if tid not in idx:
        raise SectionedCandidateReducerError(
            f"confirm target_id {tid!r} not found in current active facts"
        )
    bucket, _ = idx[tid]
    for f in memory[bucket]["active"]:
        if f.get("memory_id") == tid:
            f["last_confirmed_at"] = now_epoch
            return
    raise SectionedCandidateReducerError(f"confirm target_id {tid!r} not found")


def _apply_retire(
    candidate: Dict[str, Any],
    memory: Dict[str, Any],
    now_epoch: int,
    superseded_facts: List[Dict[str, Any]],
) -> None:
    section = candidate.get("section")
    if not isinstance(section, str) or section not in VALID_SECTIONS:
        logger.warning("sectioned_reducer: invalid section on retire: %r", section)
        return
    bucket = BUCKET_FOR_SECTION[section]
    facts_by_id = _section_facts_by_id(memory, bucket)
    resolved = _resolve_retire_target_id(candidate=candidate, facts_by_id=facts_by_id)
    if resolved is None:
        logger.warning(
            "retire_target_missing: skipping retire for target_id=%r fact_key=%r summary=%r",
            candidate.get("target_id"),
            candidate.get("fact_key"),
            candidate.get("summary"),
        )
        return
    fact = _pop_active(memory, bucket, resolved)
    if fact is None:
        return
    superseded_facts.append(dict(fact))
    reason_raw = candidate.get("retirement_reason")
    if (
        isinstance(reason_raw, str)
        and reason_raw.strip()
        and reason_raw.strip() in VALID_RETIREMENT_REASONS
    ):
        rr = reason_raw.strip()
    else:
        rr = RETIREMENT_NO_LONGER_RELEVANT
    retired = _make_retired_dict(fact, now_epoch=now_epoch, retirement_reason=rr)
    _route_retired_fact(retired, bucket=bucket, memory=memory, protected_ids=set())
