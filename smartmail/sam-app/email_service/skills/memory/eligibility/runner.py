"""Runner for the memory refresh eligibility workflow."""

import json
import logging
from typing import Any, Dict

import skills.runtime as skill_runtime
from config import OPENAI_CLASSIFICATION_MODEL
from skills.memory.eligibility.errors import MemoryRefreshEligibilityError
from skills.memory.eligibility.prompt import SYSTEM_PROMPT
from skills.memory.eligibility.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.memory.eligibility.validator import validate_eligibility_payload

logger = logging.getLogger(__name__)


def _fallback(reason_resolution: str) -> Dict[str, Any]:
    return {
        "should_refresh": False,
        "reason": "no_meaningful_change",
        "model_name": OPENAI_CLASSIFICATION_MODEL,
        "resolution_source": "fallback",
        "reason_resolution": reason_resolution,
    }


def run_memory_refresh_eligibility(interaction_context: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(interaction_context, dict):
        raise MemoryRefreshEligibilityError("interaction_context must be a dict")

    if not skill_runtime.live_llm_enabled():
        return _fallback("live_llm_disabled")

    try:
        payload, _raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=OPENAI_CLASSIFICATION_MODEL,
            system_prompt=SYSTEM_PROMPT,
            user_content=json.dumps(interaction_context, separators=(",", ":"), ensure_ascii=True),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live memory-refresh eligibility LLM calls are disabled",
            warning_log_name="memory_refresh_eligibility",
            retries=1,
        )
        validated = validate_eligibility_payload(payload)
        logger.info(
            "memory_refresh_eligibility should_refresh=%s reason=%s model=%s",
            validated["should_refresh"],
            validated["reason"],
            validated["model_name"],
        )
        return validated
    except MemoryRefreshEligibilityError:
        return _fallback("single_prompt_validation_failed")
    except skill_runtime.SkillExecutionError as e:
        if e.code == "invalid_json_response":
            return _fallback("single_prompt_validation_failed")
        logger.error("Error extracting memory refresh eligibility: %s", e)
        return _fallback("llm_memory_refresh_eligibility_failed")
    except Exception as e:
        logger.error("Error extracting memory refresh eligibility: %s", e)
        return _fallback("llm_memory_refresh_eligibility_failed")
