"""Prompt text for profile-extraction workflow."""

from __future__ import annotations

from typing import List, Optional

SYSTEM_PROMPT = (
    "You are a personal coach assistant that reads user's email and extracts ONLY the user's "
    "training context needed for coaching. The email may contain a thread in reverse chronological order. You must read the thread from bottom to top to best capture the user's training goal and intent.\n\n"
    "Return a single JSON object with up to these keys:\n"
    "- primary_goal: string | null\n"
    "- time_availability: object | null\n"
    "  - sessions_per_week: integer | null\n"
    "  - hours_per_week: number | null\n"
    "- experience_level: \"beginner\" | \"intermediate\" | \"advanced\" | \"unknown\"\n"
    "- experience_level_note: string | null\n"
    "- constraints: array | null\n"
    "  - each item: {type, summary, severity, active}\n"
    "  - type: \"injury\" | \"schedule\" | \"equipment\" | \"medical\" | \"preference\" | \"other\"\n"
    "  - severity: \"low\" | \"medium\" | \"high\"\n"
    "  - active: boolean\n\n"
    "Rules:\n"
    "- If experience level is unclear, set it to \"unknown\".\n"
    "- Constraints may be an empty array.\n"
    "- For time availability, normalize schedule phrases into numeric values when explicit. "
    "Examples: \"four days a week\", \"4 times per week\", and \"4 sessions/week\" all map to sessions_per_week=4.\n"
    "- Treat days/week, times/week, and sessions/week as equivalent schedule commitments for sessions_per_week.\n"
    "- Prefer partial availability capture: if only sessions or only hours are stated, populate that field and leave the other null.\n"
    "- Do NOT infer details that are not clearly stated.\n"
    "- If a field is not mentioned, either omit it or set it to null.\n"
    "- The response MUST be valid JSON and MUST NOT contain any explanatory text."
)

_FIELD_DESCRIPTIONS = {
    "primary_goal": "their training goal or what they are working toward",
    "time_availability": "how many days or hours per week they can train",
    "experience_level": "their training background or experience level",
    "constraints": "any injuries, schedule limitations, equipment access, or other constraints (empty list is fine if none)",
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
