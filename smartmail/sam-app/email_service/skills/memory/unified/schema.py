"""Typed contracts and JSON schema for the candidate-operation memory refresh (AM2)."""

from typing import Any, Dict, List, Optional, TypedDict


class CandidateMemoryRefreshInput(TypedDict):
    current_memory_notes: List[Dict[str, Any]]
    current_continuity: Optional[Dict[str, Any]]
    interaction_context: Dict[str, Any]


class CandidateOp(TypedDict, total=False):
    action: str                # required: upsert | confirm | retire
    target_id: str             # existing memory_note_id (required for confirm/retire, optional for upsert)
    fact_type: str             # required for new upsert; forbidden on upsert-with-target_id
    fact_key: str              # required for new upsert; forbidden on upsert-with-target_id
    summary: str               # required for upsert; optional for confirm/retire
    importance: str            # required for new upsert; optional for upsert-with-target_id
    evidence_source: str       # required: athlete_email | profile_update | manual_activity | rule_engine_state
    evidence_strength: str     # required: explicit | strong_inference | weak_inference


class ContinuityOutput(TypedDict):
    summary: str
    last_recommendation: str
    open_loops: List[str]


class CandidateMemoryRefreshOutput(TypedDict):
    candidates: List[CandidateOp]
    continuity: ContinuityOutput


JSON_SCHEMA_NAME = "memory_refresh_candidates"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates", "continuity"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "action",
                    "target_id",
                    "fact_type",
                    "fact_key",
                    "summary",
                    "importance",
                    "evidence_source",
                    "evidence_strength",
                ],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["upsert", "confirm", "retire"],
                    },
                    "target_id": {"type": ["string", "null"]},
                    "fact_type": {
                        "type": ["string", "null"],
                        "enum": ["goal", "constraint", "schedule", "preference", "other", None],
                    },
                    "fact_key": {"type": ["string", "null"]},
                    "summary": {"type": ["string", "null"]},
                    "importance": {
                        "type": ["string", "null"],
                        "enum": ["high", "medium", None],
                    },
                    "evidence_source": {
                        "type": "string",
                        "enum": ["athlete_email", "profile_update", "manual_activity", "rule_engine_state"],
                    },
                    "evidence_strength": {
                        "type": "string",
                        "enum": ["explicit", "strong_inference", "weak_inference"],
                    },
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
