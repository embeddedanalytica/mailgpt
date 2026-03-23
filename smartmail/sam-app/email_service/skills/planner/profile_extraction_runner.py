"""Runner for profile-extraction workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import PROFILE_EXTRACTION_MODEL
from skills.planner.profile_extraction_prompt import SYSTEM_PROMPT, build_intake_aware_prompt
from skills.planner.profile_extraction_schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.planner.profile_extraction_validator import validate_profile_extraction_output

logger = logging.getLogger(__name__)


class ProfileExtractionProposalError(RuntimeError):
    """Raised when profile extraction generation fails."""


def run_profile_extraction_workflow(
    email_body: str,
    *,
    model_name: Optional[str] = None,
    missing_fields: Optional[list[str]] = None,
) -> Dict[str, Any]:
    selected_model = str(model_name or PROFILE_EXTRACTION_MODEL).strip() or PROFILE_EXTRACTION_MODEL
    system_prompt = build_intake_aware_prompt(missing_fields) if missing_fields else SYSTEM_PROMPT
    return skill_runtime.run_validated_json_schema_workflow(
        logger=logger,
        model_name=selected_model,
        system_prompt=system_prompt,
        user_content=json.dumps({"email_body": str(email_body or "")}, separators=(",", ":"), ensure_ascii=True),
        schema_name=JSON_SCHEMA_NAME,
        schema=JSON_SCHEMA,
        disabled_message="profile-extraction LLM calls are disabled",
        warning_log_name="profile_extraction",
        validate_payload=validate_profile_extraction_output,
        workflow_label="profile_extraction",
        proposal_error_factory=ProfileExtractionProposalError,
        retries=1,
        require_live_llm=False,
    )
