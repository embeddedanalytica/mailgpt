"""Validation for the candidate-operation memory refresh LLM output (AM2)."""

from typing import Any, Dict, List

from athlete_memory_contract import (
    MAX_OPEN_LOOPS,
    VALID_FACT_TYPES,
    VALID_IMPORTANCE_LEVELS,
    normalize_fact_key,
)
from skills.memory.unified.errors import MemoryRefreshError

VALID_ACTIONS = {"upsert", "confirm", "retire"}
VALID_EVIDENCE_SOURCES = {"athlete_email", "profile_update", "manual_activity", "rule_engine_state"}
VALID_EVIDENCE_STRENGTHS = {"explicit", "strong_inference", "weak_inference"}


def _require_str(field: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise MemoryRefreshError(f"{field} must be a non-empty string")
    return value.strip()


def _validate_continuity(continuity_raw: Any) -> Dict[str, Any]:
    """Validates continuity section (unchanged from AM3)."""
    if not isinstance(continuity_raw, dict):
        raise MemoryRefreshError("continuity must be a dict")

    summary = _require_str("continuity.summary", continuity_raw.get("summary"))
    last_recommendation = _require_str(
        "continuity.last_recommendation", continuity_raw.get("last_recommendation")
    )

    open_loops_raw = continuity_raw.get("open_loops")
    if not isinstance(open_loops_raw, list):
        raise MemoryRefreshError("continuity.open_loops must be a list")

    open_loops: List[str] = []
    for idx, item in enumerate(open_loops_raw[:MAX_OPEN_LOOPS]):
        if isinstance(item, str) and item.strip():
            open_loops.append(item.strip())

    return {
        "summary": summary,
        "last_recommendation": last_recommendation,
        "open_loops": open_loops,
    }


def validate_candidate_memory_response(data: Any) -> Dict[str, Any]:
    """Validates and normalizes the raw LLM output for candidate-operation memory refresh.

    Returns a dict with keys: candidates, continuity.
    Raises MemoryRefreshError on invalid output.
    """
    if not isinstance(data, dict):
        raise MemoryRefreshError("candidate memory refresh output must be a dict")

    # --- candidates ---
    candidates_raw = data.get("candidates")
    if not isinstance(candidates_raw, list):
        raise MemoryRefreshError("candidates must be a list")

    candidates: List[Dict[str, Any]] = []
    seen_target_ids: Dict[str, int] = {}  # target_id -> first index
    seen_new_canonical_keys: Dict[str, int] = {}  # canonical_key -> first index

    for idx, item in enumerate(candidates_raw):
        if not isinstance(item, dict):
            raise MemoryRefreshError(f"candidates[{idx}] must be a dict")

        prefix = f"candidates[{idx}]"

        # action (required)
        action = _require_str(f"{prefix}.action", item.get("action"))
        if action not in VALID_ACTIONS:
            raise MemoryRefreshError(
                f"{prefix}.action must be one of {sorted(VALID_ACTIONS)}, got {action!r}"
            )

        # evidence_source (required)
        evidence_source = _require_str(f"{prefix}.evidence_source", item.get("evidence_source"))
        if evidence_source not in VALID_EVIDENCE_SOURCES:
            raise MemoryRefreshError(
                f"{prefix}.evidence_source must be one of {sorted(VALID_EVIDENCE_SOURCES)}, got {evidence_source!r}"
            )

        # evidence_strength (required)
        evidence_strength = _require_str(f"{prefix}.evidence_strength", item.get("evidence_strength"))
        if evidence_strength not in VALID_EVIDENCE_STRENGTHS:
            raise MemoryRefreshError(
                f"{prefix}.evidence_strength must be one of {sorted(VALID_EVIDENCE_STRENGTHS)}, got {evidence_strength!r}"
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

        # --- action-specific validation ---

        if action == "upsert" and not target_id:
            # New fact creation
            fact_type = _require_str(f"{prefix}.fact_type", item.get("fact_type"))
            if fact_type not in VALID_FACT_TYPES:
                raise MemoryRefreshError(
                    f"{prefix}.fact_type must be one of {sorted(VALID_FACT_TYPES)}, got {fact_type!r}"
                )
            fact_key = _require_str(f"{prefix}.fact_key", item.get("fact_key"))
            summary = _require_str(f"{prefix}.summary", item.get("summary"))
            importance = _require_str(f"{prefix}.importance", item.get("importance"))
            if importance not in VALID_IMPORTANCE_LEVELS:
                raise MemoryRefreshError(
                    f"{prefix}.importance must be one of {sorted(VALID_IMPORTANCE_LEVELS)}, got {importance!r}"
                )

            # rule_engine_state cannot create new facts
            if evidence_source == "rule_engine_state":
                raise MemoryRefreshError(
                    f"{prefix}: evidence_source 'rule_engine_state' cannot create new facts (upsert without target_id)"
                )

            # Check duplicate canonical keys among new-create upserts
            canonical = normalize_fact_key(fact_type, fact_key)
            if canonical in seen_new_canonical_keys:
                raise MemoryRefreshError(
                    f"{prefix}: duplicate canonical key {canonical!r} "
                    f"(conflicts with candidates[{seen_new_canonical_keys[canonical]}])"
                )
            seen_new_canonical_keys[canonical] = idx

            candidate["fact_type"] = fact_type
            candidate["fact_key"] = fact_key
            candidate["summary"] = summary
            candidate["importance"] = importance
            raw_supersedes = item.get("supersedes_fact_keys")
            if raw_supersedes is not None:
                if not isinstance(raw_supersedes, list):
                    raise MemoryRefreshError(f"{prefix}.supersedes_fact_keys must be a list")
                supersedes_fact_keys: List[str] = []
                seen_supersedes: set[str] = set()
                for key_idx, raw_key in enumerate(raw_supersedes):
                    cleaned_key = _require_str(
                        f"{prefix}.supersedes_fact_keys[{key_idx}]",
                        raw_key,
                    )
                    canonical_key = normalize_fact_key(fact_type, cleaned_key.removeprefix(f"{fact_type}:"))
                    if canonical_key in seen_supersedes:
                        continue
                    seen_supersedes.add(canonical_key)
                    supersedes_fact_keys.append(canonical_key)
                if supersedes_fact_keys:
                    candidate["supersedes_fact_keys"] = supersedes_fact_keys

        elif action == "upsert" and target_id:
            # Update existing fact — fact_type and fact_key are forbidden (immutable)
            if item.get("fact_type") is not None:
                raise MemoryRefreshError(
                    f"{prefix}: fact_type is forbidden on upsert with target_id (immutable after creation)"
                )
            if item.get("fact_key") is not None:
                raise MemoryRefreshError(
                    f"{prefix}: fact_key is forbidden on upsert with target_id (immutable after creation)"
                )
            summary = _require_str(f"{prefix}.summary", item.get("summary"))
            candidate["summary"] = summary

            # rule_engine_state cannot mutate existing facts
            if evidence_source == "rule_engine_state":
                raise MemoryRefreshError(
                    f"{prefix}: evidence_source 'rule_engine_state' cannot rewrite existing facts"
                )

            # importance is optional on update
            raw_importance = item.get("importance")
            if raw_importance is not None:
                importance = _require_str(f"{prefix}.importance", raw_importance)
                if importance not in VALID_IMPORTANCE_LEVELS:
                    raise MemoryRefreshError(
                        f"{prefix}.importance must be one of {sorted(VALID_IMPORTANCE_LEVELS)}, got {importance!r}"
                    )
                candidate["importance"] = importance

        elif action == "confirm":
            if not target_id:
                raise MemoryRefreshError(f"{prefix}: confirm requires target_id")
            # summary is optional on confirm
            raw_summary = item.get("summary")
            if raw_summary is not None and isinstance(raw_summary, str) and raw_summary.strip():
                candidate["summary"] = raw_summary.strip()

        elif action == "retire":
            if not target_id:
                raise MemoryRefreshError(f"{prefix}: retire requires target_id")
            if evidence_strength != "explicit":
                raise MemoryRefreshError(
                    f"{prefix}: retire requires evidence_strength 'explicit', got {evidence_strength!r}"
                )
            if evidence_source == "rule_engine_state":
                raise MemoryRefreshError(
                    f"{prefix}: evidence_source 'rule_engine_state' cannot retire facts"
                )
            raw_fact_key = item.get("fact_key")
            if raw_fact_key is not None:
                candidate["fact_key"] = _require_str(f"{prefix}.fact_key", raw_fact_key)
            raw_summary = item.get("summary")
            if raw_summary is not None and isinstance(raw_summary, str) and raw_summary.strip():
                candidate["summary"] = raw_summary.strip()

        # --- cross-candidate checks for target_id conflicts ---
        if target_id:
            if target_id in seen_target_ids:
                prev_idx = seen_target_ids[target_id]
                raise MemoryRefreshError(
                    f"{prefix}: conflicting actions on target_id {target_id!r} "
                    f"(conflicts with candidates[{prev_idx}])"
                )
            seen_target_ids[target_id] = idx

        candidates.append(candidate)

    # --- continuity ---
    continuity = _validate_continuity(data.get("continuity"))

    return {
        "candidates": candidates,
        "continuity": continuity,
    }
