"""Response-generation workflow contracts and JSON schema."""

from typing import Any, Dict, TypedDict


class ResponseGenerationBrief(TypedDict):
    reply_mode: str
    athlete_context: Dict[str, Any]
    decision_context: Dict[str, Any]
    validated_plan: Dict[str, Any]
    delivery_context: Dict[str, Any]
    memory_context: Dict[str, Any]


class FinalEmailResponsePayload(TypedDict):
    final_email_body: str


JSON_SCHEMA_NAME = "response_generation_final_email"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["final_email_body"],
    "properties": {
        "final_email_body": {"type": "string", "minLength": 1},
    },
}
