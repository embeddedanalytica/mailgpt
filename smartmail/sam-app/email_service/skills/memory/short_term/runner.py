"""Runner for the short-term memory refresh workflow."""

import json
import logging
from typing import Any, Dict, Optional

from athlete_memory_contract import ContinuitySummary, format_unix_timestamp_for_prompt
from config import PROFILE_EXTRACTION_MODEL
from skills.memory.refresh.errors import MemoryRefreshError, MemoryRefreshPromptError
from skills.memory.short_term.prompt import SYSTEM_PROMPT
from skills.memory.short_term.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.short_term.validator import validate_short_term_memory_response
from skills.runtime import SkillExecutionError, execute_json_schema, preview_text

logger = logging.getLogger(__name__)


def build_short_term_memory_user_payload(
    *,
    prior_continuity_summary: Optional[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
) -> str:
    if prior_continuity_summary is not None and not isinstance(prior_continuity_summary, dict):
        raise MemoryRefreshPromptError("prior_continuity_summary must be a dict or None")
    if not isinstance(latest_interaction_context, dict):
        raise MemoryRefreshPromptError("latest_interaction_context must be a dict")

    prompt_continuity_summary = None
    if prior_continuity_summary is not None:
        normalized = ContinuitySummary.from_dict(prior_continuity_summary).to_dict()
        prompt_continuity_summary = dict(normalized)
        prompt_continuity_summary["updated_at_readable"] = format_unix_timestamp_for_prompt(
            normalized["updated_at"]
        )

    payload = {
        "prior_continuity_summary": prompt_continuity_summary,
        "latest_interaction_context": latest_interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def run_short_term_memory_refresh(
    *,
    prior_continuity_summary: Optional[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    raw_content = ""
    try:
        data, raw_content = execute_json_schema(
            logger=logger,
            model_name=PROFILE_EXTRACTION_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_content=build_short_term_memory_user_payload(
                prior_continuity_summary=prior_continuity_summary,
                latest_interaction_context=latest_interaction_context,
            ),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live short-term memory refresh LLM calls are disabled",
            warning_log_name="memory_refresh_short_term",
        )
        return validate_short_term_memory_response(data)
    except Exception as exc:
        if not raw_content and isinstance(exc, SkillExecutionError):
            raw_content = exc.raw_response
        logger.error(
            "Short-term memory refresh failed: %s (raw_response_preview=%s)",
            exc,
            preview_text(raw_content),
        )
        raise MemoryRefreshError(
            "LLM short-term memory refresh failed",
            raw_response=raw_content,
            cause_message=str(exc),
        ) from exc
