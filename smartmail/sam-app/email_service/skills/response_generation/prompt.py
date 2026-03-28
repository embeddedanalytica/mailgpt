"""Prompt text for the response-generation workflow."""

from typing import Any, Dict, List, Optional

from prompt_pack_loader import load_coach_reply_prompt_pack


_PROMPT_PACK = load_coach_reply_prompt_pack()
DIRECTIVE_SYSTEM_PROMPT = _PROMPT_PACK["response_generation"]["directive_system_prompt"]


def build_directive_constraints_section(brief: Dict[str, Any]) -> str:
    """Surface directive constraints prominently in the system prompt.

    Extracts avoid list items, scope boundaries, and format constraints from the
    coaching_directive so the writer sees them as hard rules, not just data in the
    user message.

    Returns empty string when no constraints need emphasis.
    """
    directive = brief.get("coaching_directive", {})
    avoid: List[str] = directive.get("avoid") or []
    content_plan: List[str] = directive.get("content_plan") or []

    lines: List[str] = []

    if avoid:
        lines.extend([
            "",
            "HARD CONSTRAINTS from the strategist (violating any of these is a failure):",
        ])
        for item in avoid:
            lines.append(f"  - {item}")
        lines.append("Do not mention, reference, or allude to anything on this list — not even as background context.")
        lines.append("")

    if content_plan and len(content_plan) <= 2 and not _content_plan_has_decision(content_plan):
        lines.extend([
            "Scope lock: the content_plan has only {n} item{s}. Produce exactly that — no extras, no bonus tips, no follow-up questions unless the directive includes one.".format(
                n=len(content_plan), s="" if len(content_plan) == 1 else "s"
            ),
            "",
        ])

    return "\n".join(lines) if lines else ""


_DECISION_KEYWORDS = {
    "approve", "add", "progress", "advance", "upgrade", "increase",
    "start", "begin", "introduce", "clear to", "cleared for",
    "decide", "decision", "confirm readiness", "ready to",
    "move to", "transition", "shift",
}


def _content_plan_has_decision(content_plan: List[str]) -> bool:
    """Return True when content_plan contains decision/progression language."""
    text = " ".join(content_plan).lower()
    return any(kw in text for kw in _DECISION_KEYWORDS)


def _is_narrow_directive(brief: Dict[str, Any]) -> bool:
    """Return True when the directive is minimal enough that continuity detail is noise.

    Returns False when the directive contains coaching decisions (approvals,
    progressions, transitions) even if the content_plan is short — those
    need full context.
    """
    directive = brief.get("coaching_directive", {})
    content_plan = directive.get("content_plan") or []
    main_message = directive.get("main_message") or ""
    if len(content_plan) > 2 or len(main_message) >= 120:
        return False
    if _content_plan_has_decision(content_plan):
        return False
    return True


def build_continuity_prompt_section(continuity_context: Optional[Dict[str, Any]]) -> str:
    """Render a continuity context section to append to the system prompt.

    Returns empty string when no context is available.
    """
    if not continuity_context:
        return ""

    lines = [
        "",
        "Training continuity context (from the continuity_context field in the brief):",
        f"- The athlete is in week {continuity_context.get('weeks_in_current_block', '?')} "
        f"of a {continuity_context.get('current_block_focus', 'unknown').replace('_', ' ')} block.",
    ]

    weeks_until = continuity_context.get("weeks_until_event")
    event_date = continuity_context.get("goal_event_date")
    if weeks_until is not None:
        lines.append(f"- {weeks_until} weeks until their goal event ({event_date}).")

    reason = continuity_context.get("last_transition_reason")
    if reason and reason != "bootstrap_initial_state":
        lines.append(f"- Current focus was set because: {reason}")

    lines.extend([
        "",
        "Week and block reference rules:",
        "- When referring to the athlete's position in training, use the week number and block focus above "
        "as the default source.",
        "- NEVER calculate, guess, or invent week numbers. If continuity_context says week 1, it is week 1 — "
        "even if the conversation has spanned multiple turns.",
        "- Do not say 'Week 3' when continuity_context says week 1. Do not say 'five weeks into the block' "
        "when continuity_context says week 2. The number here is the only correct number.",
        "- Do not invent continuity, block history, or phase durations beyond what is provided here.",
        "",
        "IMPORTANT — athlete override rule:",
        "- If the athlete explicitly corrects a week number, block label, or phase name in their current "
        "message, follow the athlete's correction. The athlete's latest explicit instruction overrides "
        "continuity_context values.",
        "- If the athlete asks you to stop using week labels or block names, omit them entirely.",
    ])

    return "\n".join(lines)
