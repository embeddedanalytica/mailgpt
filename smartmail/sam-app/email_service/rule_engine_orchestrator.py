"""Deterministic RE2 orchestrator that composes rule decisions."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

try:  # pragma: no cover - import style depends on runner context
    from .dynamodb_models import update_current_plan
    from .openai_responder import LanguageRenderError, LanguageReplyRenderer
    from .rule_engine import (
        RuleEngineContractError,
        RuleEngineOutput,
        _event_expected,
        _prior_phase_from_rule_state,
        apply_event_date_validation_guard,
        apply_phase_upgrade_hysteresis,
        apply_main_sport_deload_adjustments,
        build_weekly_skeleton,
        build_decision_envelope,
        compose_email_payload,
        detect_inconsistent_training,
        derive_phase,
        derive_risk,
        is_valid_phase,
        resolve_effective_performance_intent,
        resolve_main_sport_after_guardrails,
        route_today_action,
        select_track,
        should_trigger_main_sport_deload,
        should_switch_main_sport,
        validate_event_date,
        validate_rule_engine_output,
    )
    from .rule_engine_state import load_rule_state, update_rule_state
    from .skills.planner import build_planner_brief, run_planner_workflow
except ImportError:  # pragma: no cover
    from dynamodb_models import update_current_plan
    from openai_responder import LanguageRenderError, LanguageReplyRenderer
    from rule_engine import (
        RuleEngineContractError,
        RuleEngineOutput,
        _event_expected,
        _prior_phase_from_rule_state,
        apply_event_date_validation_guard,
        apply_phase_upgrade_hysteresis,
        apply_main_sport_deload_adjustments,
        build_weekly_skeleton,
        build_decision_envelope,
        compose_email_payload,
        detect_inconsistent_training,
        derive_phase,
        derive_risk,
        is_valid_phase,
        resolve_effective_performance_intent,
        resolve_main_sport_after_guardrails,
        route_today_action,
        select_track,
        should_trigger_main_sport_deload,
        should_switch_main_sport,
        validate_event_date,
        validate_rule_engine_output,
    )
    from rule_engine_state import load_rule_state, update_rule_state
    from skills.planner import build_planner_brief, run_planner_workflow


class RuleEngineOrchestratorError(ValueError):
    """Raised when orchestration inputs are invalid."""


def _map_phase_for_current_plan(phase: str) -> str:
    normalized = str(phase or "").strip().lower()
    if normalized == "peak_taper":
        return "peak"
    if normalized == "return_to_training":
        return "recovery"
    if normalized in {"base", "build", "recovery", "peak"}:
        return normalized
    return "unknown"


def _session_type_from_skeleton(weekly_skeleton: list[str]) -> str:
    if not weekly_skeleton:
        return "mobility"
    first = str(weekly_skeleton[0]).strip().lower()
    if first in {"quality", "intervals", "tempo", "threshold", "vo2", "race_sim", "hills_hard"}:
        return "hard"
    if first in {"strength", "mobility", "skills"}:
        return "strength"
    if first == "recovery":
        return "recovery"
    return "easy"


def _phase_history_from_rule_state(rule_state: Dict[str, Any]) -> list[str]:
    history = rule_state.get("phase_risk_time_last_6", [])
    phases: list[str] = []
    if not isinstance(history, list):
        return phases
    for item in history:
        if not isinstance(item, dict):
            continue
        phase = str(item.get("phase", "")).strip().lower()
        if is_valid_phase(phase):
            phases.append(phase)
    return phases


def _next_phase_upgrade_streak(
    phase_history: list[str],
    candidate_phase: str,
    stabilized_phase: str,
    risk_flag: str,
    prior_upgrade_streak: int,
) -> int:
    if not phase_history:
        return 0
    normalized_candidate = str(candidate_phase or "").strip().lower()
    normalized_stabilized = str(stabilized_phase or "").strip().lower()
    normalized_risk = str(risk_flag or "").strip().lower()
    if normalized_risk in {"red_a", "red_b"}:
        return 0
    last_phase = str(phase_history[-1]).strip().lower()
    if normalized_candidate not in {"base", "build", "peak_taper"}:
        return 0
    phase_rank = {"base": 0, "build": 1, "peak_taper": 2}
    if last_phase not in phase_rank:
        return 0
    if phase_rank[normalized_candidate] <= phase_rank[last_phase]:
        return 0
    if normalized_stabilized == normalized_candidate:
        return 0
    return max(1, int(prior_upgrade_streak) + 1)


def apply_rule_engine_plan_update(
    athlete_id: str,
    engine_output: Any,
    logical_request_id: str,
) -> Dict[str, Any]:
    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise RuleEngineOrchestratorError("athlete_id must be a non-empty string")
    if not isinstance(logical_request_id, str) or not logical_request_id.strip():
        raise RuleEngineOrchestratorError("logical_request_id must be a non-empty string")

    if isinstance(engine_output, RuleEngineOutput):
        payload = engine_output.to_dict()
    elif isinstance(engine_output, dict):
        payload = dict(engine_output)
    else:
        raise RuleEngineOrchestratorError("engine_output must be RuleEngineOutput or dict")

    validate_rule_engine_output(payload)

    plan_update_status = str(payload.get("plan_update_status", "")).strip().lower()
    if plan_update_status != "updated":
        return {"status": "skipped", "plan_version": None, "error_code": None}

    weekly_skeleton = [str(item) for item in payload.get("weekly_skeleton", [])]
    updates = {
        "current_phase": _map_phase_for_current_plan(payload.get("phase")),
        "current_focus": str(payload.get("track", "")).strip() or "Build consistency",
        "next_recommended_session": {
            "date": str(payload.get("week_start", "TBD")).strip() or "TBD",
            "type": _session_type_from_skeleton(weekly_skeleton),
            "target": weekly_skeleton[0] if weekly_skeleton else "short mobility or recovery",
        },
        "plan_status": "active" if payload.get("risk_flag") == "green" else "adjusting",
        "weekly_skeleton": weekly_skeleton,
        "plan_adjustments": [str(item) for item in payload.get("adjustments", [])],
        "plan_update_status": payload.get("plan_update_status"),
    }
    return update_current_plan(
        athlete_id,
        updates,
        logical_request_id=logical_request_id,
        rationale="rule_engine_re2_update",
        changes_from_previous=["weekly_skeleton_refreshed", f"track={payload.get('track', '')}"],
    )


def run_rule_engine_for_week(
    athlete_id: str,
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    today_date: date,
    *,
    persist_state: bool = True,
) -> RuleEngineOutput:
    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise RuleEngineOrchestratorError("athlete_id must be a non-empty string")
    if not isinstance(profile, dict):
        raise RuleEngineOrchestratorError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineOrchestratorError("checkin must be a dict")
    if not isinstance(today_date, date):
        raise RuleEngineOrchestratorError("today_date must be a datetime.date")
    if not isinstance(persist_state, bool):
        raise RuleEngineOrchestratorError("persist_state must be a bool")

    rule_state = load_rule_state(athlete_id)
    phase_history = _phase_history_from_rule_state(rule_state)
    prior_phase = _prior_phase_from_rule_state(rule_state)
    prior_upgrade_streak = int(rule_state.get("phase_upgrade_streak", 0) or 0)
    effective_performance_intent = resolve_effective_performance_intent(profile, checkin)
    risk_flag = derive_risk(profile, checkin, rule_state)
    candidate_phase = derive_phase(
        profile,
        checkin,
        today_date,
        rule_state,
        risk_flag=risk_flag,
        effective_performance_intent=effective_performance_intent,
    )

    plan_update_status = "updated"
    if _event_expected(profile, checkin):
        validation_status = validate_event_date(checkin, today_date)
        candidate_phase, plan_update_status = apply_event_date_validation_guard(
            validation_status=validation_status,
            candidate_phase=candidate_phase,
            prior_phase=prior_phase,
            candidate_plan_update_status=plan_update_status,
        )

    inconsistent_training = detect_inconsistent_training(
        phase_history,
        candidate_phase,
        risk_flag,
    )
    phase = apply_phase_upgrade_hysteresis(
        phase_history,
        candidate_phase,
        risk_flag,
        prior_upgrade_streak=prior_upgrade_streak,
    )
    phase_upgrade_streak = _next_phase_upgrade_streak(
        phase_history,
        candidate_phase,
        phase,
        risk_flag,
        prior_upgrade_streak,
    )

    effective_profile = dict(profile)
    should_switch = should_switch_main_sport(profile, checkin, rule_state)
    resolved_main_sport = resolve_main_sport_after_guardrails(profile, checkin, rule_state, risk_flag)
    if resolved_main_sport:
        effective_profile["main_sport_current"] = resolved_main_sport

    track = select_track(effective_profile, phase, risk_flag)
    skeleton_data = build_weekly_skeleton(
        effective_profile,
        checkin,
        track,
        phase,
        risk_flag,
        effective_performance_intent,
        rule_state,
    )
    weekly_skeleton = list(skeleton_data["weekly_skeleton"])
    adjustments = list(skeleton_data["adjustments"])

    if plan_update_status == "updated":
        plan_update_status = skeleton_data["plan_update_status"]

    deload_applied = False
    if track in {"main_base", "main_build", "main_peak_taper"} and should_trigger_main_sport_deload(
        phase,
        rule_state,
        risk_flag,
    ):
        weekly_skeleton = apply_main_sport_deload_adjustments(weekly_skeleton)
        deload_applied = True

    infeasible = skeleton_data["infeasible"]
    if infeasible:
        plan_update_status = skeleton_data["plan_update_status"]
        weekly_skeleton = []
        adjustments = list(skeleton_data["adjustments"])

    routed_plan = route_today_action(
        checkin,
        risk_flag,
        track,
        weekly_skeleton,
    )
    today_action = str(routed_plan["today_action"])
    adjustments = list(dict.fromkeys(adjustments + list(routed_plan["adjustments"])))
    if inconsistent_training and phase != candidate_phase:
        adjustments.append("phase_upgrade_requires_two_consecutive_qualifying_checkins")

    decision_envelope = build_decision_envelope(
        effective_profile,
        checkin,
        phase,
        risk_flag,
        track,
        effective_performance_intent,
        rule_state,
        fallback_skeleton=weekly_skeleton,
        adjustments=adjustments,
        plan_update_status=plan_update_status,
        today_action=today_action,
        routing_context=routed_plan["routing_context"],
    )
    planner_brief = build_planner_brief(
        effective_profile,
        checkin,
        decision_envelope,
        rule_state,
    )
    final_plan = {
        "source": "deterministic_fallback",
        "weekly_skeleton": list(decision_envelope.get("fallback_skeleton", weekly_skeleton)),
        "output_mode": planner_brief.get("structure_preference", "structure"),
        "planner_rationale": "deterministic_fallback_default",
        "planner_state_suggestions": [],
    }
    if (
        plan_update_status not in {"unchanged_clarification_needed", "unchanged_infeasible_week"}
        and not deload_applied
    ):
        final_plan = run_planner_workflow(planner_brief)

    final_plan.update(
        {
            "today_action": today_action,
            "adjustments": list(adjustments),
            "routing_context": dict(routed_plan["routing_context"]),
            "plan_update_status": plan_update_status,
        }
    )
    weekly_skeleton = [str(item) for item in final_plan.get("weekly_skeleton", [])]

    deterministic_payload = compose_email_payload(
        effective_profile,
        checkin,
        final_plan,
        decision_envelope,
    )
    next_email_payload = dict(deterministic_payload)
    if plan_update_status == "updated":
        try:
            rendered_payload = LanguageReplyRenderer.render_reply(final_plan, decision_envelope)
            validate_rule_engine_output(
                {
                    "classification_label": "compatibility_check",
                    "track": track,
                    "phase": phase,
                    "risk_flag": risk_flag,
                    "weekly_skeleton": weekly_skeleton,
                    "today_action": today_action,
                    "plan_update_status": plan_update_status,
                    "adjustments": adjustments,
                    "next_email_payload": rendered_payload,
                }
            )
            next_email_payload = dict(rendered_payload)
        except (LanguageRenderError, RuleEngineContractError):
            next_email_payload = dict(deterministic_payload)

    output_payload = {
        "classification_label": "deterministic_re4",
        "track": track,
        "phase": phase,
        "risk_flag": risk_flag,
        "weekly_skeleton": weekly_skeleton,
        "today_action": today_action,
        "plan_update_status": plan_update_status,
        "adjustments": adjustments,
        "next_email_payload": next_email_payload,
    }
    validate_rule_engine_output(output_payload)

    prior_weeks_since_deload = int(rule_state.get("weeks_since_deload", 0) or 0)
    next_weeks_since_deload = 0 if deload_applied else max(0, prior_weeks_since_deload + 1)
    if persist_state:
        update_rule_state(
            athlete_id,
            {
                **checkin,
                "time_bucket": checkin.get("time_bucket", profile.get("time_bucket", "")),
            },
            {
                "phase": phase,
                "risk_flag": risk_flag,
                "weeks_since_deload": next_weeks_since_deload,
                "phase_upgrade_streak": phase_upgrade_streak,
                "main_sport_switched": bool(
                    should_switch and resolved_main_sport and resolved_main_sport != profile.get("main_sport_current")
                ),
                "previous_main_sport": profile.get("main_sport_current"),
            },
        )

    return RuleEngineOutput.from_dict(output_payload)
