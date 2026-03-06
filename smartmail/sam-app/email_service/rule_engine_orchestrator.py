"""Deterministic RE2 orchestrator that composes rule decisions."""

from __future__ import annotations

from datetime import date
from typing import Any, Dict

try:  # pragma: no cover - import style depends on runner context
    from .dynamodb_models import update_current_plan
    from .rule_engine import (
        RuleEngineOutput,
        _event_expected,
        _prior_phase_from_rule_state,
        apply_event_date_validation_guard,
        apply_main_sport_deload_adjustments,
        build_weekly_skeleton,
        derive_phase,
        derive_risk,
        resolve_effective_performance_intent,
        resolve_main_sport_after_guardrails,
        select_track,
        should_trigger_main_sport_deload,
        should_switch_main_sport,
        validate_event_date,
        validate_rule_engine_output,
    )
    from .rule_engine_state import load_rule_state, update_rule_state
except ImportError:  # pragma: no cover
    from dynamodb_models import update_current_plan
    from rule_engine import (
        RuleEngineOutput,
        _event_expected,
        _prior_phase_from_rule_state,
        apply_event_date_validation_guard,
        apply_main_sport_deload_adjustments,
        build_weekly_skeleton,
        derive_phase,
        derive_risk,
        resolve_effective_performance_intent,
        resolve_main_sport_after_guardrails,
        select_track,
        should_trigger_main_sport_deload,
        should_switch_main_sport,
        validate_event_date,
        validate_rule_engine_output,
    )
    from rule_engine_state import load_rule_state, update_rule_state


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


def _fallback_today_action(risk_flag: str, infeasible: bool) -> str:
    if infeasible:
        return "infeasible_week_keep_plan_unchanged"
    if risk_flag == "red_b":
        return "stop_intensity_consult_clinician"
    if risk_flag == "red_a":
        return "stop_intensity_switch_to_easy_cross_train"
    if risk_flag == "yellow":
        return "do_planned_but_conservative"
    return "proceed_as_planned"


def _compose_next_email_payload(
    *,
    risk_flag: str,
    track: str,
    weekly_skeleton: list[str],
    adjustments: list[str],
    plan_update_status: str,
) -> Dict[str, Any]:
    sessions = [f"session_{idx + 1}: {token}" for idx, token in enumerate(weekly_skeleton)]
    if plan_update_status == "unchanged_infeasible_week":
        sessions = ["Optional short mobility/recovery touch only."]

    safety_focus = track == "return_or_risk_managed"
    summary = "Safety-managed week: protect consistency and reduce load." if safety_focus else "Deterministic weekly skeleton generated."
    disclaimer_short = ""
    if risk_flag == "red_b":
        disclaimer_short = "Please stop training and consult a clinician/physio."

    return {
        "subject_hint": "This week: safety-first consistency" if safety_focus else "This week: execute the plan",
        "summary": summary,
        "sessions": sessions,
        "plan_focus_line": "Prioritize safety and consistency." if safety_focus else "Progress with controlled load.",
        "technique_cue": "Keep effort smooth and controlled.",
        "recovery_target": "Prioritize sleep and low-stress recovery routines.",
        "if_then_rules": [
            "If pain worsens, stop intensity and report immediately.",
            "If schedule collapses, keep only anchor sessions.",
        ],
        "disclaimer_short": disclaimer_short,
        "safety_note": "No hard sessions when risk is red-tier.",
    }


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
    effective_performance_intent = resolve_effective_performance_intent(profile, checkin)
    risk_flag = derive_risk(profile, checkin, rule_state)
    phase = derive_phase(
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
        phase, plan_update_status = apply_event_date_validation_guard(
            validation_status=validation_status,
            candidate_phase=phase,
            prior_phase=_prior_phase_from_rule_state(rule_state),
            candidate_plan_update_status=plan_update_status,
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

    today_action = _fallback_today_action(risk_flag, infeasible)
    next_email_payload = _compose_next_email_payload(
        risk_flag=risk_flag,
        track=track,
        weekly_skeleton=weekly_skeleton,
        adjustments=adjustments,
        plan_update_status=plan_update_status,
    )

    output_payload = {
        "classification_label": "deterministic_re2",
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
                "main_sport_switched": bool(
                    should_switch and resolved_main_sport and resolved_main_sport != profile.get("main_sport_current")
                ),
                "previous_main_sport": profile.get("main_sport_current"),
            },
        )

    return RuleEngineOutput.from_dict(output_payload)
