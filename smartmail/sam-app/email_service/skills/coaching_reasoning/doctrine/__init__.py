"""Coaching doctrine loader — assembles sport-specific coaching knowledge."""

from pathlib import Path
from typing import Optional

from .manifest import GENERAL_FILES, SPORT_ALIASES, SPORT_FILES, UNIVERSAL_FILES

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


def build_doctrine_context(sport: Optional[str] = None) -> str:
    """Returns assembled doctrine text for the given sport.

    Loads: universal/* + sport-specific/* (if matched) + general/*
    A runner gets running doctrine only. A cyclist gets cycling only. No cross-loading.
    """
    sections = [_load(f) for f in UNIVERSAL_FILES]
    sport_key = _resolve_sport(sport)
    if sport_key and sport_key in SPORT_FILES:
        sections.extend(_load(f) for f in SPORT_FILES[sport_key])
    sections.extend(_load(f) for f in GENERAL_FILES)
    return "\n\n".join(sections)


def list_loaded_files(sport: Optional[str] = None) -> list[str]:
    """Returns which doctrine files would be loaded for a given sport (for testing/debugging)."""
    files = list(UNIVERSAL_FILES)
    sport_key = _resolve_sport(sport)
    if sport_key and sport_key in SPORT_FILES:
        files.extend(SPORT_FILES[sport_key])
    files.extend(GENERAL_FILES)
    return files
