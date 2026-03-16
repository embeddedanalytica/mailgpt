"""Runner for the response-generation workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import LANGUAGE_RENDER_MODEL
from skills.response_generation.errors import (
    ResponseGenerationContractError,
    ResponseGenerationProposalError,
)
from skills.response_generation.prompt import SYSTEM_PROMPT
from skills.response_generation.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.response_generation.validator import (
    validate_response_generation_brief,
    validate_response_generation_output,
)

logger = logging.getLogger(__name__)


class ResponseGenerationLLM:
    """Language LLM boundary for athlete-facing final email generation."""

    SYSTEM_PROMPT = SYSTEM_PROMPT

    @staticmethod
    def generate_final_email_response(
        response_brief: Dict[str, Any],
        *,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw_content = ""
        try:
            brief = validate_response_generation_brief(response_brief)
        except ResponseGenerationContractError as exc:
            raise ResponseGenerationProposalError(str(exc)) from exc

        try:
            selected_model = str(model_name or LANGUAGE_RENDER_MODEL).strip() or LANGUAGE_RENDER_MODEL
            payload, raw_content = skill_runtime.execute_json_schema(
                logger=logger,
                model_name=selected_model,
                system_prompt=SYSTEM_PROMPT,
                user_content=json.dumps(brief, separators=(",", ":"), ensure_ascii=True),
                schema_name=JSON_SCHEMA_NAME,
                schema=JSON_SCHEMA,
                disabled_message="live response-generation LLM calls are disabled",
                warning_log_name="response_generation",
                retries=1,
            )
            validated = validate_response_generation_output(payload)
            validated["model_name"] = selected_model
            return validated
        except ResponseGenerationContractError as exc:
            logger.error(
                "Response generation failed: %s (raw_response_preview=%s)",
                exc,
                skill_runtime.preview_text(raw_content),
            )
            raise ResponseGenerationProposalError("response generation failed") from exc
        except skill_runtime.SkillExecutionError as exc:
            logger.error(
                "Response generation failed: %s (raw_response_preview=%s)",
                exc,
                skill_runtime.preview_text(exc.raw_response or raw_content),
            )
            raise ResponseGenerationProposalError("response generation failed") from exc
        except Exception as exc:
            logger.error(
                "Response generation failed: %s (raw_response_preview=%s)",
                exc,
                skill_runtime.preview_text(raw_content),
            )
            raise ResponseGenerationProposalError("response generation failed") from exc


def run_response_generation_workflow(
    response_brief: Dict[str, Any],
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    brief = validate_response_generation_brief(response_brief)
    try:
        return ResponseGenerationLLM.generate_final_email_response(
            brief,
            model_name=model_name,
        )
    except ResponseGenerationProposalError:
        raise
