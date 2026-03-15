"""Runner for the memory refresh routing workflow."""

import json
import logging
from typing import Any, Dict, List, Optional

import skills.runtime as skill_runtime
from athlete_memory_contract import (
    ContinuitySummary,
    MemoryNote,
    filter_active_memory_notes,
    format_unix_timestamp_for_prompt,
)
from config import OPENAI_CLASSIFICATION_MODEL
from skills.memory.eligibility.errors import MemoryRefreshEligibilityError
from skills.memory.router.prompt import SYSTEM_PROMPT
from skills.memory.router.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.router.validator import validate_router_payload

logger = logging.getLogger(__name__)


def _fallback(reason_resolution: str) -> Dict[str, Any]:
    return {
        "route": "neither",
        "model_name": OPENAI_CLASSIFICATION_MODEL,
        "resolution_source": "fallback",
        "reason_resolution": reason_resolution,
        "raw_response_text": "",
        "raw_llm_data": None,
    }


def build_memory_router_user_payload(
    *,
    prior_memory_notes: List[Dict[str, Any]],
    prior_continuity_summary: Optional[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
) -> str:
    if not isinstance(prior_memory_notes, list):
        raise MemoryRefreshEligibilityError("prior_memory_notes must be a list")
    if prior_continuity_summary is not None and not isinstance(prior_continuity_summary, dict):
        raise MemoryRefreshEligibilityError("prior_continuity_summary must be a dict or None")
    if not isinstance(latest_interaction_context, dict):
        raise MemoryRefreshEligibilityError("latest_interaction_context must be a dict")

    prompt_memory_notes = []
    for note in filter_active_memory_notes(prior_memory_notes):
        normalized = MemoryNote.from_dict(note).to_dict()
        prompt_note = dict(normalized)
        prompt_note["last_confirmed_at_readable"] = format_unix_timestamp_for_prompt(
            normalized["last_confirmed_at"]
        )
        prompt_memory_notes.append(prompt_note)

    prompt_continuity_summary = None
    if prior_continuity_summary is not None:
        normalized = ContinuitySummary.from_dict(prior_continuity_summary).to_dict()
        prompt_continuity_summary = dict(normalized)
        prompt_continuity_summary["updated_at_readable"] = format_unix_timestamp_for_prompt(
            normalized["updated_at"]
        )

    payload = {
        "prior_memory_notes": prompt_memory_notes,
        "prior_continuity_summary": prompt_continuity_summary,
        "latest_interaction_context": latest_interaction_context,
    }
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=True)


def run_memory_router(
    *,
    prior_memory_notes: List[Dict[str, Any]],
    prior_continuity_summary: Optional[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    if not skill_runtime.live_llm_enabled():
        return _fallback("live_llm_disabled")

    try:
        payload, raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=OPENAI_CLASSIFICATION_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_content=build_memory_router_user_payload(
                prior_memory_notes=prior_memory_notes,
                prior_continuity_summary=prior_continuity_summary,
                latest_interaction_context=latest_interaction_context,
            ),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live memory-refresh router LLM calls are disabled",
            warning_log_name="memory_refresh_router",
            retries=1,
        )
        validated = validate_router_payload(payload)
        logger.info(
            "memory_refresh_router route=%s model=%s",
            validated["route"],
            validated["model_name"],
        )
        validated["raw_response_text"] = raw_content
        validated["raw_llm_data"] = payload
        return validated
    except MemoryRefreshEligibilityError:
        return _fallback("single_prompt_validation_failed")
    except skill_runtime.SkillExecutionError as exc:
        if exc.code == "invalid_json_response":
            fallback = _fallback("single_prompt_validation_failed")
            fallback["raw_response_text"] = exc.raw_response
            return fallback
        logger.error("Error extracting memory refresh route: %s", exc)
        fallback = _fallback("llm_memory_refresh_router_failed")
        fallback["raw_response_text"] = exc.raw_response
        return fallback
    except Exception as exc:
        logger.error("Error extracting memory refresh route: %s", exc)
        return _fallback("llm_memory_refresh_router_failed")
