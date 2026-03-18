"""
Profile extraction and gating for coaching context.
Business logic for coaching context; no auth or verification.
"""
from decimal import Decimal
from typing import Optional, Dict, Any, List

from skills.planner import (
    ProfileExtractionProposalError,
    run_profile_extraction_workflow,
)


def _contains_unknown_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("unknown", "not sure", "skip", "n/a", "na", "prefer not")
    )


def parse_profile_updates_from_email(body: str) -> Dict[str, Any]:
    """
    Parse athlete profile updates from email body.

    Uses an LLM-backed extractor for primary parsing. On extraction failure,
    returns an empty updates dict (fail closed).
    """
    updates: Dict[str, Any] = {}

    try:
        raw = run_profile_extraction_workflow(body)
    except ProfileExtractionProposalError:
        # Fail closed: do not apply any profile updates if extraction fails.
        return {}

    primary_goal = raw.get("primary_goal")
    if isinstance(primary_goal, str) and primary_goal.strip():
        updates["primary_goal"] = primary_goal.strip()

    time_availability = raw.get("time_availability")
    if isinstance(time_availability, dict):
        normalized_time: Dict[str, Any] = {}
        sessions_per_week = time_availability.get("sessions_per_week")
        if isinstance(sessions_per_week, (int, float)) and int(sessions_per_week) > 0:
            normalized_time["sessions_per_week"] = int(sessions_per_week)
        hours_per_week = time_availability.get("hours_per_week")
        if isinstance(hours_per_week, (int, float)) and float(hours_per_week) > 0:
            normalized_time["hours_per_week"] = float(hours_per_week)
        if normalized_time:
            updates["time_availability"] = normalized_time

    experience_level = raw.get("experience_level")
    if isinstance(experience_level, str) and experience_level.strip():
        updates["experience_level"] = experience_level.strip().lower()
    else:
        updates["experience_level"] = "unknown"

    experience_level_note = raw.get("experience_level_note")
    if isinstance(experience_level_note, str) and experience_level_note.strip():
        updates["experience_level_note"] = experience_level_note.strip()

    constraints = raw.get("constraints")
    if isinstance(constraints, list):
        normalized_constraints: List[Dict[str, Any]] = []
        for item in constraints:
            if not isinstance(item, dict):
                continue
            summary = str(item.get("summary", "")).strip()
            if not summary:
                continue
            constraint_type = str(item.get("type", "other")).strip().lower() or "other"
            severity = str(item.get("severity", "medium")).strip().lower() or "medium"
            active = item.get("active")
            if not isinstance(active, bool):
                active = True
            normalized_constraints.append(
                {
                    "type": constraint_type,
                    "summary": summary,
                    "severity": severity,
                    "active": active,
                }
            )
        updates["constraints"] = normalized_constraints
    elif _contains_unknown_marker(body) and "constraints" in body.lower():
        updates["constraints"] = []

    return updates


def get_missing_required_profile_fields(profile: Optional[Dict[str, Any]]) -> List[str]:
    """Return list of required profile field names that are missing or invalid."""
    profile = profile or {}
    missing: List[str] = []

    primary_goal = str(profile.get("primary_goal", "")).strip()
    if not primary_goal:
        missing.append("primary_goal")

    time_availability = profile.get("time_availability")
    has_time = False
    if isinstance(time_availability, dict):
        sessions_per_week = time_availability.get("sessions_per_week")
        hours_per_week = time_availability.get("hours_per_week")
        has_sessions = isinstance(sessions_per_week, int) and sessions_per_week > 0
        has_hours = isinstance(hours_per_week, (int, float, Decimal)) and float(hours_per_week) > 0
        has_time = has_sessions or has_hours
    if not has_time:
        missing.append("time_availability")

    experience_level = str(profile.get("experience_level", "")).strip().lower()
    if experience_level not in {"beginner", "intermediate", "advanced", "unknown"}:
        missing.append("experience_level")

    constraints = profile.get("constraints")
    if not isinstance(constraints, list):
        missing.append("constraints")

    return missing
