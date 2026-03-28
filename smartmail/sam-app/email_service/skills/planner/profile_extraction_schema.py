"""JSON schema for profile-extraction workflow."""

JSON_SCHEMA_NAME = "profile_extraction_response"

_CONSTRAINT_ITEM = {
    "type": "object",
    "additionalProperties": False,
    "required": ["type", "summary", "severity", "active"],
    "properties": {
        "type": {"type": "string"},
        "summary": {"type": "string"},
        "severity": {"type": "string"},
        "active": {"type": "boolean"},
    },
}

_NULLABLE_NONEMPTY_LIST = {
    "anyOf": [
        {"type": "null"},
        {
            "type": "array",
            "minItems": 1,
            "items": _CONSTRAINT_ITEM,
        },
    ],
}

_INJURY_STATUS = {
    "anyOf": [
        {"type": "null"},
        {
            "type": "object",
            "additionalProperties": False,
            "required": ["has_injuries"],
            "properties": {
                "has_injuries": {"type": "boolean"},
            },
        },
    ],
}

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "primary_goal",
        "time_availability",
        "experience_level",
        "experience_level_note",
        "constraints",
        "injury_status",
        "injury_constraints",
    ],
    "properties": {
        "primary_goal": {"type": ["string", "null"]},
        "time_availability": {
            "type": ["object", "null"],
            "anyOf": [
                {"type": "null"},
                {
                    "type": "object",
                    "additionalProperties": False,
                    "required": ["sessions_per_week", "daily_windows", "availability_notes"],
                    "properties": {
                        "sessions_per_week": {"type": ["string", "null"]},
                        "daily_windows": {
                            "anyOf": [
                                {"type": "null"},
                                {
                                    "type": "array",
                                    "items": {"type": "string"},
                                },
                            ],
                        },
                        "availability_notes": {"type": ["string", "null"]},
                    },
                },
            ],
        },
        "experience_level": {
            "type": "string",
            "enum": ["beginner", "intermediate", "advanced", "unknown", ""],
        },
        "experience_level_note": {"type": ["string", "null"]},
        "constraints": {
            "type": ["array", "null"],
            "anyOf": [
                {"type": "null"},
                {
                    "type": "array",
                    "items": _CONSTRAINT_ITEM,
                },
            ],
        },
        "injury_status": _INJURY_STATUS,
        "injury_constraints": _NULLABLE_NONEMPTY_LIST,
    },
}
