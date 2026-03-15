"""Runner for the planner workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import PLANNING_LLM_MODEL
from skills.planner.errors import PlannerContractError, PlannerProposalError
from skills.planner.prompt import SYSTEM_PROMPT
from skills.planner.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.planner.validator import (
    repair_or_fallback_plan,
    validate_planner_brief,
    validate_planner_output,
    validate_planner_response,
)

logger = logging.getLogger(__name__)


class PlanningLLM:
    """Planning LLM boundary for RE4."""

    SYSTEM_PROMPT = SYSTEM_PROMPT

    @staticmethod
    def propose_plan(
        planner_brief: Dict[str, Any],
        *,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        raw_content = ""
        try:
            brief = validate_planner_brief(planner_brief)
        except PlannerContractError as exc:
            raise PlannerProposalError(str(exc)) from exc
        try:
            selected_model = str(model_name or PLANNING_LLM_MODEL).strip() or PLANNING_LLM_MODEL
            payload, raw_content = skill_runtime.execute_json_schema(
                logger=logger,
                model_name=selected_model,
                system_prompt=SYSTEM_PROMPT,
                user_content=json.dumps(brief, separators=(",", ":"), ensure_ascii=True),
                schema_name=JSON_SCHEMA_NAME,
                schema=JSON_SCHEMA,
                disabled_message="live planner LLM calls are disabled",
                warning_log_name="planner_generation",
                retries=1,
            )
            return validate_planner_response(payload, model_name=selected_model)
        except PlannerContractError as exc:
            logger.error(
                "Planning LLM proposal failed: %s (raw_response_preview=%s)",
                exc,
                skill_runtime.preview_text(raw_content),
            )
            raise PlannerProposalError("planning llm proposal failed") from exc
        except skill_runtime.SkillExecutionError as exc:
            logger.error(
                "Planning LLM proposal failed: %s (raw_response_preview=%s)",
                exc,
                skill_runtime.preview_text(exc.raw_response or raw_content),
            )
            raise PlannerProposalError("planning llm proposal failed") from exc
        except Exception as exc:
            logger.error(
                "Planning LLM proposal failed: %s (raw_response_preview=%s)",
                exc,
                skill_runtime.preview_text(raw_content),
            )
            raise PlannerProposalError("planning llm proposal failed") from exc


def run_planner_workflow(
    planner_brief: Dict[str, Any],
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    brief = validate_planner_brief(planner_brief)
    try:
        planner_response = PlanningLLM.propose_plan(brief, model_name=model_name)
        plan_proposal = dict(planner_response.get("plan_proposal", {}))
        validation_result = validate_planner_output(brief, plan_proposal)
        if validation_result["is_valid"]:
            return {
                "status": "accepted",
                "source": "validated_planner_plan",
                "weekly_skeleton": list(
                    validation_result["normalized_plan_proposal"].get("weekly_skeleton", [])
                ),
                "output_mode": brief.get("structure_preference", "structure"),
                "planner_rationale": str(planner_response.get("rationale", "")).strip(),
                "planner_state_suggestions": list(
                    planner_response.get("non_binding_state_suggestions", [])
                ),
                "validation_errors": [],
                "failure_reason": "",
                "model_name": str(planner_response.get("model_name", "")).strip(),
            }

        repaired = repair_or_fallback_plan(validation_result, brief)
        repaired["planner_state_suggestions"] = list(
            planner_response.get("non_binding_state_suggestions", [])
        )
        repaired["model_name"] = str(planner_response.get("model_name", "")).strip()
        return repaired
    except PlannerProposalError:
        fallback_skeleton = list(brief.get("fallback_skeleton", [])) or ["easy_aerobic"]
        return {
            "status": "repaired_or_fallback",
            "source": "deterministic_fallback",
            "weekly_skeleton": fallback_skeleton,
            "output_mode": brief.get("structure_preference", "structure"),
            "planner_rationale": "deterministic_fallback_planner_unavailable",
            "planner_state_suggestions": [],
            "validation_errors": [],
            "failure_reason": "planner_unavailable",
            "model_name": str(model_name or "").strip(),
        }
