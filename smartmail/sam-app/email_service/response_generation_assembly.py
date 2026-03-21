"""Assembly helpers for bounded response-generation inputs."""

from __future__ import annotations

from typing import Any, Dict, Optional

from athlete_memory_contract import (
    BACKBONE_SLOT_KEYS,
    AthleteMemoryContractError,
    BackboneSlots,
    ContinuitySummary,
    validate_backbone_slots,
    validate_context_note_list,
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


def _shape_memory_salience_v3(
    backbone: dict[str, Any],
    context_notes: list[dict[str, Any]],
    continuity_summary: Optional[dict[str, Any]],
) -> dict[str, Any]:
    """Shapes AM3 memory tiers into salience categories for the response LLM."""
    # Backbone = priority memory (structurally protected, always included)
    backbone_summaries: dict[str, str] = {}
    for key in BACKBONE_SLOT_KEYS:
        slot = backbone.get(key)
        if isinstance(slot, dict):
            summary = _string_field(slot.get("summary"))
            if summary:
                backbone_summaries[key] = summary

    continuity_focus = None
    if isinstance(continuity_summary, dict):
        continuity_focus = _string_field(continuity_summary.get("summary"))

    return {
        "backbone_summaries": backbone_summaries,
        "context_notes": context_notes,
        "continuity_focus": continuity_focus,
    }


def _constraint_summaries(profile_after: Dict[str, Any]) -> Optional[str]:
    constraints = profile_after.get("constraints")
    if not isinstance(constraints, list):
        return None
    summaries = [
        str(item.get("summary", "")).strip()
        for item in constraints
        if isinstance(item, dict) and str(item.get("summary", "")).strip()
    ]
    if not summaries:
        return None
    return "; ".join(summaries)


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

    decision_context: Dict[str, Any] = {}
    if reply_mode == "intake" and missing_profile_fields:
        decision_context["missing_profile_fields"] = list(missing_profile_fields)
        decision_context["clarification_needed"] = True
    else:
        clarification_needed = reply_mode == "clarification" or bool(missing_profile_fields)
        if isinstance(rule_engine_decision, dict):
            clarification_needed = clarification_needed or bool(
                rule_engine_decision.get("clarification_needed")
            )
        if clarification_needed:
            decision_context["clarification_needed"] = True
        if missing_profile_fields:
            decision_context["clarification_questions"] = build_clarification_questions(missing_profile_fields)

    include_decision_fields = reply_mode not in {"off_topic_redirect", "intake"}
    if validated_engine_output is not None and include_decision_fields:
        for field_name in ("track", "phase", "risk_flag", "today_action", "plan_update_status"):
            field_value = _string_field(validated_engine_output.get(field_name))
            if field_value:
                decision_context[field_name] = field_value

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

    # AM3 backbone + context_notes model
    backbone = normalized_memory_context.get("backbone")
    if not isinstance(backbone, dict):
        backbone = BackboneSlots.empty().to_dict()
    else:
        try:
            backbone = validate_backbone_slots(backbone).to_dict()
        except AthleteMemoryContractError:
            backbone = BackboneSlots.empty().to_dict()

    context_notes = normalized_memory_context.get("context_notes")
    if not isinstance(context_notes, list):
        context_notes = []
    else:
        try:
            context_notes = validate_context_note_list(context_notes)
        except AthleteMemoryContractError:
            context_notes = []

    continuity_summary = normalized_memory_context.get("continuity_summary")
    if not isinstance(continuity_summary, dict):
        continuity_summary = None
    else:
        try:
            continuity_summary = ContinuitySummary.from_dict(continuity_summary).to_dict()
        except AthleteMemoryContractError:
            continuity_summary = None

    memory_salience = _shape_memory_salience_v3(backbone, context_notes, continuity_summary)
    memory_available = bool(
        memory_salience["backbone_summaries"]
        or context_notes
        or memory_salience["continuity_focus"]
    )

    memory_payload: Dict[str, Any] = {
        "memory_available": memory_available,
        "continuity_summary": continuity_summary,
    }
    if memory_salience["backbone_summaries"]:
        memory_payload["backbone_summaries"] = memory_salience["backbone_summaries"]
    if memory_salience["context_notes"]:
        memory_payload["context_notes"] = memory_salience["context_notes"]
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
