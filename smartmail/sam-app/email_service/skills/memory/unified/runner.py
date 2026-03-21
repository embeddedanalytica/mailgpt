"""Runner for the unified memory refresh workflow (AM3)."""

import json
import logging
from typing import Any, Dict, List, Optional

from athlete_memory_contract import (
    BACKBONE_SLOT_KEYS,
    BackboneSlots,
    ContinuitySummary,
    format_unix_timestamp_for_prompt,
)
from config import PROFILE_EXTRACTION_MODEL
from skills.memory.unified.errors import MemoryRefreshError, MemoryRefreshPromptError
from skills.memory.unified.prompt import SYSTEM_PROMPT
from skills.memory.unified.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.unified.validator import validate_unified_memory_response
from skills.runtime import SkillExecutionError, execute_json_schema, preview_text

logger = logging.getLogger(__name__)


def _format_backbone_for_prompt(backbone: Dict[str, Any]) -> Dict[str, Any]:
    """Formats backbone slots for the LLM prompt, adding readable timestamps."""
    formatted: Dict[str, Any] = {}
    for key in BACKBONE_SLOT_KEYS:
        slot = backbone.get(key)
        if not isinstance(slot, dict) or slot.get("summary") is None:
            formatted[key] = None
            continue
        entry: Dict[str, Any] = {"summary": slot["summary"]}
        updated_at = slot.get("updated_at")
        if updated_at is not None:
            try:
                entry["updated_at_readable"] = format_unix_timestamp_for_prompt(updated_at)
            except Exception:
                pass
        formatted[key] = entry
    return formatted


def _format_context_notes_for_prompt(context_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Formats context notes for the LLM prompt."""
    formatted: List[Dict[str, Any]] = []
    for note in context_notes:
        if not isinstance(note, dict):
            continue
        entry: Dict[str, Any] = {
            "label": str(note.get("label", "")).strip(),
            "summary": str(note.get("summary", "")).strip(),
        }
        updated_at = note.get("updated_at")
        if updated_at is not None:
            try:
                entry["updated_at_readable"] = format_unix_timestamp_for_prompt(updated_at)
            except Exception:
                pass
        if entry["label"] and entry["summary"]:
            formatted.append(entry)
    return formatted


def _format_continuity_for_prompt(continuity: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Formats continuity summary for the LLM prompt."""
    if continuity is None:
        return None
    if not isinstance(continuity, dict):
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


def build_unified_memory_user_payload(
    *,
    current_backbone: Dict[str, Any],
    current_context_notes: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> str:
    """Builds the JSON user-message payload for the unified memory refresh LLM call."""
    if not isinstance(interaction_context, dict):
        raise MemoryRefreshPromptError("interaction_context must be a dict")

    payload = {
        "current_backbone": _format_backbone_for_prompt(current_backbone),
        "current_context_notes": _format_context_notes_for_prompt(current_context_notes),
        "current_continuity": _format_continuity_for_prompt(current_continuity),
        "interaction_context": interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def run_unified_memory_refresh(
    *,
    current_backbone: Dict[str, Any],
    current_context_notes: List[Dict[str, Any]],
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    """Runs the unified memory refresh skill (single LLM call).

    Returns a validated dict with keys: backbone, context_notes, continuity.
    Raises MemoryRefreshError on failure.
    """
    raw_content = ""
    try:
        user_payload = build_unified_memory_user_payload(
            current_backbone=current_backbone,
            current_context_notes=current_context_notes,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )
        logger.info(
            "Unified memory refresh starting payload_chars=%s",
            len(user_payload),
        )

        data, raw_content = execute_json_schema(
            logger=logger,
            model_name=PROFILE_EXTRACTION_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_content=user_payload,
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live unified memory refresh LLM calls are disabled",
            warning_log_name="memory_refresh_unified",
        )

        validated = validate_unified_memory_response(data)
        logger.info(
            "Unified memory refresh completed backbone_populated=%s context_count=%s open_loops=%s",
            sum(1 for k in BACKBONE_SLOT_KEYS if validated["backbone"].get(k)),
            len(validated["context_notes"]),
            len(validated["continuity"]["open_loops"]),
        )
        return validated

    except MemoryRefreshError:
        raise
    except Exception as exc:
        if not raw_content and isinstance(exc, SkillExecutionError):
            raw_content = exc.raw_response
        logger.error(
            "Unified memory refresh failed: %s (raw_response_preview=%s)",
            exc,
            preview_text(raw_content),
        )
        raise MemoryRefreshError(
            "LLM unified memory refresh failed",
            raw_response=raw_content,
            cause_message=str(exc),
        ) from exc
