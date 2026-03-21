"""Typed contracts and JSON schema for the unified memory refresh workflow (AM3)."""

from typing import Any, Dict, List, Optional, TypedDict


class UnifiedMemoryRefreshInput(TypedDict):
    current_backbone: Dict[str, Any]
    current_context_notes: List[Dict[str, Any]]
    current_continuity: Optional[Dict[str, Any]]
    interaction_context: Dict[str, Any]


class UnifiedBackboneOutput(TypedDict):
    primary_goal: Optional[str]
    weekly_structure: Optional[str]
    hard_constraints: Optional[str]
    training_preferences: Optional[str]


class UnifiedContextNoteOutput(TypedDict):
    label: str
    summary: str


class UnifiedContinuityOutput(TypedDict):
    summary: str
    last_recommendation: str
    open_loops: List[str]


class UnifiedMemoryRefreshOutput(TypedDict):
    backbone: UnifiedBackboneOutput
    context_notes: List[UnifiedContextNoteOutput]
    continuity: UnifiedContinuityOutput


JSON_SCHEMA_NAME = "memory_refresh_unified"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["backbone", "context_notes", "continuity"],
    "properties": {
        "backbone": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "primary_goal",
                "weekly_structure",
                "hard_constraints",
                "training_preferences",
            ],
            "properties": {
                "primary_goal": {"type": ["string", "null"]},
                "weekly_structure": {"type": ["string", "null"]},
                "hard_constraints": {"type": ["string", "null"]},
                "training_preferences": {"type": ["string", "null"]},
            },
        },
        "context_notes": {
            "type": "array",
            "maxItems": 4,
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["label", "summary"],
                "properties": {
                    "label": {"type": "string", "minLength": 1},
                    "summary": {"type": "string", "minLength": 1},
                },
            },
        },
        "continuity": {
            "type": "object",
            "additionalProperties": False,
            "required": ["summary", "last_recommendation", "open_loops"],
            "properties": {
                "summary": {"type": "string", "minLength": 1},
                "last_recommendation": {"type": "string", "minLength": 1},
                "open_loops": {
                    "type": "array",
                    "maxItems": 3,
                    "items": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}
