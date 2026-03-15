"""
Contract helpers for athlete memory artifacts.

AM2 keeps durable facts on ``memory_notes`` and short-lived continuity on
``continuity_summary``.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
import re
from typing import Any, Dict, Iterable, List


ALLOWED_FACT_TYPES = {
    "goal",
    "constraint",
    "schedule",
    "preference",
    "other",
}
ALLOWED_MEMORY_NOTE_IMPORTANCE = {"high", "medium", "low"}
ALLOWED_MEMORY_NOTE_STATUS = {"active", "inactive"}
MAX_MEMORY_NOTES = 7
MAX_OPEN_LOOPS = 3

FACT_KEY_REFERENCE_EXAMPLES = [
    {
        "label": "hard schedule constraint",
        "fact_type": "constraint",
        "summary": "Weekday sessions need to finish before 7am.",
        "canonical_fact_key": "weekday_before_7am_cutoff",
    },
    {
        "label": "recurring anchor",
        "fact_type": "schedule",
        "summary": "Sunday is usually the long-run anchor.",
        "canonical_fact_key": "sunday_long_run_anchor",
    },
    {
        "label": "durable reversal",
        "fact_type": "schedule",
        "summary": "Saturday is open again for key training.",
        "canonical_fact_key": "saturday_availability",
    },
    {
        "label": "meaningful flexibility",
        "fact_type": "schedule",
        "summary": "Bike commuting twice a week is now realistic.",
        "canonical_fact_key": "bike_commute_volume",
    },
    {
        "label": "routine noise should be rejected",
        "fact_type": "other",
        "summary": "Tuesday tempo felt smooth this week.",
        "canonical_fact_key": "tuesday_tempo_felt_smooth_this_week",
    },
]

_MEMORY_NOTE_FIELDS = {
    "memory_note_id",
    "fact_type",
    "fact_key",
    "summary",
    "importance",
    "status",
    "created_at",
    "updated_at",
    "last_confirmed_at",
}
_CONTINUITY_SUMMARY_FIELDS = {
    "summary",
    "last_recommendation",
    "open_loops",
    "updated_at",
}

_FACT_KEY_ALLOWED_CHARS = re.compile(r"[^a-z0-9:_]+")
_FACT_KEY_UNDERSCORES = re.compile(r"_+")


class AthleteMemoryContractError(ValueError):
    """Raised when athlete memory contract validation fails."""


def _validate_payload_fields(
    *,
    payload: Dict[str, Any],
    object_name: str,
    required_fields: set[str],
) -> None:
    missing_fields = sorted(required_fields - set(payload.keys()))
    if missing_fields:
        raise AthleteMemoryContractError(
            f"{object_name} is missing required fields: {', '.join(missing_fields)}"
        )


def _require_non_empty_str(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AthleteMemoryContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_unix_timestamp(field_name: str, value: Any) -> int:
    if isinstance(value, bool):
        raise AthleteMemoryContractError(f"{field_name} must be a positive unix timestamp")
    if isinstance(value, Decimal):
        if value != value.to_integral_value():
            raise AthleteMemoryContractError(f"{field_name} must be a positive unix timestamp")
        value = int(value)
    if not isinstance(value, int) or value <= 0:
        raise AthleteMemoryContractError(f"{field_name} must be a positive unix timestamp")
    return int(value)


def format_unix_timestamp_for_prompt(value: Any) -> str:
    timestamp = _validate_unix_timestamp("timestamp", value)
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).strftime("%Y-%m-%d")


def normalize_fact_key(value: Any) -> str:
    raw = _require_non_empty_str("fact_key", value).lower()
    normalized = _FACT_KEY_ALLOWED_CHARS.sub("_", raw)
    normalized = normalized.strip("_:")
    if ":" in normalized:
        fact_type, _, remainder = normalized.partition(":")
        fact_type = _FACT_KEY_UNDERSCORES.sub("_", fact_type).strip("_")
        remainder = _FACT_KEY_UNDERSCORES.sub("_", remainder).strip("_")
        if fact_type in ALLOWED_FACT_TYPES and remainder:
            normalized = remainder
        else:
            normalized = _FACT_KEY_UNDERSCORES.sub("_", normalized).strip("_")
    else:
        normalized = _FACT_KEY_UNDERSCORES.sub("_", normalized).strip("_")
    if not normalized:
        raise AthleteMemoryContractError("fact_key must contain letters or numbers")
    return normalized


def _validate_fact_type(value: Any) -> str:
    fact_type = _require_non_empty_str("fact_type", value).lower()
    if fact_type not in ALLOWED_FACT_TYPES:
        raise AthleteMemoryContractError(
            f"fact_type must be one of {sorted(ALLOWED_FACT_TYPES)}"
        )
    return fact_type


def _validate_importance(value: Any) -> str:
    importance = _require_non_empty_str("importance", value).lower()
    if importance not in ALLOWED_MEMORY_NOTE_IMPORTANCE:
        raise AthleteMemoryContractError(
            f"importance must be one of {sorted(ALLOWED_MEMORY_NOTE_IMPORTANCE)}"
        )
    return importance


def _validate_status(value: Any) -> str:
    status = _require_non_empty_str("status", value).lower()
    if status not in ALLOWED_MEMORY_NOTE_STATUS:
        raise AthleteMemoryContractError(
            f"status must be one of {sorted(ALLOWED_MEMORY_NOTE_STATUS)}"
        )
    return status


@dataclass(frozen=True)
class MemoryNote:
    memory_note_id: int
    fact_type: str
    fact_key: str
    summary: str
    importance: str
    status: str
    created_at: int
    updated_at: int
    last_confirmed_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory_note_id": self.memory_note_id,
            "fact_type": self.fact_type,
            "fact_key": self.fact_key,
            "summary": self.summary,
            "importance": self.importance,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_confirmed_at": self.last_confirmed_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "MemoryNote":
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError("memory_note must be a dict")
        _validate_payload_fields(
            payload=payload,
            object_name="memory_note",
            required_fields=_MEMORY_NOTE_FIELDS,
        )
        note = cls(
            memory_note_id=payload.get("memory_note_id"),
            fact_type=payload.get("fact_type"),
            fact_key=payload.get("fact_key"),
            summary=payload.get("summary"),
            importance=payload.get("importance"),
            status=payload.get("status"),
            created_at=payload.get("created_at"),
            updated_at=payload.get("updated_at"),
            last_confirmed_at=payload.get("last_confirmed_at"),
        )
        validate_memory_note(note)
        return note


def validate_memory_note(note: MemoryNote) -> None:
    if not isinstance(note.memory_note_id, int) or note.memory_note_id < 1:
        raise AthleteMemoryContractError("memory_note_id must be an integer >= 1")

    object.__setattr__(note, "fact_type", _validate_fact_type(note.fact_type))
    object.__setattr__(note, "fact_key", normalize_fact_key(note.fact_key))
    object.__setattr__(note, "summary", _require_non_empty_str("summary", note.summary))
    object.__setattr__(note, "importance", _validate_importance(note.importance))
    object.__setattr__(note, "status", _validate_status(note.status))
    object.__setattr__(note, "created_at", _validate_unix_timestamp("created_at", note.created_at))
    object.__setattr__(note, "updated_at", _validate_unix_timestamp("updated_at", note.updated_at))
    object.__setattr__(
        note,
        "last_confirmed_at",
        _validate_unix_timestamp("last_confirmed_at", note.last_confirmed_at),
    )
    if note.updated_at < note.created_at:
        raise AthleteMemoryContractError("updated_at must be >= created_at")
    if note.last_confirmed_at < note.created_at:
        raise AthleteMemoryContractError("last_confirmed_at must be >= created_at")


def filter_active_memory_notes(memory_notes: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    active_notes: List[Dict[str, Any]] = []
    for raw_note in memory_notes:
        note = MemoryNote.from_dict(raw_note).to_dict()
        if note["status"] == "active":
            active_notes.append(note)
    return active_notes


def validate_memory_note_list(memory_notes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    if not isinstance(memory_notes, list):
        raise AthleteMemoryContractError("memory_notes must be a list")

    normalized_notes: List[Dict[str, Any]] = []
    seen_ids = set()
    active_fact_keys = set()
    active_count = 0
    for idx, raw_note in enumerate(memory_notes):
        try:
            normalized = MemoryNote.from_dict(raw_note).to_dict()
        except AthleteMemoryContractError as exc:
            raise AthleteMemoryContractError(f"memory_notes[{idx}] invalid: {exc}") from exc

        note_id = normalized["memory_note_id"]
        if note_id in seen_ids:
            raise AthleteMemoryContractError("memory_notes contains duplicate memory_note_id values")
        seen_ids.add(note_id)

        if normalized["status"] == "active":
            active_count += 1
            fact_key = normalized["fact_key"]
            if fact_key in active_fact_keys:
                raise AthleteMemoryContractError(
                    "memory_notes contains duplicate active fact_key values"
                )
            active_fact_keys.add(fact_key)

        normalized_notes.append(normalized)

    if active_count > MAX_MEMORY_NOTES:
        raise AthleteMemoryContractError(
            f"memory_notes may contain at most {MAX_MEMORY_NOTES} active notes"
        )
    return normalized_notes


@dataclass(frozen=True)
class ContinuitySummary:
    summary: str
    last_recommendation: str
    open_loops: List[str]
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "last_recommendation": self.last_recommendation,
            "open_loops": list(self.open_loops),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ContinuitySummary":
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError("continuity_summary must be a dict")
        _validate_payload_fields(
            payload=payload,
            object_name="continuity_summary",
            required_fields=_CONTINUITY_SUMMARY_FIELDS,
        )
        summary = cls(
            summary=payload.get("summary"),
            last_recommendation=payload.get("last_recommendation"),
            open_loops=payload.get("open_loops"),
            updated_at=payload.get("updated_at"),
        )
        validate_continuity_summary(summary)
        return summary


def validate_continuity_summary(summary: ContinuitySummary) -> None:
    object.__setattr__(summary, "summary", _require_non_empty_str("summary", summary.summary))
    object.__setattr__(
        summary,
        "last_recommendation",
        _require_non_empty_str("last_recommendation", summary.last_recommendation),
    )
    if not isinstance(summary.open_loops, list):
        raise AthleteMemoryContractError("open_loops must be a list")
    if len(summary.open_loops) > MAX_OPEN_LOOPS:
        raise AthleteMemoryContractError(
            f"open_loops may contain at most {MAX_OPEN_LOOPS} items"
        )
    normalized_open_loops: List[str] = []
    for idx, item in enumerate(summary.open_loops):
        normalized_open_loops.append(_require_non_empty_str(f"open_loops[{idx}]", item))
    object.__setattr__(summary, "open_loops", normalized_open_loops)
    object.__setattr__(summary, "updated_at", _validate_unix_timestamp("updated_at", summary.updated_at))
