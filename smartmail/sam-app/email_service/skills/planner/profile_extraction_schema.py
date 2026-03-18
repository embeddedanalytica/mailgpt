"""JSON schema for profile-extraction workflow."""

JSON_SCHEMA_NAME = "profile_extraction_response"

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "primary_goal",
        "time_availability",
        "experience_level",
        "experience_level_note",
        "constraints",
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
                    "required": ["sessions_per_week", "hours_per_week"],
                    "properties": {
                        "sessions_per_week": {"type": ["integer", "null"], "minimum": 0},
                        "hours_per_week": {"type": ["number", "null"], "minimum": 0},
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
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["type", "summary", "severity", "active"],
                        "properties": {
                            "type": {"type": "string"},
                            "summary": {"type": "string"},
                            "severity": {"type": "string"},
                            "active": {"type": "boolean"},
                        },
                    },
                },
            ],
        },
    },
}
