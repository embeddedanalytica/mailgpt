"""Sport → doctrine file mapping. Add a sport by adding an entry here + its files."""

# Files under universal/ — always loaded for every athlete
UNIVERSAL_FILES = [
    "universal/core.md",
    "universal/recovery_and_risk.md",
    "universal/relationship_arc.md",
]

# Files under general/ — always loaded
GENERAL_FILES = [
    "general/recommendations.md",
]

# Sport-specific files — loaded ONLY when the athlete's sport matches
SPORT_FILES: dict[str, list[str]] = {
    "running": [
        "running/methodology.md",
        "running/recommendations.md",
    ],
    # Future:
    # "cycling": ["cycling/methodology.md", "cycling/recommendations.md"],
    # "swimming": ["swimming/methodology.md", "swimming/recommendations.md"],
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
    # "cycling": "cycling",
    # "road cycling": "cycling",
    # "mountain biking": "cycling",
}
