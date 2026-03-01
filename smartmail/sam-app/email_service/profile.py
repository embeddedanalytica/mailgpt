"""
Profile extraction and gating: goal, weekly time budget, sports.
Business logic for coaching context; no auth or verification.
"""
import re
from typing import Optional, Dict, Any, List

from openai_responder import ProfileExtractor, ProfileExtractionError
from email_copy import EmailCopy


def _contains_unknown_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("unknown", "not sure", "skip", "n/a", "na", "prefer not")
    )


class GoalExtractor:
    """Pluggable goal extraction strategy."""

    def extract_goal(self, email_body: str) -> Optional[str]:
        raise NotImplementedError()


class RegexGoalExtractor(GoalExtractor):
    """Default goal extraction using deterministic regex patterns."""

    def extract_goal(self, email_body: str) -> Optional[str]:
        return _extract_goal_with_regex(email_body)


_goal_extractor: GoalExtractor = RegexGoalExtractor()


def set_goal_extractor(extractor: GoalExtractor) -> None:
    """Override the default goal extractor (e.g. for tests or future LLM extraction)."""
    global _goal_extractor
    _goal_extractor = extractor


def extract_goal_from_email(email_body: str) -> Optional[str]:
    return _goal_extractor.extract_goal(email_body)


class WeeklyTimeExtractor:
    """Pluggable weekly time extraction strategy."""

    def extract_weekly_minutes(self, email_body: str) -> Optional[int]:
        raise NotImplementedError()


class RegexWeeklyTimeExtractor(WeeklyTimeExtractor):
    """Default weekly time extraction using deterministic regex patterns."""

    def extract_weekly_minutes(self, email_body: str) -> Optional[int]:
        return _extract_weekly_minutes_with_regex(email_body)


_weekly_time_extractor: WeeklyTimeExtractor = RegexWeeklyTimeExtractor()


def set_weekly_time_extractor(extractor: WeeklyTimeExtractor) -> None:
    global _weekly_time_extractor
    _weekly_time_extractor = extractor


def extract_weekly_minutes_from_email(email_body: str) -> Optional[int]:
    return _weekly_time_extractor.extract_weekly_minutes(email_body)


class SportsExtractor:
    """Pluggable sports extraction strategy."""

    def extract_sports(self, email_body: str) -> List[str]:
        raise NotImplementedError()


class KeywordSportsExtractor(SportsExtractor):
    """Default sports extraction using keyword normalization."""

    def extract_sports(self, email_body: str) -> List[str]:
        return _extract_sports_with_keywords(email_body)


_sports_extractor: SportsExtractor = KeywordSportsExtractor()


def set_sports_extractor(extractor: SportsExtractor) -> None:
    global _sports_extractor
    _sports_extractor = extractor


def extract_sports_from_email(email_body: str) -> List[str]:
    return _sports_extractor.extract_sports(email_body)


def _extract_goal_with_regex(text: str) -> Optional[str]:
    goal_patterns = [
        r"\bgoal\s*[:\-]\s*([^\n\r]+)",
        r"\bmy goal is\s+([^\n\r]+)",
        r"\bi want to\s+([^\n\r]+)",
        r"\bi(?:'| a)?m training for\s+([^\n\r]+)",
    ]
    for pattern in goal_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            goal = match.group(1).strip(" .,!?:;")
            if goal:
                return goal
    return None


def _extract_weekly_minutes_with_regex(text: str) -> Optional[int]:
    combined_match = re.search(
        r"(\d{1,3})\s*h(?:ours?)?\s*(\d{1,3})?\s*m(?:in(?:utes?)?)?",
        text,
        flags=re.IGNORECASE,
    )
    if combined_match:
        hours = int(combined_match.group(1))
        minutes = int(combined_match.group(2) or 0)
        return (hours * 60) + minutes

    hour_match = re.search(r"(\d{1,3})\s*h(?:ours?)?\b", text, flags=re.IGNORECASE)
    if hour_match:
        return int(hour_match.group(1)) * 60

    minute_match = re.search(
        r"(\d{1,4})\s*m(?:in(?:utes?)?)?\b", text, flags=re.IGNORECASE
    )
    if minute_match:
        return int(minute_match.group(1))

    weekly_numeric = re.search(
        r"\b(?:weekly|per week)\D{0,20}(\d{2,4})\b", text, flags=re.IGNORECASE
    )
    if weekly_numeric:
        return int(weekly_numeric.group(1))

    return None


def _extract_sports_with_keywords(text: str) -> List[str]:
    known = {
        "running": "running",
        "run": "running",
        "jogging": "running",
        "cycling": "cycling",
        "bike": "cycling",
        "biking": "cycling",
        "swimming": "swimming",
        "swim": "swimming",
        "triathlon": "triathlon",
        "strength": "strength",
        "weightlifting": "strength",
        "gym": "strength",
        "yoga": "yoga",
        "hiking": "hiking",
    }
    detected: List[str] = []

    explicit_line = re.search(r"\bsports?\s*[:\-]\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if explicit_line:
        parts = re.split(r"[,/]| and ", explicit_line.group(1), flags=re.IGNORECASE)
        for part in parts:
            token = part.strip().lower()
            if token in known:
                canonical = known[token]
                if canonical not in detected:
                    detected.append(canonical)

    lowered = text.lower()
    for keyword, canonical in known.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            if canonical not in detected:
                detected.append(canonical)
    return detected


def parse_profile_updates_from_email(body: str) -> Dict[str, Any]:
    """
    Parse athlete profile updates from email body.

    Uses an LLM-backed extractor for primary parsing. On extraction failure,
    returns an empty updates dict (fail closed).
    """
    updates: Dict[str, Any] = {}

    try:
        raw = ProfileExtractor.extract_profile_fields(body)
    except ProfileExtractionError:
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
        has_hours = isinstance(hours_per_week, (int, float)) and float(hours_per_week) > 0
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


def build_profile_collection_reply(missing_fields: List[str]) -> str:
    """Build the reply text asking the user for missing profile fields."""
    joined_prompts = "\n".join(EmailCopy.build_profile_collection_lines(missing_fields))
    return (
        f"{EmailCopy.PROFILE_COLLECTION_INTRO}"
        f"{joined_prompts}\n\n"
        f"{EmailCopy.PROFILE_COLLECTION_UNKNOWN_HINT}"
    )
