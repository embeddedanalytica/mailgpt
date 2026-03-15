"""Runner for the long-term memory refresh workflow."""

import json
import logging
from typing import Any, Dict, List, Optional

from athlete_memory_contract import (
    MemoryNote,
    filter_active_memory_notes,
    format_unix_timestamp_for_prompt,
)
from athlete_memory_reducer import reduce_long_term_memory
from config import PROFILE_EXTRACTION_MODEL
from skills.memory.refresh.errors import MemoryRefreshError, MemoryRefreshPromptError
from skills.memory.long_term.prompt import SYSTEM_PROMPT
from skills.memory.long_term.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.long_term.validator import validate_long_term_memory_response
from skills.runtime import SkillExecutionError, execute_json_schema, preview_text

logger = logging.getLogger(__name__)


def build_long_term_memory_user_payload(
    *,
    prior_memory_notes: List[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
) -> str:
    if not isinstance(prior_memory_notes, list):
        raise MemoryRefreshPromptError("prior_memory_notes must be a list")
    if not isinstance(latest_interaction_context, dict):
        raise MemoryRefreshPromptError("latest_interaction_context must be a dict")

    prompt_memory_notes = []
    for note in filter_active_memory_notes(prior_memory_notes):
        normalized = MemoryNote.from_dict(note).to_dict()
        prompt_note = dict(normalized)
        prompt_note["last_confirmed_at_readable"] = format_unix_timestamp_for_prompt(
            normalized["last_confirmed_at"]
        )
        prompt_note["created_at_readable"] = format_unix_timestamp_for_prompt(
            normalized["created_at"]
        )
        prompt_note["updated_at_readable"] = format_unix_timestamp_for_prompt(
            normalized["updated_at"]
        )
        prompt_memory_notes.append(prompt_note)

    payload = {
        "prior_memory_notes": prompt_memory_notes,
        "latest_interaction_context": latest_interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def run_long_term_memory_refresh(
    *,
    prior_memory_notes: List[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
    stored_memory_notes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    raw_content = ""
    try:
        data, raw_content = execute_json_schema(
            logger=logger,
            model_name=PROFILE_EXTRACTION_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_content=build_long_term_memory_user_payload(
                prior_memory_notes=prior_memory_notes,
                latest_interaction_context=latest_interaction_context,
            ),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live long-term memory refresh LLM calls are disabled",
            warning_log_name="memory_refresh_long_term",
        )
        validated = validate_long_term_memory_response(data)
        reduced_notes = reduce_long_term_memory(
            stored_memory_notes=stored_memory_notes
            if stored_memory_notes is not None
            else prior_memory_notes,
            candidate_payload=validated,
        )
        return {
            "memory_notes": reduced_notes,
            "raw_response_text": raw_content,
            "raw_llm_data": data,
            "validated_candidate_payload": validated,
        }
    except Exception as exc:
        if not raw_content and isinstance(exc, SkillExecutionError):
            raw_content = exc.raw_response
        logger.error(
            "Long-term memory refresh failed: %s (raw_response_preview=%s)",
            exc,
            preview_text(raw_content),
        )
        raise MemoryRefreshError(
            "LLM long-term memory refresh failed",
            raw_response=raw_content,
            cause_message=str(exc),
        ) from exc
