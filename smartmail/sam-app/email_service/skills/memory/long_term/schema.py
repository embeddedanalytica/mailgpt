"""Typed contracts and JSON schema for the long-term memory refresh workflow."""

from typing import Any, Dict, List, TypedDict


class LongTermUpsertCandidate(TypedDict):
    action: str
    memory_note_id: int
    fact_type: str
    fact_key: str
    summary: str
    importance: str
    evidence_source: str
    evidence_strength: str


class LongTermConfirmCandidate(TypedDict):
    action: str
    memory_note_id: int
    evidence_source: str
    evidence_strength: str


class LongTermRetireCandidate(TypedDict):
    action: str
    memory_note_id: int
    reason: str
    evidence_source: str
    evidence_strength: str


class LongTermMemoryCandidate(TypedDict, total=False):
    action: str
    memory_note_id: int
    fact_type: str
    fact_key: str
    summary: str
    importance: str
    evidence_source: str
    evidence_strength: str
    reason: str


class LongTermMemoryConsolidationOp(TypedDict):
    action: str
    source_memory_note_id: int
    target_memory_note_id: int
    summary: str


class LongTermMemoryRefreshInput(TypedDict):
    prior_memory_notes: List[Dict[str, Any]]
    latest_interaction_context: Dict[str, Any]


class LongTermMemoryRefreshOutput(TypedDict):
    candidates: List[LongTermMemoryCandidate]
    consolidation_ops: List[LongTermMemoryConsolidationOp]


JSON_SCHEMA_NAME = "memory_refresh_long_term"
JSON_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["candidates", "consolidation_ops"],
    "properties": {
        "candidates": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": [
                    "action",
                    "memory_note_id",
                    "fact_type",
                    "fact_key",
                    "summary",
                    "importance",
                    "reason",
                    "evidence_source",
                    "evidence_strength",
                ],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["upsert", "confirm", "retire"],
                    },
                    "memory_note_id": {"type": "integer", "minimum": 0},
                    "fact_type": {
                        "type": "string",
                        "enum": ["goal", "constraint", "schedule", "preference", "other", ""],
                    },
                    "fact_key": {"type": "string"},
                    "summary": {"type": "string"},
                    "importance": {
                        "type": "string",
                        "enum": ["high", "medium", "low", ""],
                    },
                    "reason": {"type": "string"},
                    "evidence_source": {
                        "type": "string",
                        "enum": [
                            "athlete_email",
                            "profile_update",
                            "manual_activity",
                            "rule_engine_state",
                        ],
                    },
                    "evidence_strength": {
                        "type": "string",
                        "enum": ["explicit", "strong_inference", "weak_inference"],
                    },
                },
            },
        },
        "consolidation_ops": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["action", "source_memory_note_id", "target_memory_note_id", "summary"],
                "properties": {
                    "action": {"type": "string", "enum": ["merge_into"]},
                    "source_memory_note_id": {"type": "integer", "minimum": 1},
                    "target_memory_note_id": {"type": "integer", "minimum": 1},
                    "summary": {"type": "string", "minLength": 1},
                },
            },
        },
    },
}
