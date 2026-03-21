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
                "coaching",
                "question",
                "off_topic",
                "safety_concern",
            ],
        },
        "complexity_score": {"type": "integer", "minimum": 1, "maximum": 5},
    },
}
