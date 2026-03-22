"""Communication-copy helpers for response-generation workflows."""

from __future__ import annotations

from typing import List


_PROFILE_PROMPT_PRIMARY_GOAL = "- Your primary goal (e.g., first marathon, improve 10k time)"
_PROFILE_PROMPT_TIME_AVAILABILITY = "- Your time availability (sessions/week and/or hours/week)"
_PROFILE_PROMPT_EXPERIENCE_LEVEL = (
    "- Your experience level (beginner, intermediate, advanced, or unknown)"
)
_PROFILE_PROMPT_INJURY_CONSTRAINTS = (
    "- Any current injuries, pains, or physical limitations (perfectly fine if there are none — just let me know either way)"
)


def build_clarification_questions(missing_fields: List[str]) -> List[str]:
    lines: List[str] = []
    if "primary_goal" in missing_fields:
        lines.append(_PROFILE_PROMPT_PRIMARY_GOAL)
    if "time_availability" in missing_fields:
        lines.append(_PROFILE_PROMPT_TIME_AVAILABILITY)
    if "experience_level" in missing_fields:
        lines.append(_PROFILE_PROMPT_EXPERIENCE_LEVEL)
    if "injury_status" in missing_fields:
        lines.append(_PROFILE_PROMPT_INJURY_CONSTRAINTS)
    return lines
