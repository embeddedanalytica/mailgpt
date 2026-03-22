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


def _normalize_constraint_list(raw_list: Any) -> List[Dict[str, Any]]:
    """Normalize a raw constraint list from the extractor. Returns empty list if invalid."""
    if not isinstance(raw_list, list):
        return []
    normalized: List[Dict[str, Any]] = []
    for item in raw_list:
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
        normalized.append(
            {
                "type": constraint_type,
                "summary": summary,
                "severity": severity,
                "active": active,
            }
        )
    return normalized


def parse_profile_updates_from_email(
    body: str,
    *,
    missing_fields: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Parse athlete profile updates from email body.

    Uses an LLM-backed extractor for primary parsing. On extraction failure,
    returns an empty updates dict (fail closed).

    When ``missing_fields`` is provided, the extraction prompt focuses on those
    fields to improve accuracy during onboarding intake.
    """
    updates: Dict[str, Any] = {}

    try:
        raw = run_profile_extraction_workflow(body, missing_fields=missing_fields)
    except ProfileExtractionProposalError:
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

    # General (non-injury) constraints — opportunistic, not required for intake completion.
    constraints = raw.get("constraints")
    if isinstance(constraints, list) and constraints:
        normalized = _normalize_constraint_list(constraints)
        if normalized:
            updates["constraints"] = normalized

    # Injury status gate — simple boolean answered by the athlete.
    injury_status = raw.get("injury_status")
    if isinstance(injury_status, dict) and isinstance(injury_status.get("has_injuries"), bool):
        updates["injury_status"] = {"has_injuries": injury_status["has_injuries"]}

    # Injury constraints — optional structured detail, only when has_injuries is true.
    injury_constraints = raw.get("injury_constraints")
    if isinstance(injury_constraints, list) and injury_constraints:
        normalized_injury = _normalize_constraint_list(injury_constraints)
        if normalized_injury:
            updates["injury_constraints"] = normalized_injury

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

    # Injury gate: athlete must have explicitly addressed their physical health.
    # injury_status is set by the extractor when the athlete says yes or no to injuries.
    injury_status = profile.get("injury_status")
    injury_addressed = (
        isinstance(injury_status, dict)
        and isinstance(injury_status.get("has_injuries"), bool)
    )
    if not injury_addressed:
        missing.append("injury_status")

    return missing
