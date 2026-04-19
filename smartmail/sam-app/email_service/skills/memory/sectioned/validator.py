"""Validation for sectioned candidate memory refresh LLM output."""

from typing import Any, Dict, List

from sectioned_memory_contract import MAX_OPEN_LOOPS, MAX_OPEN_LOOP_CHARS
from sectioned_memory_contract import (
    SUBTYPES_BY_SECTION,
    VALID_SECTIONS,
    normalize_fact_key,
)

from skills.memory.sectioned.errors import SectionedMemoryRefreshError

VALID_ACTIONS = {"upsert", "confirm", "retire"}
VALID_EVIDENCE_SOURCES = {"athlete_email", "profile_update", "manual_activity", "rule_engine_state"}
VALID_EVIDENCE_STRENGTHS = {"explicit", "strong_inference", "weak_inference"}


def _require_str(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SectionedMemoryRefreshError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_continuity(continuity_raw: Any) -> Dict[str, Any]:
    if not isinstance(continuity_raw, dict):
        raise SectionedMemoryRefreshError("continuity must be a dict")
    summary = _require_str("continuity.summary", continuity_raw.get("summary"))
    last_recommendation = _require_str(
        "continuity.last_recommendation", continuity_raw.get("last_recommendation")
    )
    open_loops_raw = continuity_raw.get("open_loops")
    if not isinstance(open_loops_raw, list):
        raise SectionedMemoryRefreshError("continuity.open_loops must be a list")
    open_loops: List[str] = []
    for idx, item in enumerate(open_loops_raw[:MAX_OPEN_LOOPS]):
        if isinstance(item, str) and item.strip():
            trimmed = item.strip()[:MAX_OPEN_LOOP_CHARS]
            open_loops.append(trimmed)
    return {
        "summary": summary,
        "last_recommendation": last_recommendation,
        "open_loops": open_loops,
    }


def validate_sectioned_candidate_response(data: Any) -> Dict[str, Any]:
    """Validate sectioned memory refresh LLM output. Returns normalized dict."""
    if not isinstance(data, dict):
        raise SectionedMemoryRefreshError("sectioned memory refresh output must be a dict")

    candidates_raw = data.get("candidates")
    if not isinstance(candidates_raw, list):
        raise SectionedMemoryRefreshError("candidates must be a list")

    candidates: List[Dict[str, Any]] = []
    seen_target_ids: Dict[str, int] = {}
    seen_new_canonical_keys: Dict[str, int] = {}

    for idx, item in enumerate(candidates_raw):
        if not isinstance(item, dict):
            raise SectionedMemoryRefreshError(f"candidates[{idx}] must be a dict")
        prefix = f"candidates[{idx}]"

        action = _require_str(f"{prefix}.action", item.get("action"))
        if action not in VALID_ACTIONS:
            raise SectionedMemoryRefreshError(
                f"{prefix}.action must be one of {sorted(VALID_ACTIONS)}, got {action!r}"
            )

        evidence_source = _require_str(f"{prefix}.evidence_source", item.get("evidence_source"))
        if evidence_source not in VALID_EVIDENCE_SOURCES:
            raise SectionedMemoryRefreshError(
                f"{prefix}.evidence_source must be one of {sorted(VALID_EVIDENCE_SOURCES)}, got {evidence_source!r}"
            )

        evidence_strength = _require_str(f"{prefix}.evidence_strength", item.get("evidence_strength"))
        if evidence_strength not in VALID_EVIDENCE_STRENGTHS:
            raise SectionedMemoryRefreshError(
                f"{prefix}.evidence_strength must be one of {sorted(VALID_EVIDENCE_STRENGTHS)}, got {evidence_strength!r}"
            )

        if evidence_source == "rule_engine_state" and action != "confirm":
            raise SectionedMemoryRefreshError(
                f"{prefix}: evidence_source 'rule_engine_state' may only emit confirm actions"
            )

        target_id = item.get("target_id")
        if isinstance(target_id, str):
            target_id = target_id.strip() or None

        candidate: Dict[str, Any] = {
            "action": action,
            "evidence_source": evidence_source,
            "evidence_strength": evidence_strength,
        }
        if target_id:
            candidate["target_id"] = target_id

        if action == "upsert" and not target_id:
            section = _require_str(f"{prefix}.section", item.get("section"))
            if section not in VALID_SECTIONS:
                raise SectionedMemoryRefreshError(
                    f"{prefix}.section must be one of {sorted(VALID_SECTIONS)}, got {section!r}"
                )
            subtype = _require_str(f"{prefix}.subtype", item.get("subtype"))
            if subtype not in SUBTYPES_BY_SECTION.get(section, frozenset()):
                raise SectionedMemoryRefreshError(
                    f"{prefix}.subtype {subtype!r} is not valid for section {section!r}"
                )
            fact_key = _require_str(f"{prefix}.fact_key", item.get("fact_key"))
            summary = _require_str(f"{prefix}.summary", item.get("summary"))

            if evidence_source == "rule_engine_state":
                raise SectionedMemoryRefreshError(
                    f"{prefix}: evidence_source 'rule_engine_state' cannot create new facts"
                )

            canonical = normalize_fact_key(section, fact_key)
            if canonical in seen_new_canonical_keys:
                raise SectionedMemoryRefreshError(
                    f"{prefix}: duplicate canonical key {canonical!r} "
                    f"(conflicts with candidates[{seen_new_canonical_keys[canonical]}])"
                )
            seen_new_canonical_keys[canonical] = idx

            candidate["section"] = section
            candidate["subtype"] = subtype
            candidate["fact_key"] = fact_key
            candidate["summary"] = summary

            raw_supersedes = item.get("supersedes_fact_keys")
            if raw_supersedes is not None:
                if not isinstance(raw_supersedes, list):
                    raise SectionedMemoryRefreshError(f"{prefix}.supersedes_fact_keys must be a list")
                supersedes_fact_keys: List[str] = []
                seen_sup: set[str] = set()
                for key_idx, raw_key in enumerate(raw_supersedes):
                    cleaned = _require_str(f"{prefix}.supersedes_fact_keys[{key_idx}]", raw_key)
                    canonical_key = normalize_fact_key(section, cleaned.removeprefix(f"{section}:"))
                    if canonical_key in seen_sup:
                        continue
                    seen_sup.add(canonical_key)
                    supersedes_fact_keys.append(canonical_key)
                if supersedes_fact_keys:
                    candidate["supersedes_fact_keys"] = supersedes_fact_keys

        elif action == "upsert" and target_id:
            summary = _require_str(f"{prefix}.summary", item.get("summary"))
            candidate["summary"] = summary
            if evidence_source == "rule_engine_state":
                raise SectionedMemoryRefreshError(
                    f"{prefix}: evidence_source 'rule_engine_state' cannot rewrite existing facts"
                )
            # Be tolerant when the model echoes immutable identity fields on update-upserts.
            # target_id remains the authoritative locator; section/fact_key are ignored here.
            raw_subtype = item.get("subtype")
            if raw_subtype is not None and isinstance(raw_subtype, str) and raw_subtype.strip():
                candidate["subtype"] = raw_subtype.strip()

        elif action == "confirm":
            if not target_id:
                raise SectionedMemoryRefreshError(f"{prefix}: confirm requires target_id")
            if evidence_source == "rule_engine_state":
                # only confirm allowed
                pass
            raw_summary = item.get("summary")
            if raw_summary is not None and isinstance(raw_summary, str) and raw_summary.strip():
                candidate["summary"] = raw_summary.strip()

        elif action == "retire":
            if not target_id:
                raise SectionedMemoryRefreshError(f"{prefix}: retire requires target_id")
            if evidence_strength != "explicit":
                raise SectionedMemoryRefreshError(
                    f"{prefix}: retire requires evidence_strength 'explicit', got {evidence_strength!r}"
                )
            if evidence_source == "rule_engine_state":
                raise SectionedMemoryRefreshError(
                    f"{prefix}: evidence_source 'rule_engine_state' cannot retire facts"
                )
            section = _require_str(f"{prefix}.section", item.get("section"))
            if section not in VALID_SECTIONS:
                raise SectionedMemoryRefreshError(
                    f"{prefix}.section must be one of {sorted(VALID_SECTIONS)}, got {section!r}"
                )
            candidate["section"] = section
            raw_fact_key = item.get("fact_key")
            if raw_fact_key is not None:
                candidate["fact_key"] = _require_str(f"{prefix}.fact_key", raw_fact_key)
            raw_summary = item.get("summary")
            if raw_summary is not None and isinstance(raw_summary, str) and raw_summary.strip():
                candidate["summary"] = raw_summary.strip()
            rr = item.get("retirement_reason")
            if isinstance(rr, str) and rr.strip():
                candidate["retirement_reason"] = rr.strip()

        if target_id:
            if target_id in seen_target_ids:
                prev_idx = seen_target_ids[target_id]
                raise SectionedMemoryRefreshError(
                    f"{prefix}: conflicting actions on target_id {target_id!r} "
                    f"(conflicts with candidates[{prev_idx}])"
                )
            seen_target_ids[target_id] = idx

        candidates.append(candidate)

    continuity = _validate_continuity(data.get("continuity"))
    return {"candidates": candidates, "continuity": continuity}
