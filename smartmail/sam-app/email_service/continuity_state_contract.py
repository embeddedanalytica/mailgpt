"""
Contract for the continuity_state object.

continuity_state preserves coaching continuity across turns.  It lives as a
top-level attribute on coach_profiles and is the single source of truth for
where an athlete sits in their current training block/phase arc.

Deterministic code owns persistence, validation, and derivation.
The doctrine-backed LLM owns the coaching meaning (transitions, focus).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from datetime import date, datetime
from enum import Enum
from typing import Any, Dict, Optional


class ContinuityStateContractError(ValueError):
    """Raised when a continuity_state artifact violates the contract."""


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class GoalHorizonType(str, Enum):
    EVENT = "event"
    GENERAL_FITNESS = "general_fitness"
    PERFORMANCE_BLOCK = "performance_block"
    RETURN_TO_TRAINING = "return_to_training"


class BlockFocus(str, Enum):
    INITIAL_ASSESSMENT = "initial_assessment"
    REBUILD_CONSISTENCY = "rebuild_consistency"
    CONTROLLED_LOAD_PROGRESSION = "controlled_load_progression"
    MAINTAIN_FITNESS = "maintain_fitness"
    MAINTAIN_THROUGH_CONSTRAINTS = "maintain_through_constraints"
    EVENT_SPECIFIC_BUILD = "event_specific_build"
    PEAK_FOR_EVENT = "peak_for_event"
    TAPER_FOR_EVENT = "taper_for_event"
    RETURN_SAFELY = "return_safely"
    RECOVERY_DELOAD = "recovery_deload"


VALID_GOAL_HORIZON_TYPES = {e.value for e in GoalHorizonType}
VALID_BLOCK_FOCUSES = {e.value for e in BlockFocus}


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def _require_non_empty_str(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ContinuityStateContractError(
            f"{field_name} must be a non-empty string"
        )
    return value.strip()


def _require_iso_date(field_name: str, value: Any) -> str:
    """Validate and normalize an ISO date string (YYYY-MM-DD)."""
    if not isinstance(value, str):
        raise ContinuityStateContractError(
            f"{field_name} must be an ISO date string, got {type(value).__name__}"
        )
    value = value.strip()
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        raise ContinuityStateContractError(
            f"{field_name} must be a valid ISO date (YYYY-MM-DD), got {value!r}"
        )
    return value


def _optional_iso_date(field_name: str, value: Any) -> Optional[str]:
    """Validate an optional ISO date — None is allowed."""
    if value is None:
        return None
    return _require_iso_date(field_name, value)


def _require_enum(field_name: str, value: Any, valid_values: set) -> str:
    if not isinstance(value, str):
        raise ContinuityStateContractError(
            f"{field_name} must be a string, got {type(value).__name__}"
        )
    value = value.strip().lower()
    if value not in valid_values:
        raise ContinuityStateContractError(
            f"{field_name} must be one of {sorted(valid_values)}, got {value!r}"
        )
    return value


# ---------------------------------------------------------------------------
# ContinuityState dataclass
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ContinuityState:
    goal_horizon_type: str       # GoalHorizonType enum value
    current_phase: str           # Canonical phase label
    current_block_focus: str     # BlockFocus enum value
    block_started_at: str        # ISO date
    goal_event_date: Optional[str]  # ISO date or None
    last_transition_reason: str  # Short description
    last_transition_date: str    # ISO date

    # -- Derivation helpers (pure, no side effects) -------------------------

    def weeks_in_current_block(self, today: date) -> int:
        """Number of complete weeks since block_started_at, minimum 1."""
        started = date.fromisoformat(self.block_started_at)
        days = (today - started).days
        if days < 0:
            return 1
        return max(1, math.ceil((days + 1) / 7))

    def weeks_until_event(self, today: date) -> Optional[int]:
        """Weeks until goal_event_date, or None if no event."""
        if self.goal_event_date is None:
            return None
        event = date.fromisoformat(self.goal_event_date)
        days = (event - today).days
        if days <= 0:
            return 0
        return math.ceil(days / 7)

    def to_continuity_context(self, today: date) -> Dict[str, Any]:
        """Build the bounded context dict consumed by downstream prompts."""
        ctx: Dict[str, Any] = {
            "goal_horizon_type": self.goal_horizon_type,
            "current_phase": self.current_phase,
            "current_block_focus": self.current_block_focus,
            "weeks_in_current_block": self.weeks_in_current_block(today),
            "last_transition_reason": self.last_transition_reason,
        }
        wue = self.weeks_until_event(today)
        if wue is not None:
            ctx["weeks_until_event"] = wue
            ctx["goal_event_date"] = self.goal_event_date
        return ctx

    # -- Serialization ------------------------------------------------------

    def to_dict(self) -> Dict[str, Any]:
        return {
            "goal_horizon_type": self.goal_horizon_type,
            "current_phase": self.current_phase,
            "current_block_focus": self.current_block_focus,
            "block_started_at": self.block_started_at,
            "goal_event_date": self.goal_event_date,
            "last_transition_reason": self.last_transition_reason,
            "last_transition_date": self.last_transition_date,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ContinuityState":
        """Validate and construct from a dict. Raises ContinuityStateContractError."""
        if not isinstance(payload, dict):
            raise ContinuityStateContractError(
                f"Expected dict, got {type(payload).__name__}"
            )

        required = {
            "goal_horizon_type", "current_phase", "current_block_focus",
            "block_started_at", "last_transition_reason", "last_transition_date",
        }
        missing = required - set(payload.keys())
        if missing:
            raise ContinuityStateContractError(
                f"Missing required fields: {sorted(missing)}"
            )

        return cls(
            goal_horizon_type=_require_enum(
                "goal_horizon_type", payload["goal_horizon_type"],
                VALID_GOAL_HORIZON_TYPES,
            ),
            current_phase=_require_non_empty_str(
                "current_phase", payload["current_phase"],
            ),
            current_block_focus=_require_enum(
                "current_block_focus", payload["current_block_focus"],
                VALID_BLOCK_FOCUSES,
            ),
            block_started_at=_require_iso_date(
                "block_started_at", payload["block_started_at"],
            ),
            goal_event_date=_optional_iso_date(
                "goal_event_date", payload.get("goal_event_date"),
            ),
            last_transition_reason=_require_non_empty_str(
                "last_transition_reason", payload["last_transition_reason"],
            ),
            last_transition_date=_require_iso_date(
                "last_transition_date", payload["last_transition_date"],
            ),
        )
