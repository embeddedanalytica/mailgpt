"""Assembly helpers for bounded response-generation inputs."""

from __future__ import annotations

import re
import time as _time
from typing import Any, Dict, List, Optional

from memory_compiler import compile_prompt_memory
from response_generation_contract import ResponseBrief, normalize_reply_mode
from sectioned_memory_contract import (
    ContinuitySummary,
    SectionedMemoryContractError,
    empty_sectioned_memory,
    validate_sectioned_memory,
)
from skills.response_generation import build_clarification_questions


def _string_field(value: Any) -> Optional[str]:
    if not isinstance(value, str):
        return None
    normalized = value.strip()
    return normalized or None


def _fact_summaries(facts: List[Dict[str, Any]]) -> List[str]:
    out: List[str] = []
    for fact in facts:
        if not isinstance(fact, dict):
            continue
        s = _string_field(fact.get("summary"))
        if s:
            out.append(s)
    return out


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



# ---------------------------------------------------------------------------
# Memory contradiction detection
# ---------------------------------------------------------------------------

def detect_contradicted_facts(
    inbound_body: Optional[str],
    memory_facts: List[str],
) -> List[str]:
    """Detect memory facts that appear to be contradicted by the inbound message.

    Uses simple keyword overlap to find facts where the athlete's message
    explicitly negates or updates the stored information. Returns a list of
    human-readable contradiction descriptions.

    This is intentionally conservative — it only flags facts where the inbound
    body contains clear negation or correction language near the fact's keywords.
    """
    if not inbound_body or not memory_facts:
        return []

    text_lower = inbound_body.lower()
    contradictions: List[str] = []

    # Negation/correction phrases that signal a fact may be outdated
    _NEGATION_PHRASES = [
        "no longer", "not anymore", "no more", "resolved", "cleared up",
        "gone now", "don't have", "do not have", "isn't an issue",
        "is not an issue", "stopped", "changed", "updated", "now I can",
        "I can now", "actually",
    ]

    for fact in memory_facts:
        fact_lower = fact.lower()
        # Extract key nouns from the fact (words > 3 chars, skip common words)
        _SKIP_WORDS = {"with", "that", "this", "from", "have", "been", "when", "than", "also"}
        fact_keywords = [
            w for w in re.findall(r"[a-z]+", fact_lower)
            if len(w) > 3 and w not in _SKIP_WORDS
        ]
        if not fact_keywords:
            continue

        # Check if any fact keyword appears near a negation phrase in the inbound text
        for keyword in fact_keywords:
            if keyword not in text_lower:
                continue
            # Look for negation phrases within ~60 chars of the keyword
            for neg in _NEGATION_PHRASES:
                if neg not in text_lower:
                    continue
                kw_pos = text_lower.find(keyword)
                neg_pos = text_lower.find(neg)
                if abs(kw_pos - neg_pos) < 60:
                    contradictions.append(
                        f"Prior fact \"{fact}\" may be superseded by current message"
                    )
                    break
            else:
                continue
            break

    return contradictions


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

    if intake_completed_this_turn:
        decision_context["intake_completed_this_turn"] = True

    # Athlete presentation signals from conversation intelligence
    # Note: requested_action is intentionally NOT forwarded here — it is used
    # for routing only (inbound_rule_router). Coaching reasoning decides behavior
    # from first principles.
    if isinstance(rule_engine_decision, dict):
        bp = str(rule_engine_decision.get("brevity_preference", "")).strip()
        if bp and bp != "normal":
            decision_context["brevity_preference"] = bp

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

    raw_sectioned = normalized_memory_context.get("sectioned_memory")
    if not isinstance(raw_sectioned, dict):
        sectioned_memory = empty_sectioned_memory()
    else:
        try:
            sectioned_memory = validate_sectioned_memory(raw_sectioned)
        except SectionedMemoryContractError:
            sectioned_memory = empty_sectioned_memory()

    continuity_summary = normalized_memory_context.get("continuity_summary")
    if not isinstance(continuity_summary, dict):
        continuity_summary = None
    else:
        try:
            continuity_summary = ContinuitySummary.from_dict(continuity_summary).to_dict()
        except SectionedMemoryContractError:
            continuity_summary = None

    compiled = compile_prompt_memory(sectioned_memory, continuity_summary)
    priority_facts = _fact_summaries(compiled["priority_facts"])
    structure_facts = _fact_summaries(compiled["structure_facts"])
    preference_facts = _fact_summaries(compiled["preference_facts"])
    context_facts = _fact_summaries(compiled["context_facts"])
    continuity_focus = compiled.get("continuity_focus")

    memory_available = bool(
        priority_facts
        or structure_facts
        or preference_facts
        or context_facts
        or continuity_focus
    )

    memory_payload: Dict[str, Any] = {
        "memory_available": memory_available,
        "continuity_summary": continuity_summary,
        "sectioned_memory": sectioned_memory,
    }
    if priority_facts:
        memory_payload["priority_facts"] = priority_facts
    if structure_facts:
        memory_payload["structure_facts"] = structure_facts
    if preference_facts:
        memory_payload["preference_facts"] = preference_facts
    if context_facts:
        memory_payload["context_facts"] = context_facts
    if continuity_focus:
        memory_payload["continuity_focus"] = continuity_focus

    # Detect memory facts contradicted by the current inbound message
    all_memory_summaries = (
        priority_facts + structure_facts + preference_facts + context_facts
    )
    contradicted = detect_contradicted_facts(
        normalized_body if normalized_body else None,
        all_memory_summaries,
    )
    if contradicted:
        memory_payload["contradicted_facts"] = contradicted

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
    continuity_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Reshape a CoachingDirective + ResponseBrief into a WriterBrief for the response generation skill.

    Strips strategist-only fields from the directive before handing it to the writer.
    """
    # These fields are used by orchestration and eval, not by the writer contract.
    writer_directive = {
        k: v
        for k, v in directive.items()
        if k not in {"rationale", "reply_action"}
    }

    result = {
        "reply_mode": brief.reply_mode,
        "coaching_directive": writer_directive,
        "plan_data": dict(brief.validated_plan),
        "delivery_context": dict(brief.delivery_context),
    }
    if continuity_context is not None:
        result["continuity_context"] = continuity_context
    return result
