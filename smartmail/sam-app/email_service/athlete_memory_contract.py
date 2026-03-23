"""
Contract helpers for athlete memory artifacts.

AM2 uses a durable-fact model:
- **Durable facts** (typed, keyed): goal, constraint, schedule, preference, other.
  Each fact has a stable identity (memory_note_id) and system-derived canonical key.
- **Continuity summary**: short-lived coaching state for the next 1-2 exchanges.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AthleteMemoryContractError(ValueError):
    """Raised when an athlete-memory artifact violates the contract."""


MAX_OPEN_LOOPS = 3

# ---------------------------------------------------------------------------
# Durable fact constants
# ---------------------------------------------------------------------------

VALID_FACT_TYPES = {"goal", "constraint", "schedule", "preference", "other"}
VALID_IMPORTANCE_LEVELS = {"high", "medium"}
HIGH_IMPORTANCE_TYPES = {"goal", "constraint"}
LOW_VALUE_FACT_TYPES = {"other", "preference"}
MAX_ACTIVE_FACTS = 7
ADMISSION_THRESHOLD = 5  # reject new low-value facts when active count >= this


def _require_non_empty_str(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AthleteMemoryContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_unix_timestamp(field_name: str, value: Any) -> int:
    if isinstance(value, Decimal):
        if value != int(value):
            raise AthleteMemoryContractError(
                f"{field_name} must be a whole number (got Decimal with fractional part)"
            )
        value = int(value)
    if not isinstance(value, int) or value <= 0:
        raise AthleteMemoryContractError(
            f"{field_name} must be a positive unix timestamp"
        )
    return value


def format_unix_timestamp_for_prompt(epoch: int) -> str:
    """Converts a unix epoch to a human-readable UTC string for LLM prompts."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


# ---------------------------------------------------------------------------
# Fact key normalization
# ---------------------------------------------------------------------------

def normalize_fact_key(fact_type: str, raw_key: str) -> str:
    """Derives a canonical fact key from type + raw key string.

    Returns ``"{fact_type}:{slug}"`` where slug is lowercased, stripped,
    whitespace collapsed to hyphens, non-alphanumeric (except hyphens)
    removed, and truncated to 64 chars.
    """
    if fact_type not in VALID_FACT_TYPES:
        raise AthleteMemoryContractError(f"invalid fact_type: {fact_type!r}")
    slug = raw_key.strip().lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    slug = slug[:64]
    if not slug:
        raise AthleteMemoryContractError(
            f"fact_key normalizes to empty string from raw key: {raw_key!r}"
        )
    return f"{fact_type}:{slug}"


# ---------------------------------------------------------------------------
# Durable fact dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class DurableFact:
    """A typed, keyed durable memory fact."""

    memory_note_id: str
    fact_type: str
    fact_key: str
    summary: str
    importance: str
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
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_confirmed_at": self.last_confirmed_at,
        }

    @classmethod
    def from_dict(cls, payload: Any, *, index: int = 0) -> "DurableFact":
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError(f"memory_notes[{index}] must be a dict")
        prefix = f"memory_notes[{index}]"
        memory_note_id = _require_non_empty_str(f"{prefix}.memory_note_id", payload.get("memory_note_id"))
        fact_type = _require_non_empty_str(f"{prefix}.fact_type", payload.get("fact_type"))
        if fact_type not in VALID_FACT_TYPES:
            raise AthleteMemoryContractError(
                f"{prefix}.fact_type must be one of {sorted(VALID_FACT_TYPES)}, got {fact_type!r}"
            )
        fact_key = _require_non_empty_str(f"{prefix}.fact_key", payload.get("fact_key"))
        summary = _require_non_empty_str(f"{prefix}.summary", payload.get("summary"))
        importance = _require_non_empty_str(f"{prefix}.importance", payload.get("importance"))
        if importance not in VALID_IMPORTANCE_LEVELS:
            raise AthleteMemoryContractError(
                f"{prefix}.importance must be one of {sorted(VALID_IMPORTANCE_LEVELS)}, got {importance!r}"
            )
        created_at = _validate_unix_timestamp(f"{prefix}.created_at", payload.get("created_at"))
        updated_at = _validate_unix_timestamp(f"{prefix}.updated_at", payload.get("updated_at"))
        last_confirmed_at = _validate_unix_timestamp(f"{prefix}.last_confirmed_at", payload.get("last_confirmed_at"))
        return cls(
            memory_note_id=memory_note_id,
            fact_type=fact_type,
            fact_key=fact_key,
            summary=summary,
            importance=importance,
            created_at=created_at,
            updated_at=updated_at,
            last_confirmed_at=last_confirmed_at,
        )


def validate_memory_notes(notes: Any) -> List[Dict[str, Any]]:
    """Validates a list of persisted DurableFact dicts.

    Rejects duplicate memory_note_id and duplicate canonical keys.
    Returns normalized list of dicts.
    """
    if not isinstance(notes, list):
        raise AthleteMemoryContractError("memory_notes must be a list")
    normalized: List[Dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_keys: set[str] = set()
    for idx, raw_note in enumerate(notes):
        fact = DurableFact.from_dict(raw_note, index=idx)
        if fact.memory_note_id in seen_ids:
            raise AthleteMemoryContractError(
                f"memory_notes contains duplicate memory_note_id: {fact.memory_note_id!r}"
            )
        seen_ids.add(fact.memory_note_id)
        if fact.fact_key in seen_keys:
            raise AthleteMemoryContractError(
                f"memory_notes contains duplicate fact_key: {fact.fact_key!r}"
            )
        seen_keys.add(fact.fact_key)
        normalized.append(fact.to_dict())
    return normalized


# ---------------------------------------------------------------------------
# Continuity summary
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContinuitySummary:
    """Short-lived coaching state for the next 1-2 exchanges."""

    summary: str
    last_recommendation: str
    open_loops: list
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "last_recommendation": self.last_recommendation,
            "open_loops": list(self.open_loops),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ContinuitySummary":
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError("continuity_summary must be a dict")
        required = {"summary", "last_recommendation", "open_loops", "updated_at"}
        missing = sorted(required - set(payload.keys()))
        if missing:
            raise AthleteMemoryContractError(
                f"continuity_summary is missing required fields: {', '.join(missing)}"
            )
        return cls(
            summary=_require_non_empty_str("continuity_summary.summary", payload["summary"]),
            last_recommendation=_require_non_empty_str(
                "continuity_summary.last_recommendation", payload["last_recommendation"]
            ),
            open_loops=_validate_open_loops(payload["open_loops"]),
            updated_at=_validate_unix_timestamp("continuity_summary.updated_at", payload["updated_at"]),
        )


def _validate_open_loops(value: Any) -> List[str]:
    if not isinstance(value, list):
        raise AthleteMemoryContractError("continuity_summary.open_loops must be a list")
    if len(value) > MAX_OPEN_LOOPS:
        raise AthleteMemoryContractError(
            f"continuity_summary.open_loops may have at most {MAX_OPEN_LOOPS} items"
        )
    normalized: List[str] = []
    for idx, item in enumerate(value):
        normalized.append(_require_non_empty_str(f"continuity_summary.open_loops[{idx}]", item))
    return normalized


def validate_continuity_summary(summary: ContinuitySummary) -> None:
    """Validates a ContinuitySummary instance."""
    _require_non_empty_str("continuity_summary.summary", summary.summary)
    _require_non_empty_str("continuity_summary.last_recommendation", summary.last_recommendation)
    _validate_open_loops(summary.open_loops)
    _validate_unix_timestamp("continuity_summary.updated_at", summary.updated_at)
