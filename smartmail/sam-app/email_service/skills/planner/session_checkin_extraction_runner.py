"""Runner for session-checkin extraction workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from ai_extraction_contract import (
    ALLOWED_EXPERIENCE_LEVELS,
    ALLOWED_MAIN_SPORTS,
    ALLOWED_RECENT_ILLNESS,
    ALLOWED_RISK_CANDIDATES,
    ALLOWED_SCHEDULE_VARIABILITY,
    ALLOWED_STRUCTURE_PREFERENCES,
    ALLOWED_TIME_BUCKETS,
)
from config import PROFILE_EXTRACTION_MODEL
from skills.planner.session_checkin_extraction_prompt import SYSTEM_PROMPT
from skills.planner.session_checkin_extraction_schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.planner.session_checkin_extraction_validator import (
    SessionCheckinExtractionContractError,
    validate_session_checkin_extraction_output,
)

logger = logging.getLogger(__name__)


def _preview_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "")
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}..."


def _top_level_type_map(payload: Dict[str, Any]) -> Dict[str, str]:
    type_map: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = ",".join(f"{k}:{type(v).__name__}" for k, v in sorted(value.items()))
            type_map[key] = f"dict[{nested}]"
        elif isinstance(value, list):
            item_types = ",".join(sorted({type(item).__name__ for item in value})) if value else "empty"
            type_map[key] = f"list[{item_types}]"
        else:
            type_map[key] = type(value).__name__
    return type_map


class SessionCheckinExtractionProposalError(RuntimeError):
    """Raised when session-checkin extraction generation fails."""


def run_session_checkin_extraction_workflow(
    email_body: str,
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    raw_content = ""
    try:
        logger.info(
            "Session check-in extraction request: body_chars=%s body_preview=%s",
            len(str(email_body or "")),
            _preview_text(email_body),
        )
        selected_model = str(model_name or PROFILE_EXTRACTION_MODEL).strip() or PROFILE_EXTRACTION_MODEL
        system_prompt = (
            f"{SYSTEM_PROMPT}\n\n"
            "Allowed enums:\n"
            f"- risk_candidate: {sorted(ALLOWED_RISK_CANDIDATES)}\n"
            f"- experience_level: {sorted(ALLOWED_EXPERIENCE_LEVELS)}\n"
            f"- time_bucket: {sorted(ALLOWED_TIME_BUCKETS)}\n"
            f"- main_sport_current: {sorted(ALLOWED_MAIN_SPORTS)} or null\n"
            f"- recent_illness: {sorted(ALLOWED_RECENT_ILLNESS)}\n"
            f"- structure_preference: {sorted(ALLOWED_STRUCTURE_PREFERENCES)}\n"
            f"- schedule_variability: {sorted(ALLOWED_SCHEDULE_VARIABILITY)}\n"
        )
        payload, raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=selected_model,
            system_prompt=system_prompt,
            user_content=json.dumps({"email_body": str(email_body or "")}, separators=(",", ":"), ensure_ascii=True),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="session-checkin extraction LLM calls are disabled",
            warning_log_name="session_checkin_extraction",
            retries=1,
            require_live_llm=False,
        )
        logger.info(
            "Session check-in extraction raw response: chars=%s preview=%s",
            len(raw_content),
            _preview_text(raw_content),
        )
        validated = validate_session_checkin_extraction_output(payload)
        logger.info(
            "Session check-in extraction parsed payload: keys=%s field_types=%s",
            sorted(validated.keys()),
            _top_level_type_map(validated),
        )
        return validated
    except (SessionCheckinExtractionContractError, skill_runtime.SkillExecutionError) as exc:
        logger.error(
            "Session check-in extraction failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(getattr(exc, "raw_response", "") or raw_content),
        )
        raise SessionCheckinExtractionProposalError("session_checkin_extraction_failed") from exc
    except Exception as exc:
        logger.error(
            "Session check-in extraction failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(raw_content),
        )
        raise SessionCheckinExtractionProposalError("session_checkin_extraction_failed") from exc
