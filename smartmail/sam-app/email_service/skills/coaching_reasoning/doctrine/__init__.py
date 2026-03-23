"""Coaching doctrine loader — selective assembly for strategist prompts."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from .manifest import (
    CORE_UNIVERSAL_FILES,
    OPTIONAL_UNIVERSAL_ORDER,
    RUNNING_OPTIONAL_ORDER,
    SPORT_ALIASES,
)

_DIR = Path(__file__).parent
_CACHE: dict[str, str] = {}


def _load(relative_path: str) -> str:
    if relative_path not in _CACHE:
        _CACHE[relative_path] = (_DIR / relative_path).read_text().strip()
    return _CACHE[relative_path]


def _resolve_sport(sport: Optional[str]) -> Optional[str]:
    """Resolve athlete's sport string to a canonical sport key."""
    normalized = (sport or "").strip().lower()
    if not normalized:
        return None
    for keyword, canonical in SPORT_ALIASES.items():
        if keyword in normalized:
            return canonical
    return None


def _resolve_sport_from_brief(brief: dict[str, Any]) -> Optional[str]:
    athlete_ctx = brief.get("athlete_context")
    if isinstance(athlete_ctx, dict):
        return _resolve_sport(athlete_ctx.get("primary_sport"))
    return None


def _signal_blob(brief: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(str(brief.get("reply_mode") or ""))

    athlete_ctx = brief.get("athlete_context")
    if isinstance(athlete_ctx, dict):
        parts.append(str(athlete_ctx.get("constraints_summary") or ""))

    delivery = brief.get("delivery_context")
    if isinstance(delivery, dict):
        parts.append(str(delivery.get("inbound_body") or ""))

    decision = brief.get("decision_context")
    if isinstance(decision, dict):
        parts.append(str(decision.get("risk_flag") or ""))
        if decision.get("clarification_needed"):
            parts.append("clarification_needed")
        rh = decision.get("risk_recent_history")
        if isinstance(rh, list):
            parts.extend(str(x) for x in rh)
        elif rh is not None:
            parts.append(str(rh))

    return " ".join(parts).lower()


_SETBACK_PHRASES = (
    "setback",
    "pain",
    "ache",
    "sore",
    "flare",
    "niggle",
    "injured",
    "injury",
    "rebuild",
    "tendon",
    "strain",
    "sprain",
    "comeback",
    "quiet again",
    "flare-up",
    "backing off",
    "dialing back",
)
_SETBACK_HISTORY_TOKENS = frozenset({"yellow", "red"})

_ILLNESS_PHRASES = (
    "illness",
    "sick",
    "cold",
    "fever",
    "low energy",
    "fatigue",
    "exhausted",
    "rundown",
    "run down",
    "flu",
    "covid",
    "under the weather",
    "not feeling great",
    "wiped",
    "drained",
    "body feels off",
    "coming down with",
)

_TRAVEL_PHRASES = (
    "travel",
    "trip",
    "hotel",
    "limited equipment",
    "schedule disruption",
    "poor sleep",
    "jet lag",
    "timezone",
    "time zone",
    "away from home",
    "chaotic",
    "crazy week",
    "schedule blew up",
    "limited time",
    "conference",
    "late nights",
    "red-eye",
)

_INTENSITY_PHRASES = (
    "intensity",
    "tempo",
    "threshold",
    "strides",
    "workout return",
    "quality return",
    "intervals",
    "interval session",
    "pickup",
    "pickups",
    "quality",
    "progression run",
    "hard session",
    "faster work",
)

_PRESCRIPTION_PHRASES = (
    "next week",
    "plan the week",
    "week look like",
    "map the week",
    "session plan",
    "long run",
    "tempo",
    "threshold",
    "interval",
    "strides",
    "mileage",
    "weekly volume",
    "deload",
    "build week",
    "sessions per week",
    "prescribe",
    "progression",
    " volume",
    "easy day",
    "easy days",
    "easy run",
    "quality session",
)

_READING_PHRASES = ("book", "read", "resource")
_RECOMMEND_TRIGGER = "recommend"


def _has_setback_signals(blob: str, brief: dict[str, Any]) -> bool:
    if any(p in blob for p in _SETBACK_PHRASES):
        return True
    decision = brief.get("decision_context")
    if not isinstance(decision, dict):
        return False
    rh = decision.get("risk_recent_history")
    if not isinstance(rh, list):
        return False
    for entry in rh:
        token = str(entry).strip().lower()
        if token in _SETBACK_HISTORY_TOKENS:
            return True
    return False


def _has_illness_signals(blob: str) -> bool:
    return any(p in blob for p in _ILLNESS_PHRASES)


def _has_travel_signals(blob: str) -> bool:
    return any(p in blob for p in _TRAVEL_PHRASES)


def _has_intensity_signals(blob: str) -> bool:
    if any(p in blob for p in _INTENSITY_PHRASES):
        return True
    return "steady" in blob and any(
        token in blob
        for token in ("session", "work", "workout", "run", "next week", "plan")
    )


def _needs_common_failures_backstop(
    brief: dict[str, Any], blob: str, *, setback: bool, intensity: bool
) -> bool:
    decision = brief.get("decision_context")
    if isinstance(decision, dict):
        if decision.get("clarification_needed"):
            return True
        flag = str(decision.get("risk_flag") or "").strip().lower()
        if flag in {"yellow", "red"}:
            return True
    if setback or intensity:
        return True
    if "clarification" in blob:
        return True
    return False


def _has_prescription_signals(blob: str) -> bool:
    return any(p in blob for p in _PRESCRIPTION_PHRASES)


def _wants_running_reading_recommendations(blob: str) -> bool:
    if _RECOMMEND_TRIGGER not in blob:
        return False
    return any(p in blob for p in _READING_PHRASES)


def select_doctrine_files(brief: dict[str, Any]) -> list[str]:
    """Deterministic doctrine paths for this response brief (ordered, deduped)."""
    blob = _signal_blob(brief)
    sport = _resolve_sport_from_brief(brief)
    setback = _has_setback_signals(blob, brief)
    intensity = _has_intensity_signals(blob)

    selected: list[str] = list(CORE_UNIVERSAL_FILES)

    for key, path in OPTIONAL_UNIVERSAL_ORDER:
        if key == "return_from_setback" and setback:
            selected.append(path)
        elif key == "illness_and_low_energy" and _has_illness_signals(blob):
            selected.append(path)
        elif key == "travel_and_disruption" and _has_travel_signals(blob):
            selected.append(path)
        elif key == "intensity_reintroduction" and intensity:
            selected.append(path)
        elif key == "common_coaching_failures" and _needs_common_failures_backstop(
            brief, blob, setback=setback, intensity=intensity
        ):
            selected.append(path)

    if sport == "running":
        for key, path in RUNNING_OPTIONAL_ORDER:
            if key == "methodology":
                selected.append(path)
            elif key == "injury_return_patterns" and setback:
                selected.append(path)
            elif key == "common_prescription_errors" and _has_prescription_signals(blob):
                selected.append(path)
            elif key == "recommendations" and _wants_running_reading_recommendations(blob):
                selected.append(path)

    seen: set[str] = set()
    ordered: list[str] = []
    for p in selected:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def build_doctrine_context_for_brief(brief: dict[str, Any]) -> str:
    """Assemble doctrine text for the strategist using selective loading."""
    paths = select_doctrine_files(brief)
    sections = [_load(p) for p in paths]
    return "\n\n".join(sections)


def list_loaded_files(brief: dict[str, Any]) -> list[str]:
    """Doctrine paths that would load for this brief (same order as context)."""
    return select_doctrine_files(brief)
