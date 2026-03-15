"""Planner workflow contracts and JSON schema."""

from typing import Any, Dict, List, TypedDict


ALLOWED_STRUCTURE_PREFERENCES = {"structure", "flexibility", "mixed"}
ALLOWED_FINAL_PLAN_STATUSES = {"accepted", "repaired_or_fallback"}


class PlannerBrief(TypedDict):
    phase: str
    risk_flag: str
    track: str
    plan_update_status: str
    hard_limits: Dict[str, Any]
    weekly_targets: Dict[str, Any]
    allowed_session_budget: int
    max_sessions_per_week: int
    track_specific_objective: str
    priority_sessions: List[str]
    disallowed_patterns: List[str]
    structure_preference: str
    messaging_guardrails: Dict[str, Any]
    fallback_skeleton: List[str]


class PlannerProposal(TypedDict):
    weekly_skeleton: List[str]


class PlannerRawOutput(TypedDict, total=False):
    plan_proposal: PlannerProposal
    rationale: str
    non_binding_state_suggestions: List[str]
    model_name: str


class FinalPlannerResult(TypedDict):
    status: str
    source: str
    weekly_skeleton: List[str]
    output_mode: str
    planner_rationale: str
    planner_state_suggestions: List[str]
    validation_errors: List[str]
    failure_reason: str
    model_name: str


JSON_SCHEMA_NAME = "planner_proposal"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["plan_proposal", "rationale", "non_binding_state_suggestions"],
    "properties": {
        "plan_proposal": {
            "type": "object",
            "additionalProperties": False,
            "required": ["weekly_skeleton"],
            "properties": {
                "weekly_skeleton": {
                    "type": "array",
                    "items": {"type": "string", "minLength": 1},
                }
            },
        },
        "rationale": {"type": "string"},
        "non_binding_state_suggestions": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
        },
    },
}
