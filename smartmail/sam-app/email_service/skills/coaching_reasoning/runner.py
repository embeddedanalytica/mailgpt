"""Runner for the coaching-reasoning workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import LANGUAGE_RENDER_MODEL
from skills.coaching_reasoning.doctrine import list_loaded_files
from skills.coaching_reasoning.errors import CoachingReasoningError
from skills.coaching_reasoning.prompt import build_system_prompt
from skills.coaching_reasoning.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.coaching_reasoning.validator import validate_coaching_directive

logger = logging.getLogger(__name__)


def run_coaching_reasoning_workflow(
    response_brief: Dict[str, Any],
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    """Run the coaching reasoning skill and return a validated directive with metadata.

    Returns:
        {"directive": <validated CoachingDirective dict>, "doctrine_files_loaded": [str, ...]}
    """
    raw_content = ""

    try:
        selected_model = str(model_name or LANGUAGE_RENDER_MODEL).strip() or LANGUAGE_RENDER_MODEL
        system_prompt = build_system_prompt(response_brief)

        payload, raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=selected_model,
            system_prompt=system_prompt,
            user_content=json.dumps(response_brief, separators=(",", ":"), ensure_ascii=True),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="live coaching-reasoning LLM calls are disabled",
            warning_log_name="coaching_reasoning",
            retries=1,
        )

        directive = validate_coaching_directive(payload)
        return {
            "directive": directive,
            "doctrine_files_loaded": list_loaded_files(response_brief),
        }

    except CoachingReasoningError:
        raise
    except skill_runtime.SkillExecutionError as exc:
        logger.error(
            "Coaching reasoning failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(exc.raw_response or raw_content),
        )
        raise CoachingReasoningError("coaching reasoning failed") from exc
    except Exception as exc:
        logger.error(
            "Coaching reasoning failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(raw_content),
        )
        raise CoachingReasoningError("coaching reasoning failed") from exc


def _extract_sport(brief: Dict[str, Any]) -> Optional[str]:
    """Pull the athlete's sport from the brief, if available."""
    athlete_ctx = brief.get("athlete_context")
    if isinstance(athlete_ctx, dict):
        return athlete_ctx.get("primary_sport")
    return None
