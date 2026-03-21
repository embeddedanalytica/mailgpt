"""Runner for profile-extraction workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import PROFILE_EXTRACTION_MODEL
from skills.planner.profile_extraction_prompt import SYSTEM_PROMPT, build_intake_aware_prompt
from skills.planner.profile_extraction_schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.planner.profile_extraction_validator import (
    ProfileExtractionContractError,
    validate_profile_extraction_output,
)

logger = logging.getLogger(__name__)


class ProfileExtractionProposalError(RuntimeError):
    """Raised when profile extraction generation fails."""


def run_profile_extraction_workflow(
    email_body: str,
    *,
    model_name: Optional[str] = None,
    missing_fields: Optional[list[str]] = None,
) -> Dict[str, Any]:
    raw_content = ""
    try:
        selected_model = str(model_name or PROFILE_EXTRACTION_MODEL).strip() or PROFILE_EXTRACTION_MODEL
        system_prompt = build_intake_aware_prompt(missing_fields) if missing_fields else SYSTEM_PROMPT
        payload, raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=selected_model,
            system_prompt=system_prompt,
            user_content=json.dumps({"email_body": str(email_body or "")}, separators=(",", ":"), ensure_ascii=True),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="profile-extraction LLM calls are disabled",
            warning_log_name="profile_extraction",
            retries=1,
            require_live_llm=False,
        )
        return validate_profile_extraction_output(payload)
    except (ProfileExtractionContractError, skill_runtime.SkillExecutionError) as exc:
        logger.error(
            "Profile extraction workflow failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(getattr(exc, "raw_response", "") or raw_content),
        )
        raise ProfileExtractionProposalError("profile_extraction_failed") from exc
    except Exception as exc:
        logger.error(
            "Profile extraction workflow failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(raw_content),
        )
        raise ProfileExtractionProposalError("profile_extraction_failed") from exc
