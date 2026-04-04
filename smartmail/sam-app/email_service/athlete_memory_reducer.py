"""AM2 candidate-operation memory reducer.

Applies validated LLM candidate operations to the current durable fact state.
All persistence decisions are deterministic — the LLM interprets, code persists.
"""

from __future__ import annotations

import difflib
import logging
import re
import uuid
from typing import Any, Dict, List, Optional

from athlete_memory_contract import (
    ADMISSION_THRESHOLD,
    ContinuitySummary,
    DurableFact,
    HIGH_IMPORTANCE_TYPES,
    LOW_VALUE_FACT_TYPES,
    MAX_ACTIVE_FACTS,
    normalize_fact_key,
)

logger = logging.getLogger(__name__)
_TEXT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "were", "with",
}


def _is_goal_alias_conflict(existing_fact: Dict[str, Any], *, fact_key: str, summary: str) -> bool:
    """Return True when a new goal upsert is a close alias of an existing active goal.

    Keep this narrow. The purpose is to avoid duplicate durable goals for simple
    season-goal paraphrases such as "summer rec league" vs
    "summer recreational basketball league".
    """
    if existing_fact.get("fact_type") != "goal":
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

    # If either side names basketball explicitly, treat the rec-league goal as the same goal.
    existing_has_basketball = any(marker in combined_existing for marker in basketball_markers)
    new_has_basketball = any(marker in combined_new for marker in basketball_markers)
    return existing_has_basketball or new_has_basketball


class CandidateReducerError(ValueError):
    """Raised when candidate application fails validation."""


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
    if target_id in facts_by_id:
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


