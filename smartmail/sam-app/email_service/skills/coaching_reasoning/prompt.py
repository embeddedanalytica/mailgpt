"""Prompt text for the coaching-reasoning workflow."""

from typing import Any, Dict, List, Optional

from prompt_pack_loader import load_coach_reply_prompt_pack
from skills.coaching_reasoning.doctrine import build_doctrine_context_for_brief

_PROMPT_PACK = load_coach_reply_prompt_pack()
_BASE_PROMPT = _PROMPT_PACK["coaching_reasoning"]["base_prompt"]


def _build_athlete_instructions_section(response_brief: Dict[str, Any]) -> str:
    """Render structured athlete instructions as a prompt section.

    Returns empty string when no instructions are detected.
    """
    delivery = response_brief.get("delivery_context", {})
    instructions = delivery.get("athlete_instructions")
    if not instructions:
        return ""

    lines = [
        "",
        "## Athlete instructions (extracted from current message)",
        "",
        "These are hard constraints. They override coaching doctrine and durable context.",
        "",
    ]

    forbidden = instructions.get("forbidden_topics")
    if forbidden:
        lines.append("Forbidden topics (athlete explicitly asked to stop mentioning these):")
        for topic in forbidden:
            lines.append(f"  - {topic}")
        lines.append("Add each forbidden topic to your avoid list.")
        lines.append("")

    scope = instructions.get("requested_scope")
    if scope:
        lines.append(f"Requested scope: {scope}")
        lines.append("Limit your content_plan to only what the athlete asked for.")
        lines.append("")

    fmt = instructions.get("format_constraints")
    if fmt:
        lines.append(f"Format constraint: {fmt}")
        lines.append("The writer must follow this format exactly.")
        lines.append("")

    suppression = instructions.get("reply_suppression_hint")
    if suppression:
        lines.append(f"Reply suppression preference: {suppression}")
        lines.append(
            "If none of the suppression exceptions apply (no direct question, "
            "no new risk, no plan correction, no open loop), set reply_action to 'suppress'."
        )
        lines.append("")

    overrides = instructions.get("latest_overrides")
    if overrides:
        lines.append("Latest overrides (corrections from athlete this turn):")
        for override in overrides:
            lines.append(f"  - {override}")
        lines.append("These override any conflicting durable facts or prior context.")
        lines.append("")

    return "\n".join(lines)


def _build_contradicted_facts_section(response_brief: Dict[str, Any]) -> str:
    """Render contradicted memory facts as a prompt section.

    Returns empty string when no contradictions are detected.
    """
    memory = response_brief.get("memory_context", {})
    contradicted = memory.get("contradicted_facts")
    if not contradicted:
        return ""

    lines = [
        "",
        "## Contradicted durable facts",
        "",
        "The following memory facts appear to be superseded by the athlete's current message.",
        "Do not treat these as current. The athlete's latest message is authoritative.",
        "",
    ]
    for fact in contradicted:
        lines.append(f"- {fact}")

    lines.append("")
    return "\n".join(lines)


def _build_continuity_section(continuity_context: Optional[Dict[str, Any]]) -> str:
    """Render the continuity context section for the system prompt.

    Returns empty string when no context is available.
    """
    if not continuity_context:
        return ""

    lines = [
        "",
        "## Continuity context",
        "",
        "The athlete's current training continuity state:",
        f"- Goal horizon: {continuity_context.get('goal_horizon_type', 'unknown')}",
        f"- Current phase: {continuity_context.get('current_phase', 'unknown')}",
        f"- Current block focus: {continuity_context.get('current_block_focus', 'unknown')}",
        f"- Weeks in current block: {continuity_context.get('weeks_in_current_block', 'unknown')}",
    ]

    weeks_until = continuity_context.get("weeks_until_event")
    event_date = continuity_context.get("goal_event_date")
    if weeks_until is not None:
        lines.append(f"- Weeks until event: {weeks_until} (event date: {event_date})")

    reason = continuity_context.get("last_transition_reason")
    if reason:
        lines.append(f"- Last transition reason: {reason}")

    lines.extend([
        "",
        "Based on this context and the athlete's current situation, emit a continuity_recommendation",
        "in your response. Use 'keep' as the default action when no change is needed.",
        "Only recommend 'focus_shift', 'phase_shift', or 'reset_block' when the athlete's",
        "situation genuinely warrants a transition.",
        "",
        "All recommendation fields are required even on 'keep'.",
        "",
        "Valid block focus values:",
        "  initial_assessment, rebuild_consistency, controlled_load_progression,",
        "  maintain_fitness, maintain_through_constraints, event_specific_build,",
        "  peak_for_event, taper_for_event, return_safely, recovery_deload",
        "",
        "Valid transition actions: keep, focus_shift, phase_shift, reset_block",
    ])

    return "\n".join(lines)


def build_system_prompt(
    response_brief: Dict[str, Any],
    continuity_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Assemble the system prompt with selectively loaded doctrine, continuity context,
    athlete instructions, and contradicted facts."""
    doctrine = build_doctrine_context_for_brief(response_brief)
    continuity_section = _build_continuity_section(continuity_context)
    instructions_section = _build_athlete_instructions_section(response_brief)
    contradicted_section = _build_contradicted_facts_section(response_brief)
    return (
        f"{_BASE_PROMPT}\n\nCoaching methodology:\n{doctrine}"
        f"{continuity_section}{instructions_section}{contradicted_section}"
    )
