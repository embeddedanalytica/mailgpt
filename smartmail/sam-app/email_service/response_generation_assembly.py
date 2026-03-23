"""Assembly helpers for bounded response-generation inputs."""

from __future__ import annotations

import time as _time
from typing import Any, Dict, Optional

from athlete_memory_contract import (
    AthleteMemoryContractError,
    ContinuitySummary,
    validate_memory_notes,
)
from response_generation_contract import ResponseBrief, normalize_reply_mode
from rule_engine import RuleEngineContractError, validate_rule_engine_output
from skills.response_generation import build_clarification_questions


def _string_field(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _validated_engine_output(
    rule_engine_decision: Optional[Dict[str, Any]],
) -> Optional[Dict[str, Any]]:
    if not isinstance(rule_engine_decision, dict):
        return None
    engine_output = rule_engine_decision.get("engine_output")
    if not isinstance(engine_output, dict):
        return None

    try:
        validate_rule_engine_output(engine_output)
    except RuleEngineContractError:
        return None
    return engine_output


# Fact type ordering for deterministic salience
_FACT_TYPE_ORDER = {"goal": 0, "constraint": 1, "schedule": 2, "preference": 3, "other": 4}


def _shape_memory_salience_v4(
    memory_notes: list[dict[str, Any]],
    continuity_summary: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Shapes AM2 durable facts into salience categories for the response LLM.

    Deterministic ordering: goal before constraint within priority tier,
    then by most recent last_confirmed_at. Schedule next. Preference/other last.
    """
    # Sort all facts by (type_order, -last_confirmed_at) for stable ordering
    def _sort_key(f: dict[str, Any]) -> tuple:
        type_order = _FACT_TYPE_ORDER.get(f.get("fact_type", "other"), 4)
        last_confirmed = f.get("last_confirmed_at", 0)
        return (type_order, -last_confirmed)

    sorted_facts = sorted(memory_notes, key=_sort_key)

    priority_facts: list[str] = []  # goal + constraint
    structure_facts: list[str] = []  # schedule
    context_facts: list[str] = []  # preference + other

    for fact in sorted_facts:
        summary = _string_field(fact.get("summary"))
        if not summary:
            continue
        fact_type = fact.get("fact_type", "other")
        if fact_type in ("goal", "constraint"):
            priority_facts.append(summary)
        elif fact_type == "schedule":
            structure_facts.append(summary)
        else:
            context_facts.append(summary)

    continuity_focus = None
    if isinstance(continuity_summary, dict):
        continuity_focus = _string_field(continuity_summary.get("summary"))

    return {
        "priority_facts": priority_facts,
        "structure_facts": structure_facts,
        "context_facts": context_facts,
        "continuity_focus": continuity_focus,
    }


def _constraint_summaries(profile_after: Dict[str, Any]) -> Optional[str]:
    """Build a combined constraint summary from injury_status, injury_constraints, and general constraints."""
    parts: list[str] = []

    # injury_status gate: if athlete confirmed no injuries, note it explicitly
    injury_status = profile_after.get("injury_status")
    if isinstance(injury_status, dict) and injury_status.get("has_injuries") is False:
        parts.append("No current injuries or physical limitations reported")

    injury_constraints = profile_after.get("injury_constraints")
    if isinstance(injury_constraints, list):
        for item in injury_constraints:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary", "")).strip()
            if summary:
                parts.append(summary)

    constraints = profile_after.get("constraints")
    if isinstance(constraints, list):
        for item in constraints:
            if isinstance(item, dict):
                summary = str(item.get("summary", "")).strip()
                if summary:
                    parts.append(summary)

    return "; ".join(parts) if parts else None


def _missing_injury_only(missing_profile_fields: list[str]) -> bool:
    return set(missing_profile_fields) == {"injury_status"}


def build_response_brief(
    *,
    athlete_id: str,
    reply_kind: str,
    inbound_subject: Optional[str],
    inbound_body: Optional[str] = None,
    selected_model_name: Optional[str],
    profile_after: Dict[str, Any],
    missing_profile_fields: list[str],
    plan_summary: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    memory_context: Optional[Dict[str, Any]],
    connect_strava_link: Optional[str] = None,
    intake_completed_this_turn: bool = False,
    # Legacy kwargs (ignored, kept for backward compat during transition)
    pre_reply_refresh_attempted: bool = False,
    post_reply_refresh_eligible: bool = False,
) -> ResponseBrief:
    del athlete_id  # reserved for future assembly expansion

    reply_mode = normalize_reply_mode(reply_kind)
    validated_engine_output = _validated_engine_output(rule_engine_decision)
    athlete_context: Dict[str, Any] = {}
    goal_summary = _string_field(profile_after.get("primary_goal"))
    if goal_summary:
        athlete_context["goal_summary"] = goal_summary
    experience_level = _string_field(profile_after.get("experience_level"))
    if experience_level:
        athlete_context["experience_level"] = experience_level
    structure_preference = _string_field(profile_after.get("structure_preference"))
    if structure_preference:
        athlete_context["structure_preference"] = structure_preference
    constraints_summary = _constraint_summaries(profile_after)
    if constraints_summary:
        athlete_context["constraints_summary"] = constraints_summary
    primary_sport = _string_field(profile_after.get("main_sport_current"))
    if primary_sport:
        athlete_context["primary_sport"] = primary_sport

    decision_context: Dict[str, Any] = {}
    injury_followup_only = (
        reply_mode == "lightweight_non_planning" and _missing_injury_only(missing_profile_fields)
    )
    if reply_mode == "intake" and missing_profile_fields:
        decision_context["missing_profile_fields"] = list(missing_profile_fields)
        decision_context["clarification_needed"] = True
    else:
        clarification_needed = reply_mode == "clarification" or (
            bool(missing_profile_fields) and not injury_followup_only
        )
        if isinstance(rule_engine_decision, dict):
            clarification_needed = clarification_needed or bool(
                rule_engine_decision.get("clarification_needed")
            )
        if clarification_needed:
            decision_context["clarification_needed"] = True
        if missing_profile_fields:
            clarification_fields = (
                ["injury_status"] if injury_followup_only else missing_profile_fields
            )
            decision_context["clarification_questions"] = build_clarification_questions(
                clarification_fields
            )

    include_decision_fields = reply_mode not in {"off_topic_redirect", "intake"}
    if validated_engine_output is not None and include_decision_fields:
        for field_name in ("track", "phase", "risk_flag", "today_action", "plan_update_status"):
            field_value = _string_field(validated_engine_output.get(field_name))
            if field_value:
                decision_context[field_name] = field_value
        risk_recent_history = validated_engine_output.get("risk_recent_history")
        if isinstance(risk_recent_history, list) and risk_recent_history:
            decision_context["risk_recent_history"] = [
                str(f).strip() for f in risk_recent_history if isinstance(f, str) and f.strip()
            ]

    if intake_completed_this_turn:
        decision_context["intake_completed_this_turn"] = True

    # Compute weeks_in_coaching from profile created_at
    created_at = profile_after.get("created_at")
    if isinstance(created_at, (int, float)) and created_at > 0:
        weeks = max(1, int((_time.time() - created_at) / 604800))
        decision_context["weeks_in_coaching"] = weeks

    validated_plan: Dict[str, Any] = {}
    include_plan_summary = reply_mode in {"normal_coaching", "safety_risk_managed"}
    if include_plan_summary:
        normalized_plan_summary = _string_field(plan_summary)
        if normalized_plan_summary:
            validated_plan["plan_summary"] = normalized_plan_summary

    include_weekly_skeleton = reply_mode == "normal_coaching"
    if validated_engine_output is not None and include_weekly_skeleton:
        weekly_skeleton = validated_engine_output.get("weekly_skeleton")
        if isinstance(weekly_skeleton, list):
            validated_plan["weekly_skeleton"] = [
                str(item).strip()
                for item in weekly_skeleton
                if isinstance(item, str) and str(item).strip()
            ]
        next_email_payload = validated_engine_output.get("next_email_payload")
        if isinstance(next_email_payload, dict):
            session_guidance = next_email_payload.get("sessions")
            if isinstance(session_guidance, list):
                normalized_session_guidance = [
                    str(item).strip()
                    for item in session_guidance
                    if isinstance(item, str) and str(item).strip()
                ]
                if normalized_session_guidance:
                    validated_plan["session_guidance"] = normalized_session_guidance
            adjustments_or_priorities = []
            for field_name in ("summary", "plan_focus_line", "technique_cue", "recovery_target"):
                field_value = _string_field(next_email_payload.get(field_name))
                if field_value:
                    adjustments_or_priorities.append(field_value)
            if adjustments_or_priorities:
                validated_plan["adjustments_or_priorities"] = adjustments_or_priorities
            if_then_rules = next_email_payload.get("if_then_rules")
            if isinstance(if_then_rules, list):
                normalized_if_then_rules = [
                    str(item).strip()
                    for item in if_then_rules
                    if isinstance(item, str) and str(item).strip()
                ]
                if normalized_if_then_rules:
                    validated_plan["if_then_rules"] = normalized_if_then_rules
            safety_note = _string_field(next_email_payload.get("safety_note"))
            if safety_note:
                validated_plan["safety_note"] = safety_note

    delivery_context: Dict[str, Any] = {}
    normalized_subject = _string_field(inbound_subject)
    if normalized_subject:
        delivery_context["inbound_subject"] = normalized_subject
    normalized_body = _string_field(inbound_body)
    if normalized_body:
        # Truncate to keep the brief bounded
        delivery_context["inbound_body"] = normalized_body[:4000] if len(normalized_body) > 4000 else normalized_body
    normalized_model_name = _string_field(selected_model_name)
    if normalized_model_name:
        delivery_context["selected_model_name"] = normalized_model_name
    normalized_connect_strava_link = _string_field(connect_strava_link)
    if normalized_connect_strava_link:
        delivery_context["connect_strava_link"] = normalized_connect_strava_link

    normalized_memory_context = memory_context if isinstance(memory_context, dict) else {}

    # AM2 durable fact model
    memory_notes = normalized_memory_context.get("memory_notes")
    if not isinstance(memory_notes, list):
        memory_notes = []
    else:
        try:
            memory_notes = validate_memory_notes(memory_notes)
        except AthleteMemoryContractError:
            memory_notes = []

    continuity_summary = normalized_memory_context.get("continuity_summary")
    if not isinstance(continuity_summary, dict):
        continuity_summary = None
    else:
        try:
            continuity_summary = ContinuitySummary.from_dict(continuity_summary).to_dict()
        except AthleteMemoryContractError:
            continuity_summary = None

    memory_salience = _shape_memory_salience_v4(memory_notes, continuity_summary)
    memory_available = bool(
        memory_salience["priority_facts"]
        or memory_salience["structure_facts"]
        or memory_salience["context_facts"]
        or memory_salience["continuity_focus"]
    )

    memory_payload: Dict[str, Any] = {
        "memory_available": memory_available,
        "continuity_summary": continuity_summary,
    }
    if memory_salience["priority_facts"]:
        memory_payload["priority_facts"] = memory_salience["priority_facts"]
    if memory_salience["structure_facts"]:
        memory_payload["structure_facts"] = memory_salience["structure_facts"]
    if memory_salience["context_facts"]:
        memory_payload["context_facts"] = memory_salience["context_facts"]
    if memory_salience["continuity_focus"]:
        memory_payload["continuity_focus"] = memory_salience["continuity_focus"]

    payload = {
        "reply_mode": reply_mode,
        "athlete_context": athlete_context,
        "decision_context": decision_context,
        "validated_plan": validated_plan,
        "delivery_context": delivery_context,
        "memory_context": memory_payload,
    }
    return ResponseBrief.from_dict(payload)


def build_response_generation_input(
    *,
    directive: Dict[str, Any],
    brief: ResponseBrief,
) -> Dict[str, Any]:
    """Reshape a CoachingDirective + ResponseBrief into a WriterBrief for the response generation skill.

    Strips `rationale` from the directive (internal reasoning, not for the writer).
    """
    # Strip rationale — it's for eval/logging only
    writer_directive = {
        k: v for k, v in directive.items() if k != "rationale"
    }

    return {
        "reply_mode": brief.reply_mode,
        "coaching_directive": writer_directive,
        "plan_data": dict(brief.validated_plan),
        "delivery_context": dict(brief.delivery_context),
    }