def apply_candidate_refresh(
    validated_llm_output: Dict[str, Any],
    current_facts: List[Dict[str, Any]],
    now_epoch: int,
) -> Dict[str, Any]:
    """Applies validated candidate operations to current durable facts.

    Returns a dict with keys ``memory_notes`` and ``continuity_summary``
    ready for DynamoDB persistence.

    Raises CandidateReducerError if a confirm or targeted upsert references a
    non-existent target_id.
    """
    # Build lookup from current active facts
    facts_by_id: Dict[str, Dict[str, Any]] = {}
    for fact_dict in current_facts:
        mid = fact_dict.get("memory_note_id")
        if mid:
            facts_by_id[mid] = dict(fact_dict)  # shallow copy

    candidates = validated_llm_output["candidates"]
    superseded_facts: List[Dict[str, Any]] = []

    for candidate in candidates:
        action = candidate["action"]
        target_id = candidate.get("target_id")

        if action == "upsert" and not target_id:
            # --- New fact creation ---
            fact_type = candidate["fact_type"]
            fact_key = normalize_fact_key(fact_type, candidate["fact_key"])
            importance = candidate["importance"]
            summary = candidate["summary"]

            for existing in facts_by_id.values():
                if existing.get("fact_key") == fact_key:
                    raise CandidateReducerError(
                        "new-create upsert conflicts with existing canonical fact_key "
                        f"{fact_key!r}; use target_id update path instead"
                    )
                if fact_type == "goal" and _is_goal_alias_conflict(
                    existing,
                    fact_key=fact_key,
                    summary=summary,
                ):
                    raise CandidateReducerError(
                        "new-create upsert conflicts with existing goal alias "
                        f"{existing.get('fact_key')!r}; use target_id update path instead"
                    )

            # Enforce importance floor for high-importance types
            if fact_type in HIGH_IMPORTANCE_TYPES:
                importance = "high"

            # Admission gate: reject low-value new facts when budget is tight
            if (
                fact_type in LOW_VALUE_FACT_TYPES
                and importance != "high"
                and len(facts_by_id) >= ADMISSION_THRESHOLD
            ):
                logger.info(
                    "admission_gate: rejected new %s/%s fact %r (active=%d, threshold=%d)",
                    fact_type, importance, fact_key, len(facts_by_id), ADMISSION_THRESHOLD,
                )
                continue

            new_id = str(uuid.uuid4())
            facts_by_id[new_id] = {
                "memory_note_id": new_id,
                "fact_type": fact_type,
                "fact_key": fact_key,
                "summary": summary,
                "importance": importance,
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "last_confirmed_at": now_epoch,
            }
            superseded_keys = candidate.get("supersedes_fact_keys") or []
            if superseded_keys and fact_type in {"schedule", "constraint"}:
                superseded_keys = {
                    str(key).strip() for key in superseded_keys if isinstance(key, str) and str(key).strip()
                }
                for existing_id, fact in list(facts_by_id.items()):
                    if existing_id == new_id:
                        continue
                    if fact.get("fact_type") != fact_type:
                        continue
                    if fact.get("fact_key") in superseded_keys:
                        superseded_facts.append(dict(fact))
                        del facts_by_id[existing_id]

                sanitized_summary = _drop_superseded_fact_references(
                    facts_by_id[new_id]["summary"],
                    superseded_facts,
                )
                if sanitized_summary:
                    facts_by_id[new_id]["summary"] = sanitized_summary

        elif action == "upsert" and target_id:
            # --- Update existing fact ---
            if target_id not in facts_by_id:
                raise CandidateReducerError(
                    f"upsert target_id {target_id!r} not found in current active facts"
                )
            existing = facts_by_id[target_id]
            existing["summary"] = candidate["summary"]
            existing["updated_at"] = now_epoch
            existing["last_confirmed_at"] = now_epoch
            if "importance" in candidate:
                new_importance = candidate["importance"]
                # Enforce importance floor
                if existing["fact_type"] in HIGH_IMPORTANCE_TYPES:
                    new_importance = "high"
                existing["importance"] = new_importance

        elif action == "confirm":
            # --- Confirm existing fact ---
            if target_id not in facts_by_id:
                raise CandidateReducerError(
                    f"confirm target_id {target_id!r} not found in current active facts"
                )
            facts_by_id[target_id]["last_confirmed_at"] = now_epoch

        elif action == "retire":
            # --- Delete from active list ---
            resolved_target_id = _resolve_retire_target_id(
                candidate=candidate,
                facts_by_id=facts_by_id,
            )
            if resolved_target_id is None:
                logger.warning(
                    "retire_target_missing: skipping retire for target_id=%r fact_key=%r summary=%r",
                    target_id,
                    candidate.get("fact_key"),
                    candidate.get("summary"),
                )
                continue
            superseded_facts.append(dict(facts_by_id[resolved_target_id]))
            del facts_by_id[resolved_target_id]

    # Collect active facts
    active_facts = list(facts_by_id.values())

    # --- Canonical key uniqueness backstop ---
    seen_keys: Dict[str, int] = {}  # canonical_key -> index of best (most recent updated_at)
    for i, fact in enumerate(active_facts):
        key = fact["fact_key"]
        if key in seen_keys:
            prev_idx = seen_keys[key]
            prev_fact = active_facts[prev_idx]
            # Keep the one with the most recent updated_at
            if fact["updated_at"] >= prev_fact["updated_at"]:
                seen_keys[key] = i
        else:
            seen_keys[key] = i
    if len(seen_keys) < len(active_facts):
        keep_indices = set(seen_keys.values())
        active_facts = [f for i, f in enumerate(active_facts) if i in keep_indices]
        logger.warning(
            "canonical_key_uniqueness_backstop: removed duplicate active facts, "
            "active_count=%d", len(active_facts)
        )

    # --- Budget enforcement ---
    # Fact-type eviction tiers: other/preference evicted before schedule
    _FACT_TYPE_EVICTION_ORDER = {"other": 0, "preference": 1, "schedule": 2, "constraint": 3, "goal": 3}

    if len(active_facts) > MAX_ACTIVE_FACTS:
        # Sort: medium importance first, then least-valuable fact_type first, then oldest confirmed first
        def _eviction_sort_key(f: Dict[str, Any]) -> tuple:
            importance_order = 0 if f["importance"] == "medium" else 1
            type_order = _FACT_TYPE_EVICTION_ORDER.get(f.get("fact_type", "other"), 0)
            return (importance_order, type_order, f["last_confirmed_at"])

        active_facts.sort(key=_eviction_sort_key)

        # Evict from the front (least valuable first), but never evict high-importance
        evicted: List[Dict[str, Any]] = []
        kept: List[Dict[str, Any]] = []
        for fact in active_facts:
            if fact["importance"] != "high" and len(active_facts) - len(evicted) > MAX_ACTIVE_FACTS:
                evicted.append(fact)
            else:
                kept.append(fact)

        if evicted:
            logger.info(
                "budget_enforcement: evicted %d medium-importance facts, active_count=%d",
                len(evicted), len(kept),
            )

        if len(kept) > MAX_ACTIVE_FACTS:
            logger.warning(
                "budget_overflow: %d active facts (all high-importance), budget=%d",
                len(kept), MAX_ACTIVE_FACTS,
            )

        active_facts = kept

    # --- Continuity (unchanged from AM3) ---
    continuity_raw = validated_llm_output["continuity"]
    sanitized_summary = _drop_superseded_fact_references(
        continuity_raw["summary"],
        superseded_facts,
    )
    sanitized_recommendation = _drop_superseded_fact_references(
        continuity_raw["last_recommendation"],
        superseded_facts,
    )
    continuity = ContinuitySummary(
        summary=sanitized_summary or "Current coaching context updated.",
        last_recommendation=sanitized_recommendation or "Use the updated current schedule and constraints going forward.",
        open_loops=[
            sanitized_loop
            for loop in continuity_raw["open_loops"]
            if (sanitized_loop := _drop_superseded_fact_references(loop, superseded_facts)).strip()
        ],
        updated_at=now_epoch,
    )

    return {
        "memory_notes": [DurableFact.from_dict(f, index=i).to_dict() for i, f in enumerate(active_facts)],
        "continuity_summary": continuity.to_dict(),
    }
