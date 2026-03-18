"""Validator for profile-extraction workflow."""

from __future__ import annotations

from typing import Any, Dict


class ProfileExtractionContractError(ValueError):
    """Raised when profile-extraction response shape is invalid."""


def validate_profile_extraction_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ProfileExtractionContractError("invalid_response_shape")
    time_availability = payload.get("time_availability")
    if isinstance(time_availability, dict):
        sessions_per_week = time_availability.get("sessions_per_week")
        hours_per_week = time_availability.get("hours_per_week")
        has_sessions = isinstance(sessions_per_week, (int, float)) and float(sessions_per_week) > 0
        has_hours = isinstance(hours_per_week, (int, float)) and float(hours_per_week) > 0
        if not (has_sessions or has_hours):
            primary_goal = payload.get("primary_goal")
            experience_level = str(payload.get("experience_level", "")).strip().lower()
            experience_level_note = payload.get("experience_level_note")
            constraints = payload.get("constraints")
            has_primary_goal = isinstance(primary_goal, str) and bool(primary_goal.strip())
            has_experience_signal = experience_level in {"beginner", "intermediate", "advanced"}
            has_experience_note = isinstance(experience_level_note, str) and bool(experience_level_note.strip())
            has_constraints = isinstance(constraints, list) and any(
                isinstance(item, dict) and str(item.get("summary", "")).strip() for item in constraints
            )
            if not (has_primary_goal or has_experience_signal or has_experience_note or has_constraints):
                raise ProfileExtractionContractError("invalid_time_availability_placeholder")
    return dict(payload)
