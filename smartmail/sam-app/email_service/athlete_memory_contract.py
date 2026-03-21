"""
Contract helpers for athlete memory artifacts.

AM3 uses a two-tier memory model:
- **Backbone slots** (4 fixed keys): primary_goal, weekly_structure,
  hard_constraints, training_preferences — always present, structurally
  protected from eviction.
- **Context notes** (max 4 free-form): secondary durable facts.
- **Continuity summary**: short-lived coaching state for the next 1-2
  exchanges.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


class AthleteMemoryContractError(ValueError):
    """Raised when an athlete-memory artifact violates the contract."""


MAX_OPEN_LOOPS = 3


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


# ---------------------------------------------------------------------------
# Backbone + context model
# ---------------------------------------------------------------------------

BACKBONE_SLOT_KEYS = [
    "primary_goal",
    "weekly_structure",
    "hard_constraints",
    "training_preferences",
]

MAX_CONTEXT_NOTES = 4


@dataclass(frozen=True)
class BackboneSlot:
    """A single backbone memory slot. Nullable when not yet populated."""

    summary: Optional[str]
    updated_at: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Any, *, slot_name: str = "backbone_slot") -> "BackboneSlot":
        if payload is None:
            return cls(summary=None, updated_at=None)
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError(f"{slot_name} must be a dict or null")
        summary = payload.get("summary")
        updated_at = payload.get("updated_at")
        if summary is not None:
            summary = _require_non_empty_str(f"{slot_name}.summary", summary)
        if updated_at is not None:
            updated_at = _validate_unix_timestamp(f"{slot_name}.updated_at", updated_at)
        # Both must be present together or both null.
        if (summary is None) != (updated_at is None):
            raise AthleteMemoryContractError(
                f"{slot_name}: summary and updated_at must both be present or both null"
            )
        return cls(summary=summary, updated_at=updated_at)


@dataclass(frozen=True)
class BackboneSlots:
    """The four protected backbone memory slots."""

    primary_goal: BackboneSlot
    weekly_structure: BackboneSlot
    hard_constraints: BackboneSlot
    training_preferences: BackboneSlot

    def to_dict(self) -> Dict[str, Any]:
        return {
            "primary_goal": self.primary_goal.to_dict(),
            "weekly_structure": self.weekly_structure.to_dict(),
            "hard_constraints": self.hard_constraints.to_dict(),
            "training_preferences": self.training_preferences.to_dict(),
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "BackboneSlots":
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError("backbone must be a dict")
        return cls(
            primary_goal=BackboneSlot.from_dict(
                payload.get("primary_goal"), slot_name="backbone.primary_goal",
            ),
            weekly_structure=BackboneSlot.from_dict(
                payload.get("weekly_structure"), slot_name="backbone.weekly_structure",
            ),
            hard_constraints=BackboneSlot.from_dict(
                payload.get("hard_constraints"), slot_name="backbone.hard_constraints",
            ),
            training_preferences=BackboneSlot.from_dict(
                payload.get("training_preferences"), slot_name="backbone.training_preferences",
            ),
        )

    @classmethod
    def empty(cls) -> "BackboneSlots":
        """Returns backbone with all slots unpopulated."""
        empty_slot = BackboneSlot(summary=None, updated_at=None)
        return cls(
            primary_goal=empty_slot,
            weekly_structure=empty_slot,
            hard_constraints=empty_slot,
            training_preferences=empty_slot,
        )


@dataclass(frozen=True)
class ContextNote:
    """A free-form durable context note (secondary to backbone)."""

    label: str
    summary: str
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "label": self.label,
            "summary": self.summary,
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Any, *, index: int = 0) -> "ContextNote":
        if not isinstance(payload, dict):
            raise AthleteMemoryContractError(f"context_notes[{index}] must be a dict")
        return cls(
            label=_require_non_empty_str(f"context_notes[{index}].label", payload.get("label")),
            summary=_require_non_empty_str(f"context_notes[{index}].summary", payload.get("summary")),
            updated_at=_validate_unix_timestamp(f"context_notes[{index}].updated_at", payload.get("updated_at")),
        )


def validate_backbone_slots(payload: Any) -> BackboneSlots:
    """Validates and returns a BackboneSlots instance from a raw dict."""
    return BackboneSlots.from_dict(payload)


def validate_context_note_list(context_notes: Any) -> List[Dict[str, Any]]:
    """Validates a list of context notes and returns normalized dicts."""
    if not isinstance(context_notes, list):
        raise AthleteMemoryContractError("context_notes must be a list")
    if len(context_notes) > MAX_CONTEXT_NOTES:
        raise AthleteMemoryContractError(
            f"context_notes may contain at most {MAX_CONTEXT_NOTES} items"
        )
    normalized: List[Dict[str, Any]] = []
    seen_labels: set[str] = set()
    for idx, raw_note in enumerate(context_notes):
        note = ContextNote.from_dict(raw_note, index=idx)
        label_key = note.label.lower()
        if label_key in seen_labels:
            raise AthleteMemoryContractError(
                f"context_notes contains duplicate label: {note.label!r}"
            )
        seen_labels.add(label_key)
        normalized.append(note.to_dict())
    return normalized


