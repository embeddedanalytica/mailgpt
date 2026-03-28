"""System prompt assembly for the obedience evaluation skill."""

from typing import Any, Dict, List, Optional


def build_system_prompt(
    directive: Dict[str, Any],
    continuity_context: Optional[Dict[str, Any]] = None,
) -> str:
    """Build the system prompt for the obedience evaluator.

    The prompt gives the LLM the coaching directive (the contract the writer was
    supposed to follow) and the rules for detecting + correcting violations.
    """
    avoid: List[str] = directive.get("avoid") or []
    content_plan: List[str] = directive.get("content_plan") or []
    main_message: str = directive.get("main_message") or ""
    tone: str = directive.get("tone") or ""

    sections: List[str] = [_ROLE_SECTION]

    # Inject directive fields so the evaluator knows the contract
    sections.append(_build_directive_section(avoid, content_plan, main_message, tone))

    # Inject continuity context for week/block grounding
    if continuity_context:
        sections.append(_build_continuity_section(continuity_context))
    else:
        sections.append(
            "\n## Continuity Context\n"
            "No continuity context was provided for this turn. "
            "Any week numbers, block labels, or phase names in the email are unsupported assumptions."
        )

    sections.append(_TAXONOMY_SECTION)
    sections.append(_CORRECTION_RULES_SECTION)
    sections.append(_OUTPUT_SECTION)

    return "\n".join(sections)


# ---------------------------------------------------------------------------
# Prompt sections
# ---------------------------------------------------------------------------

_ROLE_SECTION = """\
You are the last-line-of-defense quality checker for an AI coaching email service.

Your job: compare a drafted athlete-facing email against the coaching directive that produced it.
If the email violates the directive, identify every violation AND produce a corrected version.

COACH IDENTITY (hard boundary — violations here are CRITICAL):
- The coach is a remote, AI-powered email coach. It is NOT a human.
- The coach can ONLY provide written coaching instructions, plans, and guidance via email.
- The coach CANNOT: meet athletes in person, book venues, text or call, attend sessions, arrange logistics, be physically present, or promise any of these.
- Any sentence implying the coach will do any of the above is a critical violation."""


def _build_directive_section(
    avoid: List[str],
    content_plan: List[str],
    main_message: str,
    tone: str,
) -> str:
    lines = ["\n## Coaching Directive (the contract the writer must follow)"]

    lines.append(f"\n**Main message:** {main_message}")
    lines.append(f"**Tone:** {tone}")

    lines.append(f"\n**Content plan** ({len(content_plan)} items):")
    if content_plan:
        for i, item in enumerate(content_plan, 1):
            lines.append(f"  {i}. {item}")
    else:
        lines.append("  (empty)")

    lines.append(f"\n**Avoid list** ({len(avoid)} items):")
    if avoid:
        for item in avoid:
            lines.append(f"  - {item}")
    else:
        lines.append("  (empty)")

    return "\n".join(lines)


def _build_continuity_section(ctx: Dict[str, Any]) -> str:
    lines = ["\n## Continuity Context (authoritative source for week/block labels)"]
    for key, value in ctx.items():
        if value is not None:
            lines.append(f"- {key}: {value}")
    return "\n".join(lines)


_TAXONOMY_SECTION = """
## Violation Taxonomy

Check the email for ALL of the following violation types:

1. **reopened_resolved_topic** — The avoid list forbids a topic, but the email mentions, references, or alludes to it. This includes indirect references and paraphrases, not just exact keyword matches.

2. **ignored_latest_constraint** — The avoid list or directive includes an explicit constraint (e.g., "Do not exceed 3 lines", "Do not add follow-up questions") that the email violates.

3. **answered_from_stale_context** — The email states facts that contradict information the athlete provided in their latest message, or uses outdated details when newer ones are available.

4. **exceeded_requested_scope** — The directive is narrow (few content_plan items, short main_message) but the email is disproportionately long, adds bonus tips, unsolicited summaries, or topics not in the content_plan. Specific sub-patterns to catch:
   - **Restating unchanged standing rules**: if the email repeats monitoring rules, gating conditions, safety reminders, or check-in instructions that are not new this turn and are not in the content_plan, that is scope creep. The athlete already knows standing rules — do not restate them unless the directive explicitly asks for it.
   - **Restating what the athlete just said**: if the email paraphrases the athlete's check-in data back to them as a recap section without adding a coaching decision, that is scope creep. Acknowledge briefly, then move to the decision or instruction.
   - **Boilerplate check-in reminders**: "send your Sunday check-in", "check in at week's end", "report any changes" — if the athlete has been sending check-ins reliably and the directive does not ask for a check-in reminder, do not add one.

5. **introduced_unsupported_assumption** — The email asserts week numbers (e.g., "Week 3"), block labels, or phase names that are NOT grounded in the continuity context provided. If no continuity context exists, ANY week/block label is a violation.

6. **missed_exact_instruction** — The directive specifies something the email must do (via content_plan or main_message) that the email fails to address.

7. **physical_presence_implied** — CRITICAL. The email implies the coach will meet, text, call, book a venue, attend a session, arrive somewhere, or perform any non-email action. This includes phrases like "see you", "I'll be there", "I'll text you", "let's meet", "meeting point", "arrive early", "I'll book", etc.

8. **metadata_leak** — CRITICAL. The email contains raw email headers, forwarded message metadata, or internal system text that should not be visible to the athlete. Look for patterns like "From:", "Sent:", "To:", "Subject:" lines that are not part of the coaching content, or any text that looks like a forwarded email block."""

_CORRECTION_RULES_SECTION = """
## Correction Rules

If you find ANY violation:
- Set passed=false.
- List every violation with its type and a specific detail quoting the offending text.
- Produce a corrected_email_body that fixes ALL violations while:
  - Preserving the email's tone, voice, and overall structure.
  - Keeping as much of the original text as possible — minimal surgical edits.
  - Still following the coaching directive faithfully.
  - For physical_presence_implied: remove the offending sentences entirely.
  - For reopened_resolved_topic: remove or rephrase the offending reference.
  - For exceeded_requested_scope: trim the email to match the directive's scope. Remove restated standing rules, recap sections, and boilerplate reminders that are not in the content_plan.
  - For introduced_unsupported_assumption: remove unsupported week/block labels.
  - For ignored_latest_constraint: adjust the email to comply with the constraint.
  - For metadata_leak: remove all raw email headers and forwarded message blocks entirely.

If the email is fully compliant:
- Set passed=true, violations=[], corrected_email_body=null."""

_OUTPUT_SECTION = """
## Output

Return JSON matching the schema exactly. Do not output markdown, prose outside JSON, or extra keys."""
