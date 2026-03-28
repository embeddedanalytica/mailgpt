"""Validation and deterministic fallback for planner contracts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from rule_engine import (
    ALLOWED_SESSION_TAGS,
    HARD_SESSION_TAGS,
    PHASES,
    PLAN_UPDATE_STATUSES,
    RISK_FLAGS,
    TRACKS,
    _RED_TIER_FLAGS,
    _days_available,
)
from skills.planner.errors import PlannerContractError, PlannerRepairError
from skills.planner.schema import ALLOWED_STRUCTURE_PREFERENCES


def _require_dict(value: Any, *, field_name: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise PlannerContractError(f"{field_name} must be a dict")
    return dict(value)


def _normalize_string_list(values: Any, *, field_name: str, lowercase: bool = False) -> List[str]:
    if not isinstance(values, list):
        raise PlannerContractError(f"{field_name} must be a list")
    normalized: List[str] = []
    for idx, item in enumerate(values):
        if not isinstance(item, str):
            raise PlannerContractError(f"{field_name}[{idx}] must be a string")
        token = item.strip()
        if not token:
            raise PlannerContractError(f"{field_name}[{idx}] must be a non-empty string")
        normalized.append(token.lower() if lowercase else token)
    return normalized


def validate_planner_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise PlannerContractError("planner_brief must be a dict")

    required_keys = {
        "phase",
        "risk_flag",
        "track",
        "plan_update_status",
        "hard_limits",
        "weekly_targets",
        "allowed_session_budget",
        "max_sessions_per_week",
        "track_specific_objective",
        "priority_sessions",
        "disallowed_patterns",
        "structure_preference",
        "messaging_guardrails",
        "fallback_skeleton",
    }
    optional_keys = {
        "continuity_context",
        "athlete_session_preferences",
    }
    allowed_keys = required_keys | optional_keys
    unknown_keys = sorted(set(payload.keys()) - allowed_keys)
    if unknown_keys:
        raise PlannerContractError(
            "planner_brief contains unknown keys: " + ", ".join(unknown_keys)
        )
    missing_keys = sorted(required_keys - set(payload.keys()))
    if missing_keys:
        raise PlannerContractError(
            "planner_brief is missing keys: " + ", ".join(missing_keys)
        )

    phase = str(payload.get("phase", "")).strip().lower()
    if phase not in PHASES:
        raise PlannerContractError(f"phase must be one of {sorted(PHASES)}")

    risk_flag = str(payload.get("risk_flag", "")).strip().lower()
    if risk_flag not in RISK_FLAGS:
        raise PlannerContractError(f"risk_flag must be one of {sorted(RISK_FLAGS)}")

    track = str(payload.get("track", "")).strip().lower()
    if track not in TRACKS:
        raise PlannerContractError(f"track must be one of {sorted(TRACKS)}")

    plan_update_status = str(payload.get("plan_update_status", "")).strip().lower()
    if plan_update_status not in PLAN_UPDATE_STATUSES:
        raise PlannerContractError(
            f"plan_update_status must be one of {sorted(PLAN_UPDATE_STATUSES)}"
        )

    hard_limits = _require_dict(payload.get("hard_limits"), field_name="hard_limits")
    weekly_targets = _require_dict(payload.get("weekly_targets"), field_name="weekly_targets")
    messaging_guardrails = _require_dict(
        payload.get("messaging_guardrails"),
        field_name="messaging_guardrails",
    )

    allowed_session_budget = payload.get("allowed_session_budget")
    if not isinstance(allowed_session_budget, int) or allowed_session_budget < 1:
        raise PlannerContractError("allowed_session_budget must be a positive int")

    max_sessions_per_week = payload.get("max_sessions_per_week")
    if not isinstance(max_sessions_per_week, int) or max_sessions_per_week < 1:
        raise PlannerContractError("max_sessions_per_week must be a positive int")

    track_specific_objective = str(payload.get("track_specific_objective", "")).strip()
    if not track_specific_objective:
        raise PlannerContractError("track_specific_objective must be a non-empty string")

    priority_sessions = _normalize_string_list(
        payload.get("priority_sessions"),
        field_name="priority_sessions",
    )
    disallowed_patterns = _normalize_string_list(
        payload.get("disallowed_patterns"),
        field_name="disallowed_patterns",
        lowercase=True,
    )
    structure_preference = str(payload.get("structure_preference", "")).strip().lower()
    if structure_preference not in ALLOWED_STRUCTURE_PREFERENCES:
        raise PlannerContractError(
            f"structure_preference must be one of {sorted(ALLOWED_STRUCTURE_PREFERENCES)}"
        )
    fallback_skeleton = _normalize_string_list(
        payload.get("fallback_skeleton"),
        field_name="fallback_skeleton",
        lowercase=True,
    )
    for idx, token in enumerate(fallback_skeleton):
        if token not in ALLOWED_SESSION_TAGS:
            raise PlannerContractError(
                f"fallback_skeleton[{idx}] must be one of {sorted(ALLOWED_SESSION_TAGS)}"
            )

    result = {
        "phase": phase,
        "risk_flag": risk_flag,
        "track": track,
        "plan_update_status": plan_update_status,
        "hard_limits": hard_limits,
        "weekly_targets": weekly_targets,
        "allowed_session_budget": allowed_session_budget,
        "max_sessions_per_week": max_sessions_per_week,
        "track_specific_objective": track_specific_objective,
        "priority_sessions": priority_sessions,
        "disallowed_patterns": disallowed_patterns,
        "structure_preference": structure_preference,
        "messaging_guardrails": messaging_guardrails,
        "fallback_skeleton": fallback_skeleton,
    }
    if "continuity_context" in payload:
        result["continuity_context"] = payload["continuity_context"]
    if "athlete_session_preferences" in payload:
        result["athlete_session_preferences"] = _normalize_string_list(
            payload["athlete_session_preferences"],
            field_name="athlete_session_preferences",
        )
    return result


def build_planner_brief(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    decision_envelope: Dict[str, Any],
    rule_state: Dict[str, Any],
    continuity_context: Optional[Dict[str, Any]] = None,
    athlete_session_preferences: Optional[List[str]] = None,
) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise PlannerContractError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise PlannerContractError("checkin must be a dict")
    if not isinstance(decision_envelope, dict):
        raise PlannerContractError("decision_envelope must be a dict")
    if not isinstance(rule_state, dict):
        raise PlannerContractError("rule_state must be a dict")

    output_mode = str(
        checkin.get("structure_preference", profile.get("structure_preference", "structure"))
    ).strip().lower()
    if output_mode not in ALLOWED_STRUCTURE_PREFERENCES:
        output_mode = "structure"

    hard_limits = dict(decision_envelope.get("hard_limits", {}))
    weekly_targets = dict(decision_envelope.get("weekly_targets", {}))
    fallback_skeleton = [
        str(item).strip().lower()
        for item in decision_envelope.get("fallback_skeleton", [])
        if str(item).strip() and str(item).strip().lower() in ALLOWED_SESSION_TAGS
    ]
    if not fallback_skeleton:
        fallback_skeleton = ["easy_aerobic"]

    max_sessions = int(
        hard_limits.get("max_sessions_per_week", len(fallback_skeleton)) or len(fallback_skeleton)
    )
    max_sessions = max(1, max_sessions)
    allowed_session_budget = min(max_sessions, max(1, _days_available(checkin)))

    brief_payload: Dict[str, Any] = {
        "phase": str(decision_envelope.get("phase", "base")).strip().lower() or "base",
        "risk_flag": str(decision_envelope.get("risk_flag", "green")).strip().lower() or "green",
        "track": str(decision_envelope.get("track", "general_low_time")).strip().lower()
        or "general_low_time",
        "plan_update_status": str(decision_envelope.get("plan_update_status", "updated")).strip().lower()
        or "updated",
        "hard_limits": hard_limits,
        "weekly_targets": weekly_targets,
        "allowed_session_budget": allowed_session_budget,
        "max_sessions_per_week": max_sessions,
        "track_specific_objective": str(weekly_targets.get("track_objective", "")).strip(),
        "priority_sessions": [
            str(item)
            for item in weekly_targets.get("priority_sessions", [])
            if str(item).strip()
        ],
        "disallowed_patterns": [
            str(item).strip().lower()
            for item in weekly_targets.get("disallowed_patterns", [])
            if str(item).strip()
        ],
        "structure_preference": output_mode,
        "messaging_guardrails": dict(decision_envelope.get("messaging_guardrails", {})),
        "fallback_skeleton": fallback_skeleton,
    }
    if continuity_context is not None:
        brief_payload["continuity_context"] = continuity_context
    if athlete_session_preferences:
        brief_payload["athlete_session_preferences"] = list(athlete_session_preferences)
    return validate_planner_brief(brief_payload)


def validate_planner_response(payload: Dict[str, Any], *, model_name: str = "") -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise PlannerContractError("planner response must be a dict")

    allowed_keys = {
        "plan_proposal",
        "rationale",
        "non_binding_state_suggestions",
        "model_name",
    }
    unknown_keys = sorted(set(payload.keys()) - allowed_keys)
    if unknown_keys:
        raise PlannerContractError(
            "planner response contains unknown keys: " + ", ".join(unknown_keys)
        )
    missing_keys = sorted({"plan_proposal", "rationale", "non_binding_state_suggestions"} - set(payload.keys()))
    if missing_keys:
        raise PlannerContractError(
            "planner response is missing keys: " + ", ".join(missing_keys)
        )

    plan_proposal = _require_dict(payload.get("plan_proposal"), field_name="plan_proposal")
    allowed_plan_keys = {"weekly_skeleton"}
    unknown_plan_keys = sorted(set(plan_proposal.keys()) - allowed_plan_keys)
    if unknown_plan_keys:
        raise PlannerContractError(
            "plan_proposal contains unknown keys: " + ", ".join(unknown_plan_keys)
        )
    if "weekly_skeleton" not in plan_proposal:
        raise PlannerContractError("plan_proposal is missing keys: weekly_skeleton")

    weekly_skeleton = _normalize_string_list(
        plan_proposal.get("weekly_skeleton"),
        field_name="plan_proposal.weekly_skeleton",
        lowercase=True,
    )
    rationale = str(payload.get("rationale", "")).strip()
    suggestions = _normalize_string_list(
        payload.get("non_binding_state_suggestions"),
        field_name="non_binding_state_suggestions",
    )
    normalized_model_name = str(payload.get("model_name") or model_name or "").strip()

    return {
        "plan_proposal": {"weekly_skeleton": weekly_skeleton},
        "rationale": rationale,
        "non_binding_state_suggestions": suggestions,
        "model_name": normalized_model_name,
    }


def validate_planner_output(
    planner_brief: Dict[str, Any],
    plan_proposal: Dict[str, Any],
) -> Dict[str, Any]:
    brief = validate_planner_brief(planner_brief)
    proposal = _require_dict(plan_proposal, field_name="plan_proposal")
    allowed_plan_keys = {"weekly_skeleton"}
    unknown_plan_keys = sorted(set(proposal.keys()) - allowed_plan_keys)
    if unknown_plan_keys:
        raise PlannerContractError(
            "plan_proposal contains unknown keys: " + ", ".join(unknown_plan_keys)
        )

    proposed = [
        str(item).strip().lower()
        for item in proposal.get("weekly_skeleton", [])
        if str(item).strip()
    ]
    errors: List[str] = []
    if not proposed:
        errors.append("weekly_skeleton_missing")
    if any(token not in ALLOWED_SESSION_TAGS for token in proposed):
        errors.append("unknown_session_tag")

    max_sessions = max(1, int(brief.get("max_sessions_per_week", len(proposed) or 1) or 1))
    if len(proposed) > max_sessions:
        errors.append("session_count_exceeds_max")

    hard_budget = max(
        0,
        int(brief.get("hard_limits", {}).get("max_hard_sessions_per_week", 0) or 0),
    )
    hard_count = sum(1 for token in proposed if token in HARD_SESSION_TAGS)
    if hard_count > hard_budget:
        errors.append("hard_session_budget_exceeded")

    if brief["risk_flag"] in _RED_TIER_FLAGS and hard_count > 0:
        errors.append("red_tier_intensity_forbidden")

    disallowed_patterns = set(brief.get("disallowed_patterns", []))
    if "back_to_back_hard_days" in disallowed_patterns:
        for idx in range(1, len(proposed)):
            if proposed[idx] in HARD_SESSION_TAGS and proposed[idx - 1] in HARD_SESSION_TAGS:
                errors.append("back_to_back_hard_days")
                break
    if "make_up_intensity" in disallowed_patterns and "make_up_intensity" in proposed:
        errors.append("make_up_intensity_forbidden")

    return {
        "is_valid": not errors,
        "errors": errors,
        "normalized_plan_proposal": {
            "weekly_skeleton": proposed,
        },
    }


def repair_or_fallback_plan(
    validation_result: Dict[str, Any],
    planner_brief: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(validation_result, dict):
        raise PlannerRepairError("validation_result must be a dict")

    brief = validate_planner_brief(planner_brief)
    normalized = _require_dict(
        validation_result.get("normalized_plan_proposal", {}),
        field_name="normalized_plan_proposal",
    )
    proposed = [
        str(item).strip().lower()
        for item in normalized.get("weekly_skeleton", [])
        if str(item).strip()
    ]
    validation_errors = [
        str(item).strip().lower()
        for item in validation_result.get("errors", [])
        if str(item).strip()
    ]
    fallback_skeleton = list(brief["fallback_skeleton"]) or ["easy_aerobic"]

    if not proposed:
        return {
            "status": "repaired_or_fallback",
            "source": "deterministic_fallback",
            "weekly_skeleton": fallback_skeleton,
            "output_mode": brief["structure_preference"],
            "planner_rationale": "fallback_due_to_missing_plan",
            "planner_state_suggestions": [],
            "validation_errors": validation_errors,
            "failure_reason": "missing_plan",
            "model_name": "",
        }

    repaired = [token for token in proposed if token in ALLOWED_SESSION_TAGS]
    if not repaired:
        repaired = list(fallback_skeleton)

    max_sessions = max(1, int(brief.get("max_sessions_per_week", len(repaired)) or len(repaired)))
    repaired = repaired[:max_sessions]

    hard_budget = max(
        0,
        int(brief.get("hard_limits", {}).get("max_hard_sessions_per_week", 0) or 0),
    )
    hard_used = 0
    for idx, token in enumerate(list(repaired)):
        if token in HARD_SESSION_TAGS:
            if brief["risk_flag"] in _RED_TIER_FLAGS or hard_used >= hard_budget:
                repaired[idx] = "easy_aerobic"
            else:
                hard_used += 1

    disallowed_patterns = set(brief.get("disallowed_patterns", []))
    if "back_to_back_hard_days" in disallowed_patterns:
        for idx in range(1, len(repaired)):
            if repaired[idx] in HARD_SESSION_TAGS and repaired[idx - 1] in HARD_SESSION_TAGS:
                repaired[idx] = "easy_aerobic"

    revalidated = validate_planner_output(brief, {"weekly_skeleton": repaired})
    if not revalidated["is_valid"]:
        return {
            "status": "repaired_or_fallback",
            "source": "deterministic_fallback",
            "weekly_skeleton": fallback_skeleton,
            "output_mode": brief["structure_preference"],
            "planner_rationale": "fallback_due_to_unrepairable_plan",
            "planner_state_suggestions": [],
            "validation_errors": validation_errors,
            "failure_reason": "unrepairable_plan",
            "model_name": "",
        }
    return {
        "status": "repaired_or_fallback",
        "source": "repaired_planner_plan",
        "weekly_skeleton": repaired,
        "output_mode": brief["structure_preference"],
        "planner_rationale": "deterministic_repair_applied",
        "planner_state_suggestions": [],
        "validation_errors": validation_errors,
        "failure_reason": "validation_failed",
        "model_name": "",
    }
