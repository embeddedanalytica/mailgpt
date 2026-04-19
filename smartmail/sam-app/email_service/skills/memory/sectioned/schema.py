"""JSON schema for sectioned candidate memory refresh."""

from typing import Any, Dict, List, Optional, TypedDict


class SectionedCandidateMemoryRefreshInput(TypedDict, total=False):
    current_memory: Dict[str, Any]
    current_continuity: Optional[Dict[str, Any]]
    interaction_context: Dict[str, Any]


class SectionedCandidateOp(TypedDict, total=False):
    action: str
    target_id: Optional[str]
    section: Optional[str]
    subtype: Optional[str]
    fact_key: Optional[str]
    summary: Optional[str]
    supersedes_fact_keys: Optional[List[str]]
    evidence_source: str
    evidence_strength: str
    retirement_reason: Optional[str]


class SectionedContinuityOutput(TypedDict):
    summary: str
    last_recommendation: str
    open_loops: List[str]


class SectionedCandidateMemoryRefreshOutput(TypedDict):
    candidates: List[SectionedCandidateOp]
    continuity: SectionedContinuityOutput


JSON_SCHEMA_NAME = "sectioned_memory_refresh_candidates"
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
                    "section",
                    "subtype",
                    "fact_key",
                    "summary",
                    "supersedes_fact_keys",
                    "evidence_source",
                    "evidence_strength",
                    "retirement_reason",
                ],
                "properties": {
                    "action": {
                        "type": "string",
                        "enum": ["upsert", "confirm", "retire"],
                    },
                    "target_id": {"type": ["string", "null"]},
                    "section": {
                        "type": ["string", "null"],
                        "enum": [
                            "goal",
                            "constraint",
                            "schedule_anchor",
                            "preference",
                            "context",
                            None,
                        ],
                    },
                    "subtype": {"type": ["string", "null"]},
                    "fact_key": {"type": ["string", "null"]},
                    "summary": {"type": ["string", "null"]},
                    "supersedes_fact_keys": {
                        "type": ["array", "null"],
                        "items": {"type": "string", "minLength": 1},
                    },
                    "evidence_source": {
                        "type": "string",
                        "enum": ["athlete_email", "profile_update", "manual_activity", "rule_engine_state"],
                    },
                    "evidence_strength": {
                        "type": "string",
                        "enum": ["explicit", "strong_inference", "weak_inference"],
                    },
                    "retirement_reason": {"type": ["string", "null"]},
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
                    "description": "Only unanswered questions or action items the coach asked the athlete. Empty array if none pending.",
                    "maxItems": 3,
                    "items": {"type": "string", "minLength": 1, "maxLength": 300},
                },
            },
        },
    },
}
