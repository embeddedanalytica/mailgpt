"""
Profile extraction and gating: goal, weekly time budget, sports.
Business logic for coaching context; no auth or verification.
"""
import re
from typing import Optional, Dict, Any, List

from openai_responder import ProfileExtractor, ProfileExtractionError


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
    Parse coach profile updates from email body (goal, weekly time, sports).

    Uses an LLM-backed extractor for primary parsing, with deterministic
    normalization and unknown-marker handling here. On LLM failure, this
    function fails closed by returning an empty updates dict.
    """
    updates: Dict[str, Any] = {}

    try:
        raw = ProfileExtractor.extract_profile_fields(body)
    except ProfileExtractionError:
        # Fail closed: do not apply any profile updates if extraction fails.
        raw = {}

    # Goal
    goal_value = raw.get("goal")
    if isinstance(goal_value, str):
        goal_value = goal_value.strip()
    if goal_value:
        updates["goal"] = goal_value
    elif _contains_unknown_marker(body) and re.search(r"\bgoal\b", body, re.IGNORECASE):
        # Preserve deterministic handling of explicit unknown-style markers
        updates["goal_unknown"] = True
    elif isinstance(raw.get("goal_unknown"), bool) and raw.get("goal_unknown"):
        updates["goal_unknown"] = True

    # Weekly time budget (minutes)
    weekly_minutes = raw.get("weekly_time_budget_minutes")
    if isinstance(weekly_minutes, int) and weekly_minutes > 0:
        updates["weekly_time_budget_minutes"] = weekly_minutes
    elif _contains_unknown_marker(body) and re.search(
        r"\b(week|weekly|hours?|minutes?|time)\b", body, re.IGNORECASE
    ):
        updates["weekly_time_budget_unknown"] = True
    elif isinstance(raw.get("weekly_time_budget_unknown"), bool) and raw.get(
        "weekly_time_budget_unknown"
    ):
        updates["weekly_time_budget_unknown"] = True

    # Sports
    sports = raw.get("sports")
    normalized_sports: List[str] = []
    if isinstance(sports, list):
        for item in sports:
            if isinstance(item, str):
                token = item.strip().lower()
                if token and token not in normalized_sports:
                    normalized_sports.append(token)
    if normalized_sports:
        updates["sports"] = normalized_sports
    elif _contains_unknown_marker(body) and re.search(r"\bsports?\b", body, re.IGNORECASE):
        updates["sports_unknown"] = True
    elif isinstance(raw.get("sports_unknown"), bool) and raw.get("sports_unknown"):
        updates["sports_unknown"] = True

    return updates


def get_missing_required_profile_fields(profile: Optional[Dict[str, Any]]) -> List[str]:
    """Return list of required profile field names that are missing or invalid."""
    profile = profile or {}
    missing: List[str] = []

    goal = str(profile.get("goal", "")).strip()
    if not goal and not bool(profile.get("goal_unknown")):
        missing.append("goal")

    weekly_minutes = profile.get("weekly_time_budget_minutes")
    # Treat any non-empty value (string, number, etc.) as present. No type checks.
    has_weekly_minutes = bool(str(weekly_minutes).strip()) if weekly_minutes is not None else False

    if not has_weekly_minutes and not bool(profile.get("weekly_time_budget_unknown")):
        missing.append("weekly_time_budget_minutes")

    sports = profile.get("sports")
    valid_sports = isinstance(sports, list) and len(sports) > 0
    if not valid_sports and not bool(profile.get("sports_unknown")):
        missing.append("sports")

    return missing


def build_profile_collection_reply(missing_fields: List[str]) -> str:
    """Build the reply text asking the user for missing profile fields."""
    prompts = []
    if "goal" in missing_fields:
        prompts.append("- Your training goal (e.g., 10k PR, first marathon, improve fitness)")
    if "weekly_time_budget_minutes" in missing_fields:
        prompts.append("- Your weekly time budget (minutes or hours per week)")
    if "sports" in missing_fields:
        prompts.append("- Sports you want coaching for (e.g., running, cycling)")

    joined_prompts = "\n".join(prompts)
    return (
        "Thanks - before I can coach effectively, I need a bit more context.\n\n"
        "Please reply with:\n"
        f"{joined_prompts}\n\n"
        "If any item is unknown right now, you can say \"unknown\" for that item."
    )
