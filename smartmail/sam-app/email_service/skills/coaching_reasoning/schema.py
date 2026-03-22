"""CoachingDirective JSON schema for the coaching-reasoning workflow."""

from typing import Any, Dict

JSON_SCHEMA_NAME = "coaching_directive"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "opening",
        "main_message",
        "content_plan",
        "avoid",
        "tone",
        "recommend_material",
        "rationale",
    ],
    "properties": {
        "opening": {
            "type": "string",
            "minLength": 1,
            "description": "How to open the email — specific to this athlete's situation.",
        },
        "main_message": {
            "type": "string",
            "minLength": 1,
            "description": "Core coaching message for this turn.",
        },
        "content_plan": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "minItems": 1,
            "description": "Ordered list of content items to include in the email.",
        },
        "avoid": {
            "type": "array",
            "items": {"type": "string", "minLength": 1},
            "description": "Things the writer should NOT say or do.",
        },
        "tone": {
            "type": "string",
            "minLength": 1,
            "description": "Tone guidance for the writer.",
        },
        "recommend_material": {
            "type": ["string", "null"],
            "description": "Book or video recommendation if contextually relevant, otherwise null.",
        },
        "rationale": {
            "type": "string",
            "minLength": 1,
            "description": "Internal reasoning — for eval/logging only, NOT forwarded to the writer.",
        },
    },
}
