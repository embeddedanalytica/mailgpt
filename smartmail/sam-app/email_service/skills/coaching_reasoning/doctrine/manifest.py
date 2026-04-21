"""Doctrine file registry and sport aliases.

Selection is driven by `select_doctrine_files` in the package `__init__`; this module
holds paths and stable ordering only.
"""

from typing import Final

# Always injected into coaching-strategist prompts
CORE_UNIVERSAL_FILES: Final[list[str]] = [
    "universal/core.md",
    "universal/authority_and_override_rules.md",
]

# Universal doctrine loaded only when selection rules fire (stable merge order)
OPTIONAL_UNIVERSAL_ORDER: Final[list[tuple[str, str]]] = [
    ("relationship_arc", "universal/relationship_arc.md"),
    ("return_from_setback", "universal/return_from_setback.md"),
    ("illness_and_low_energy", "universal/illness_and_low_energy.md"),
    ("travel_and_disruption", "universal/travel_and_disruption.md"),
    ("intensity_reintroduction", "universal/intensity_reintroduction.md"),
    ("session_report_evaluation", "universal/session_report_evaluation.md"),
    ("common_coaching_failures", "universal/common_coaching_failures.md"),
]

# Running-specific (stable merge order)
RUNNING_OPTIONAL_ORDER: Final[list[tuple[str, str]]] = [
    ("methodology", "running/methodology.md"),
    ("injury_return_patterns", "running/injury_return_patterns.md"),
    ("common_prescription_errors", "running/common_prescription_errors.md"),
    ("recommendations", "running/recommendations.md"),
]

# Legacy / unused by selective strategist load — still shipped and checked by manifest tests
LEGACY_UNIVERSAL_FILES: Final[list[str]] = [
    "universal/recovery_and_risk.md",
]

GENERAL_FILES: Final[list[str]] = [
    "general/recommendations.md",
]

# Sport-specific files — loaded ONLY when the athlete's sport matches
SPORT_FILES: dict[str, list[str]] = {
    "running": [path for _, path in RUNNING_OPTIONAL_ORDER],
}

# Maps athlete profile sport values → canonical sport key
SPORT_ALIASES: dict[str, str] = {
    "running": "running",
    "marathon": "running",
    "half marathon": "running",
    "5k": "running",
    "10k": "running",
    "trail running": "running",
    "trail": "running",
    "ultramarathon": "running",
}


def all_registered_doctrine_paths() -> list[str]:
    """Every on-disk doctrine path the repo owns (integrity tests)."""
    paths = list(CORE_UNIVERSAL_FILES)
    paths.extend(path for _, path in OPTIONAL_UNIVERSAL_ORDER)
    paths.extend(path for _, path in RUNNING_OPTIONAL_ORDER)
    paths.extend(LEGACY_UNIVERSAL_FILES)
    paths.extend(GENERAL_FILES)
    return sorted(set(paths))
