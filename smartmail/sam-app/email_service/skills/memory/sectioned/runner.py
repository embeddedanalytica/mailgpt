"""Runner for sectioned candidate memory refresh."""

from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List, Optional

from config import PROFILE_EXTRACTION_MODEL
from sectioned_memory_contract import (
    VALID_STORAGE_BUCKETS,
    normalize_fact_key,
)
from skills.memory.sectioned.errors import SectionedMemoryRefreshError
from skills.memory.sectioned.prompt import SYSTEM_PROMPT
from skills.memory.sectioned.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.refresh_helpers import (
    drop_segments_referencing_facts as _drop_segments_referencing_facts,
    format_continuity_for_prompt as _format_continuity_for_prompt,
    normalize_text_tokens as _normalize_text_tokens,
    prune_resolved_open_loops as _prune_resolved_open_loops,
    stale_continuity_carryover_detected as _stale_continuity_carryover_detected,
)
from skills.memory.sectioned.validator import validate_sectioned_candidate_response
from skills.runtime import SkillExecutionError, execute_json_schema, preview_text

logger = logging.getLogger(__name__)

_REVERSAL_CUE_PATTERNS = [
    re.compile(r"\bno longer\b", re.IGNORECASE),
    re.compile(r"\bused to\b", re.IGNORECASE),
    re.compile(r"\bswitched\s+from\b.{0,60}\bto\b", re.IGNORECASE),
    re.compile(r"\bmoved\s+from\b.{0,60}\bto\b", re.IGNORECASE),
    re.compile(r"\bchanged\s+from\b.{0,60}\bto\b", re.IGNORECASE),
    re.compile(r"\breplaced\b.{0,60}\bwith\b", re.IGNORECASE),
    re.compile(r"\bnow\b.{0,30}\binstead\b", re.IGNORECASE),
    re.compile(r"\bopened up\b", re.IGNORECASE),
    re.compile(r"\bnot anymore\b", re.IGNORECASE),
    re.compile(r"\bswitched\b.{0,20}\bto\b", re.IGNORECASE),
    re.compile(r"\bchanged\b.{0,20}\bto\b", re.IGNORECASE),
    re.compile(r"\bmoved\b.{0,20}\bto\b", re.IGNORECASE),
]


def _has_reversal_cues(text: str) -> bool:
    return any(p.search(text) for p in _REVERSAL_CUE_PATTERNS)


