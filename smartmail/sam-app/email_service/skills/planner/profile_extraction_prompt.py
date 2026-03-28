"""Prompt text for profile-extraction workflow."""

from __future__ import annotations

from typing import List, Optional

SYSTEM_PROMPT = (
    "You are a personal coach assistant that reads user's email and extracts ONLY the user's "
    "training context needed for coaching. The email may contain a thread in reverse chronological order. You must read the thread from bottom to top to best capture the user's training goal and intent.\n\n"
    "Return a single JSON object with up to these keys:\n"
    "- primary_goal: string | null\n"
    "- time_availability: object | null\n"
    "  - sessions_per_week: string | null\n"
    "  - daily_windows: array[string] | null\n"
    "  - availability_notes: string | null\n"
    "- experience_level: \"beginner\" | \"intermediate\" | \"advanced\" | \"unknown\"\n"
    "- experience_level_note: string | null\n"
    "- constraints: array | null\n"
    "  - practical, non-injury constraints only: schedule, childcare, travel, equipment, terrain, training preferences\n"
    "  - each item: {type, summary, severity, active}\n"
    "  - type: \"schedule\" | \"equipment\" | \"preference\" | \"other\"\n"
    "  - severity: \"low\" | \"medium\" | \"high\"\n"
    "  - active: boolean\n"
    "  - set to null if no practical constraints are mentioned\n"
    "- injury_status: object | null\n"
    "  - has_injuries: boolean\n"
    "  - gate field — answers one question: did the athlete explicitly answer whether they currently have any physical issue, pain, soreness, or training restriction caused by their body?\n"
    "  - set to {\"has_injuries\": true} when the athlete mentions ANY injury, pain, soreness, niggle, physical limitation, or body-caused restriction — even if they also say it is the only issue\n"
    "  - set to {\"has_injuries\": false} when the athlete explicitly indicates they have no current physical problems or restrictions, even if they do not use the word \"injury\". This includes explicit statements of: no pain, no soreness, no physical limitation, no restriction, no medical limitation, no clinician-imposed limit, or nothing else going on physically\n"
    "  - set to null when the athlete has NOT addressed the topic of injuries or physical health at all\n"
    "- injury_constraints: array | null\n"
    "  - optional structured detail — only populate when injury_status.has_injuries is true\n"
    "  - physical health only: injuries, pain, soreness, niggles, medical conditions, rehab status, medications, PT/doctor context, restrictions caused by the body\n"
    "  - each item: {type, summary, severity, active}\n"
    "  - type: \"injury\" | \"medical\"\n"
    "  - severity: \"low\" | \"medium\" | \"high\"\n"
    "  - active: boolean\n"
    "  - must be null when injury_status is null or injury_status.has_injuries is false\n\n"
    "Rules:\n"
    "- If experience level is unclear, set it to \"unknown\".\n"
    "- Keep constraints and injury_constraints strictly separated:\n"
    "  - constraints: schedule, childcare, equipment, terrain, preferences — never injuries\n"
    "  - injury_constraints: physical symptoms, pain, named conditions, medical context — never schedule or preferences\n"
    "  - training preferences like 'I want to take it easy' or 'I want to rebuild carefully' do NOT belong in injury_constraints\n"
    "  - 'I want to avoid getting carried away' is a preference — put it in constraints (type: preference) or omit it, never in injury_constraints\n"
    "- injury_status and injury_constraints work together:\n"
    "  - explicit denial of physical issues: \"I have no current pain or limitations\" → injury_status: {has_injuries: false}, injury_constraints: null\n"
    "  - explicit denial of restrictions: \"There are no physical restrictions on training right now\" → injury_status: {has_injuries: false}, injury_constraints: null\n"
    "  - named issue with partial reassurance: \"My knee is a little sore, but that's the only thing\" → injury_status: {has_injuries: true}, injury_constraints: [{type: \"injury\", ...}]\n"
    "  - vague caution only: \"I'm trying not to overdo it\" → injury_status: null, injury_constraints: null\n"
    "  - not mentioned at all → injury_status: null, injury_constraints: null\n"
    "- injury_status must be null unless the athlete explicitly addresses their physical state. Wanting to be conservative or avoid overdoing it is a training preference, NOT a physical health statement. Being physically or medically unrestricted IS a physical health statement.\n"
    "- For time availability, prefer faithful capture over normalization.\n"
    "- Put coarse weekly capacity in sessions_per_week as the athlete describes it (examples: \"4 days/week\", \"usually 5 if work is calm\").\n"
    "- Put concrete recurring schedule windows in daily_windows as short strings (examples: \"Mon-Thu 05:45-07:15\", \"Mon evening 18:30-19:30 locked\").\n"
    "- Put important caveats, preferences, and conditional schedule notes in availability_notes (examples: \"Use mornings for longer sessions\", \"travel weeks usually mean hotel treadmill only\").\n"
    "- Treat any actionable schedule detail as valid time_availability evidence even when no numeric totals are given.\n"
    "- Prefer partial capture of time_availability over leaving it empty.\n"
    "- Do NOT infer details that are not clearly stated.\n"
    "- If a field is not mentioned, either omit it or set it to null.\n"
    "- The response MUST be valid JSON and MUST NOT contain any explanatory text."
)

_FIELD_DESCRIPTIONS = {
    "primary_goal": "their training goal or what they are working toward",
    "time_availability": "their training availability, including recurring windows, weekly capacity, or schedule notes",
    "experience_level": "their training background or experience level",
    "injury_status": (
        "whether they currently have any physical issue, pain, soreness, or "
        "training restriction caused by their body — or an explicit confirmation "
        "that they have none. Must be answered explicitly by the athlete; do not infer."
    ),
}


def build_intake_aware_prompt(missing_fields: Optional[List[str]] = None) -> str:
    """Build a system prompt that focuses extraction on missing profile fields."""
    if not missing_fields:
        return SYSTEM_PROMPT

    focus_lines = [
        _FIELD_DESCRIPTIONS[f]
        for f in missing_fields
        if f in _FIELD_DESCRIPTIONS
    ]
    if not focus_lines:
        return SYSTEM_PROMPT

    focus_section = (
        "\n\nIntake context:\n"
        "This is an onboarding conversation. The following information is still needed from the athlete:\n"
        + "".join(f"- {line}\n" for line in focus_lines)
        + "Pay extra attention to extracting these fields from the email. "
        "The athlete may mention them casually or indirectly."
    )
    return SYSTEM_PROMPT + focus_section
