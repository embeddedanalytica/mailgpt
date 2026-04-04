"""Runner for the coaching-reasoning workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import LANGUAGE_RENDER_MODEL
from skills.coaching_reasoning.doctrine import build_doctrine_selection_trace, list_loaded_files
from skills.coaching_reasoning.errors import CoachingReasoningError
from skills.coaching_reasoning.prompt import build_system_prompt
from skills.coaching_reasoning.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.coaching_reasoning.validator import validate_coaching_directive

logger = logging.getLogger(__name__)


def _build_revision_request(
    response_brief: Dict[str, Any],
    payload: Dict[str, Any],
    *,
    reason: str,
) -> str:
    return (
        f"{json.dumps(response_brief, separators=(',', ':'), ensure_ascii=True)}\n\n"
        "Revision request:\n"
        f"- {reason}.\n"
        "- Keep the directive answer-first and stop after the decision plus minimal execution detail.\n"
        "- Limit content_plan to at most 2 items.\n\n"
        f"Previous draft:\n{json.dumps(payload, separators=(',', ':'), ensure_ascii=True)}"
    )


def run_coaching_reasoning_workflow(
    response_brief: Dict[str, Any],
    *,
    model_name: Optional[str] = None,
    continuity_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Run the coaching reasoning skill and return a validated directive with metadata.

    Args:
        response_brief: The response brief for the current turn.
        model_name: Optional model override.
        continuity_context: Optional continuity state context for prompt enrichment.

    Returns:
        {
            "directive": <validated CoachingDirective dict>,
            "doctrine_files_loaded": [str, ...],
            "continuity_recommendation": <validated recommendation dict or None>,
        }
    """
    raw_content = ""

    try:
        selected_model = str(model_name or LANGUAGE_RENDER_MODEL).strip() or LANGUAGE_RENDER_MODEL
        doctrine_trace = build_doctrine_selection_trace(response_brief)
        response_shape = doctrine_trace.get("response_shape")
        turn_purpose = doctrine_trace.get("turn_purpose")
        system_prompt = build_system_prompt(response_brief, continuity_context=continuity_context)
        user_content = json.dumps(response_brief, separators=(",", ":"), ensure_ascii=True)
        validated = None

        for attempt in range(2):
            payload, raw_content = skill_runtime.execute_json_schema(
                logger=logger,
                model_name=selected_model,
                system_prompt=system_prompt,
                user_content=user_content,
                schema_name=JSON_SCHEMA_NAME,
                schema=JSON_SCHEMA,
                disabled_message="live coaching-reasoning LLM calls are disabled",
                warning_log_name="coaching_reasoning",
                retries=1,
            )

            try:
                validated = validate_coaching_directive(
                    payload,
                    response_shape=response_shape,
                    turn_purpose=turn_purpose,
                )
                break
            except CoachingReasoningError as exc:
                if (
                    response_shape != "answer_first_then_stop"
                    or turn_purpose != "lightweight_answer"
                    or attempt == 1
                ):
                    raise
                logger.warning("coaching_reasoning retrying after structural validation failure: %s", exc)
                user_content = _build_revision_request(
                    response_brief,
                    payload,
                    reason=str(exc),
                )

        if validated is None:
            raise CoachingReasoningError("coaching reasoning failed")

        # Extract continuity_recommendation (may or may not be present)
        continuity_recommendation = validated.pop("continuity_recommendation", None)

        return {
            "directive": validated,
            "doctrine_files_loaded": list_loaded_files(response_brief),
            "doctrine_trace": doctrine_trace,
            "continuity_recommendation": continuity_recommendation,
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
