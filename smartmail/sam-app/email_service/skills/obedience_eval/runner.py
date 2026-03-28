"""Obedience evaluation skill runner."""

import json
import logging
from typing import Any, Dict, Optional

from config import OPENAI_CLASSIFICATION_MODEL
from skills import runtime as skill_runtime
from skills.obedience_eval.errors import ObedienceEvalError
from skills.obedience_eval.prompt import build_system_prompt
from skills.obedience_eval.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.obedience_eval.validator import validate_obedience_eval

logger = logging.getLogger(__name__)


def run_obedience_eval(
    email_body: str,
    directive: Dict[str, Any],
    continuity_context: Optional[Dict[str, Any]] = None,
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Evaluate an email for obedience violations and return corrections if needed.

    Returns a dict with keys: passed, violations, corrected_email_body, reasoning.
    Raises ObedienceEvalError if the workflow fails.
    """
    raw_content = ""
    try:
        selected_model = (
            str(model_name or OPENAI_CLASSIFICATION_MODEL).strip()
            or OPENAI_CLASSIFICATION_MODEL
        )

        system_prompt = build_system_prompt(directive, continuity_context)

        user_content = json.dumps(
            {
                "email_body": email_body,
                "directive": directive,
                "continuity_context": continuity_context,
            },
            separators=(",", ":"),
            ensure_ascii=True,
        )

        payload, raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=selected_model,
            system_prompt=system_prompt,
            user_content=user_content,
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live obedience-eval LLM calls are disabled",
            warning_log_name="obedience_eval",
            retries=1,
        )

        return validate_obedience_eval(payload)

    except ObedienceEvalError:
        raise
    except skill_runtime.SkillExecutionError as exc:
        logger.error(
            "Obedience eval failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(exc.raw_response or raw_content),
        )
        raise ObedienceEvalError("obedience eval failed") from exc
    except Exception as exc:
        logger.error(
            "Obedience eval failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(raw_content),
        )
        raise ObedienceEvalError("obedience eval failed") from exc
