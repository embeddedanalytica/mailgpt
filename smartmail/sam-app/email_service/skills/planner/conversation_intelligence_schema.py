"""JSON schema for conversation-intelligence classification workflow."""

JSON_SCHEMA_NAME = "conversation_intelligence_response"

JSON_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["intent", "complexity_score"],
    "properties": {
        "intent": {
            "type": "string",
            "enum": [
                "check_in",
                "question",
                "plan_change_request",
                "milestone_update",
                "off_topic",
                "safety_concern",
                "availability_update",
            ],
        },
        "complexity_score": {"type": "integer", "minimum": 1, "maximum": 5},
    },
}
