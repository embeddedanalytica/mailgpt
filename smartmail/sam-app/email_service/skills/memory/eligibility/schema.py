"""Typed contracts and JSON schema for the memory refresh eligibility workflow."""

from typing import Any, Dict, TypedDict


ALLOWED_REASONS = {
    "durable_context_changed",
    "coaching_recommendation",
    "coaching_state_changed",
    "greeting_or_acknowledgement",
    "clarification_only",
    "no_meaningful_change",
}


class MemoryRefreshEligibilityInput(TypedDict):
    interaction_context: Dict[str, Any]


class MemoryRefreshEligibilityOutput(TypedDict):
    should_refresh: bool
    reason: str
    model_name: str
    resolution_source: str
    reason_resolution: str


JSON_SCHEMA_NAME = "memory_refresh_eligibility"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["should_refresh", "reason"],
    "properties": {
        "should_refresh": {"type": "boolean"},
        "reason": {
            "type": "string",
            "enum": sorted(ALLOWED_REASONS),
        },
    },
}
