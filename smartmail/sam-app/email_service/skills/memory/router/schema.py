"""Typed contracts and JSON schema for the memory refresh routing workflow."""

from typing import Any, Dict, TypedDict


ALLOWED_ROUTES = {"long_term", "short_term", "both", "neither"}


class MemoryRouterInput(TypedDict):
    prior_memory_notes: list[Dict[str, Any]]
    prior_continuity_summary: Dict[str, Any] | None
    latest_interaction_context: Dict[str, Any]


class MemoryRouterOutput(TypedDict):
    route: str
    model_name: str
    resolution_source: str
    reason_resolution: str


JSON_SCHEMA_NAME = "memory_refresh_router"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["route"],
    "properties": {
        "route": {
            "type": "string",
            "enum": sorted(ALLOWED_ROUTES),
        }
    },
}
