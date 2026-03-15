"""Typed contracts and JSON schema for the short-term memory refresh workflow."""

from typing import Any, Dict, Optional, TypedDict


class ShortTermMemoryRefreshInput(TypedDict):
    prior_continuity_summary: Optional[Dict[str, Any]]
    latest_interaction_context: Dict[str, Any]


class ShortTermMemoryRefreshOutput(TypedDict):
    continuity_summary: Dict[str, Any]


JSON_SCHEMA_NAME = "memory_refresh_short_term"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["continuity_summary"],
    "properties": {
        "continuity_summary": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "last_recommendation", "open_loops", "updated_at"],
            "properties": {
                "summary": {"type": "string", "minLength": 1},
                "last_recommendation": {"type": "string", "minLength": 1},
                "open_loops": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {"type": "string", "minLength": 1},
                },
                "updated_at": {"type": "integer", "minimum": 1},
            },
        }
    },
}
