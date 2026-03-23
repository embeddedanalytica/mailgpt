"""Runner for the candidate-operation memory refresh workflow (AM2)."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

from athlete_memory_contract import format_unix_timestamp_for_prompt
from config import PROFILE_EXTRACTION_MODEL
from skills.memory.unified.errors import MemoryRefreshError, MemoryRefreshPromptError
from skills.memory.unified.prompt import SYSTEM_PROMPT
from skills.memory.unified.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.unified.validator import validate_candidate_memory_response
from skills.runtime import SkillExecutionError, execute_json_schema, preview_text

logger = logging.getLogger(__name__)

# Reversal-cue patterns for the backstop check
_REVERSAL_CUE_PATTERNS = [
    re.compile(r"\bno longer\b", re.IGNORECASE),
    re.compile(r"\bused to\b", re.IGNORECASE),
    re.compile(r"\bnow\b.{0,30}\binstead\b", re.IGNORECASE),
    re.compile(r"\bopened up\b", re.IGNORECASE),
    re.compile(r"\bnot anymore\b", re.IGNORECASE),
    re.compile(r"\bswitched\b.{0,20}\bto\b", re.IGNORECASE),
    re.compile(r"\bchanged\b.{0,20}\bto\b", re.IGNORECASE),
    re.compile(r"\bmoved\b.{0,20}\bto\b", re.IGNORECASE),
]


def _has_reversal_cues(text: str) -> bool:
    """Returns True if the text contains explicit reversal language."""
    return any(p.search(text) for p in _REVERSAL_CUE_PATTERNS)


def _candidates_target_schedule_or_constraint(
    candidates: List[Dict[str, Any]],
) -> bool:
    """Returns True if any candidate retires or updates a schedule/constraint fact."""
    for c in candidates:
        action = c.get("action")
        if action == "retire":
            return True
        if action == "upsert" and c.get("target_id"):
            # Targeted upsert — we can't check fact_type here (it's on the existing fact),
            # but a targeted upsert signals the LLM is updating an existing fact.
            return True
        if action == "upsert" and not c.get("target_id"):
            ft = c.get("fact_type", "")
            if ft in ("schedule", "constraint"):
                return True
    return False


def _format_memory_notes_for_prompt(memory_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Formats active durable facts for the LLM prompt."""
    formatted: List[Dict[str, Any]] = []
    for note in memory_notes:
        if not isinstance(note, dict):
            continue
        entry: Dict[str, Any] = {
            "memory_note_id": str(note.get("memory_note_id", "")),
            "fact_type": str(note.get("fact_type", "")),
            "fact_key": str(note.get("fact_key", "")),
            "summary": str(note.get("summary", "")),
        }
        last_confirmed = note.get("last_confirmed_at")
        if last_confirmed is not None:
            try:
                entry["last_confirmed_readable"] = format_unix_timestamp_for_prompt(last_confirmed)
            except Exception:
                pass
        if entry["memory_note_id"] and entry["summary"]:
            formatted.append(entry)
    return formatted


def _format_continuity_for_prompt(continuity: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Formats continuity summary for the LLM prompt."""
    if continuity is None or not isinstance(continuity, dict):
        return None
    formatted: Dict[str, Any] = {}
    for field in ("summary", "last_recommendation"):
        value = continuity.get(field)
        if isinstance(value, str) and value.strip():
            formatted[field] = value.strip()
    open_loops = continuity.get("open_loops")
    if isinstance(open_loops, list):
        formatted["open_loops"] = [
            str(item).strip() for item in open_loops if isinstance(item, str) and str(item).strip()
        ]
    updated_at = continuity.get("updated_at")
    if updated_at is not None:
        try:
            formatted["updated_at_readable"] = format_unix_timestamp_for_prompt(updated_at)
        except Exception:
            pass
    return formatted if formatted else None


def build_memory_refresh_user_payload(
    *,
    current_memory_notes: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> str:
    """Builds the JSON user-message payload for the candidate memory refresh LLM call."""
    if not isinstance(interaction_context, dict):
        raise MemoryRefreshPromptError("interaction_context must be a dict")

    payload = {
        "current_active_facts": _format_memory_notes_for_prompt(current_memory_notes),
        "current_continuity": _format_continuity_for_prompt(current_continuity),
        "interaction_context": interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def _run_single_attempt(
    *,
    user_payload: str,
) -> Dict[str, Any]:
    """Runs a single LLM call and validates the response."""
    data, raw_content = execute_json_schema(
        logger=logger,
        model_name=PROFILE_EXTRACTION_MODEL,
        system_prompt=SYSTEM_PROMPT,
        user_content=user_payload,
        schema_name=JSON_SCHEMA_NAME,
        schema=JSON_SCHEMA,
        disabled_message="live candidate memory refresh LLM calls are disabled",
        warning_log_name="memory_refresh_candidates",
    )
    return validate_candidate_memory_response(data)


def run_candidate_memory_refresh(
    *,
    current_memory_notes: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Runs the candidate-operation memory refresh skill.

    Returns a validated dict with keys: candidates, continuity.
    Raises MemoryRefreshError on failure.
    """
    raw_content = ""
    try:
        user_payload = build_memory_refresh_user_payload(
            current_memory_notes=current_memory_notes,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )
        logger.info(
            "Candidate memory refresh starting payload_chars=%s",
            len(user_payload),
        )

        validated = _run_single_attempt(user_payload=user_payload)

        # --- Reversal backstop ---
        inbound_email = interaction_context.get("inbound_email", "")
        if (
            isinstance(inbound_email, str)
            and _has_reversal_cues(inbound_email)
            and not _candidates_target_schedule_or_constraint(validated["candidates"])
        ):
            logger.warning(
                "reversal_backstop: reversal cues detected but no retire/update on "
                "schedule or constraint — retrying once"
            )
            validated = _run_single_attempt(user_payload=user_payload)

        logger.info(
            "Candidate memory refresh completed candidate_count=%s open_loops=%s",
            len(validated["candidates"]),
            len(validated["continuity"]["open_loops"]),
        )
        return validated

    except MemoryRefreshError:
        raise
    except Exception as exc:
        if not raw_content and isinstance(exc, SkillExecutionError):
            raw_content = exc.raw_response
        logger.error(
            "Candidate memory refresh failed: %s (raw_response_preview=%s)",
            exc,
            preview_text(raw_content),
        )
        raise MemoryRefreshError(
            "LLM candidate memory refresh failed",
            raw_response=raw_content,
            cause_message=str(exc),
        ) from exc