def _flatten_active_facts(sectioned_memory: Dict[str, Any]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    for bucket in VALID_STORAGE_BUCKETS:
        for f in (sectioned_memory.get(bucket) or {}).get("active") or []:
            if isinstance(f, dict):
                out.append(f)
    return out


def _find_fact_by_memory_id(existing: List[Dict[str, Any]], target_id: Any) -> Optional[Dict[str, Any]]:
    if not isinstance(target_id, str) or not target_id.strip():
        return None
    for fact in existing:
        if fact.get("memory_id") == target_id:
            return fact
    return None


def _collect_superseded_facts_sectioned(
    candidates: List[Dict[str, Any]],
    existing_flat: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    superseded: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    facts_by_key = {
        f.get("fact_key"): f
        for f in existing_flat
        if isinstance(f, dict) and isinstance(f.get("fact_key"), str)
    }

    def _append_fact(fact: Optional[Dict[str, Any]]) -> None:
        if not isinstance(fact, dict):
            return
        mid = fact.get("memory_id")
        if isinstance(mid, str) and mid in seen_ids:
            return
        if isinstance(mid, str):
            seen_ids.add(mid)
        superseded.append(fact)

    for candidate in candidates:
        if candidate.get("action") == "retire":
            _append_fact(_find_fact_by_memory_id(existing_flat, candidate.get("target_id")))
        elif candidate.get("action") == "upsert" and not candidate.get("target_id"):
            section = candidate.get("section")
            if section not in {"schedule_anchor", "constraint"}:
                continue
            for raw_key in candidate.get("supersedes_fact_keys") or []:
                if not isinstance(raw_key, str) or not raw_key.strip():
                    continue
                canonical = normalize_fact_key(
                    section, raw_key.strip().removeprefix(f"{section}:")
                )
                _append_fact(facts_by_key.get(canonical))
    return superseded


def _candidates_address_reversal_sectioned(
    candidates: List[Dict[str, Any]],
    sectioned_memory: Dict[str, Any],
) -> bool:
    has_retire = any(c.get("action") == "retire" for c in candidates)
    has_targeted = any(
        c.get("action") == "upsert" and c.get("target_id") for c in candidates
    )
    new_sections: set[str] = set()
    for c in candidates:
        if c.get("action") == "upsert" and not c.get("target_id"):
            sec = c.get("section", "")
            if sec in ("schedule_anchor", "constraint"):
                new_sections.add(sec)
    if has_retire or has_targeted:
        return True
    if not new_sections:
        return False
    existing = _flatten_active_facts(sectioned_memory)
    for fact in existing:
        if fact.get("section") in new_sections:
            return False
    return True


def _clean_sectioned_validated_output(
    *,
    validated: Dict[str, Any],
    sectioned_memory: Dict[str, Any],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    existing_flat = _flatten_active_facts(sectioned_memory)
    superseded_facts = _collect_superseded_facts_sectioned(
        validated["candidates"], existing_flat
    )
    if superseded_facts:
        for candidate in validated["candidates"]:
            if candidate.get("action") == "upsert" and not candidate.get("target_id"):
                summary = candidate.get("summary")
                if isinstance(summary, str):
                    cleaned = _drop_segments_referencing_facts(summary, superseded_facts)
                    if cleaned:
                        candidate["summary"] = cleaned
        continuity = validated["continuity"]
        continuity["summary"] = (
            _drop_segments_referencing_facts(continuity["summary"], superseded_facts)
            or "Current coaching context updated."
        )
        continuity["open_loops"] = [
            cleaned_loop
            for loop in continuity["open_loops"]
            if (cleaned_loop := _drop_segments_referencing_facts(loop, superseded_facts)).strip()
        ]
        coach_reply = interaction_context.get("coach_reply")
        if isinstance(coach_reply, str) and coach_reply.strip():
            continuity["last_recommendation"] = coach_reply.strip()

    continuity = validated["continuity"]
    continuity["open_loops"] = _prune_resolved_open_loops(
        current_continuity=current_continuity,
        interaction_context=interaction_context,
        next_open_loops=list(continuity["open_loops"]),
    )

    if _stale_continuity_carryover_detected(
        current_continuity=current_continuity,
        interaction_context=interaction_context,
        validated=validated,
    ):
        continuity = validated["continuity"]
        continuity["open_loops"] = [
            loop
            for loop in continuity["open_loops"]
            if _normalize_text_tokens(loop)
            & (
                _normalize_text_tokens(interaction_context.get("inbound_email"))
                | _normalize_text_tokens(interaction_context.get("coach_reply"))
            )
        ]

    return validated


def _format_sectioned_memory_for_prompt(sectioned_memory: Dict[str, Any]) -> Dict[str, Any]:
    """Bounded view for the LLM (active facts per bucket)."""
    out: Dict[str, Any] = {}
    for bucket in VALID_STORAGE_BUCKETS:
        active = (sectioned_memory.get(bucket) or {}).get("active") or []
        slim: List[Dict[str, Any]] = []
        for f in active:
            if not isinstance(f, dict):
                continue
            slim.append(
                {
                    "memory_id": str(f.get("memory_id", "")),
                    "section": str(f.get("section", "")),
                    "subtype": str(f.get("subtype", "")),
                    "fact_key": str(f.get("fact_key", "")),
                    "summary": str(f.get("summary", "")),
                }
            )
        out[bucket] = {"active": slim}
    return out


def build_sectioned_memory_refresh_user_payload(
    *,
    current_memory: Dict[str, Any],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> str:
    if not isinstance(interaction_context, dict):
        raise SectionedMemoryRefreshError("interaction_context must be a dict")
    payload = {
        "current_memory": _format_sectioned_memory_for_prompt(current_memory),
        "current_continuity": _format_continuity_for_prompt(current_continuity),
        "interaction_context": interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _run_single_attempt(*, user_payload: str) -> Dict[str, Any]:
    data, _raw = execute_json_schema(
        logger=logger,
        model_name=PROFILE_EXTRACTION_MODEL,
        system_prompt=SYSTEM_PROMPT,
        user_content=user_payload,
        schema_name=JSON_SCHEMA_NAME,
        schema=JSON_SCHEMA,
        disabled_message="live sectioned memory refresh LLM calls are disabled",
        warning_log_name="sectioned_memory_refresh_candidates",
    )
    return validate_sectioned_candidate_response(data)


def run_sectioned_memory_refresh(
    *,
    current_memory: Dict[str, Any],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Run sectioned memory refresh; returns validated candidates + continuity."""
    raw_content = ""
    try:
        user_payload = build_sectioned_memory_refresh_user_payload(
            current_memory=current_memory,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )
        logger.info(
            "Sectioned memory refresh starting payload_chars=%s",
            len(user_payload),
        )
        validated = _run_single_attempt(user_payload=user_payload)

        inbound_email = interaction_context.get("inbound_email", "")
        if (
            isinstance(inbound_email, str)
            and _has_reversal_cues(inbound_email)
            and not _candidates_address_reversal_sectioned(
                validated["candidates"], current_memory
            )
        ):
            logger.warning(
                "reversal_backstop: reversal cues but no retire/update on "
                "schedule_anchor or constraint — retrying once"
            )
            validated = _run_single_attempt(user_payload=user_payload)

        validated = _clean_sectioned_validated_output(
            validated=validated,
            sectioned_memory=current_memory,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )
        logger.info(
            "Sectioned memory refresh completed candidate_count=%s",
            len(validated["candidates"]),
        )
        return validated
    except SectionedMemoryRefreshError as exc:
        # Validation and schema-shape failures raise this directly; do not swallow without a log line.
        logger.warning("Sectioned memory refresh rejected: %s", exc)
        raise
    except Exception as exc:
        if not raw_content and isinstance(exc, SkillExecutionError):
            raw_content = exc.raw_response
        logger.error(
            "Sectioned memory refresh failed: %s (raw_response_preview=%s)",
            exc,
            preview_text(raw_content),
        )
        raise SectionedMemoryRefreshError(
            "LLM sectioned memory refresh failed",
            raw_response=raw_content,
            cause_message=str(exc),
        ) from exc
