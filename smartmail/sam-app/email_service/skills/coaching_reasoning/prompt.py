"""Prompt text for the coaching-reasoning workflow."""

from typing import Any, Dict, List, Optional

from prompt_pack_loader import load_coach_reply_prompt_pack
from skills.coaching_reasoning.doctrine import (
    build_doctrine_context_for_brief,
    build_doctrine_selection_trace,
)

_PROMPT_PACK = load_coach_reply_prompt_pack()
_CR = _PROMPT_PACK["coaching_reasoning"]
_BASE_PROMPT = _CR["base_prompt"]
_CONSTITUTION = _CR["constitution"]
_OPERATIONAL_RULES = _CR["operational_rules"]
_REPLY_MODE_RULES = _CR["reply_mode_rules"]



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


def _build_tiered_base_prompt(reply_mode: str) -> str:
    """Assemble the base prompt from constitution + operational rules + mode-specific rules.

    Falls back to the legacy monolithic base prompt when split files are absent.
    """
    if not _CONSTITUTION:
        return _BASE_PROMPT
    mode_rules = _REPLY_MODE_RULES.get(reply_mode, "")
    parts = [_CONSTITUTION, _OPERATIONAL_RULES]
    if mode_rules:
        parts.append(mode_rules)
    return "\n\n".join(parts)


def _build_selector_hints_section(response_brief: Dict[str, Any]) -> str:
    trace = build_doctrine_selection_trace(response_brief)
    lines = [
        "## Selector hints",
        "",
        f"- Turn purpose: {trace['turn_purpose']}",
        f"- Posture: {trace['posture']}",
        f"- Trajectory: {trace['trajectory']}",
        f"- Response shape: {trace['response_shape']}",
    ]
    if trace["situation_tags"]:
        tag_summary = ", ".join(
            f"{item['tag']} ({item['strength']})" for item in trace["situation_tags"]
        )
        lines.append(f"- Situation tags: {tag_summary}")
    if trace["purpose_micro_avoid"]:
        lines.append("- Micro-avoid: " + "; ".join(trace["purpose_micro_avoid"]))
    return "\n".join([""] + lines + [""])


def build_system_prompt(
    response_brief: Dict[str, Any],
    continuity_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Assemble the system prompt with selectively loaded doctrine, continuity context,
    athlete instructions, and contradicted facts."""
    reply_mode = response_brief.get("reply_mode", "normal_coaching")
    base = _build_tiered_base_prompt(reply_mode)
    selector_hints = _build_selector_hints_section(response_brief)
    doctrine = build_doctrine_context_for_brief(response_brief)
    continuity_section = _build_continuity_section(continuity_context)
    contradicted_section = _build_contradicted_facts_section(response_brief)
    return (
        f"{base}{selector_hints}\nCoaching methodology:\n{doctrine}"
        f"{continuity_section}{contradicted_section}"
    )
