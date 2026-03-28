"""
Contract for the continuity_recommendation emitted by coaching_reasoning.

The LLM recommends continuity transitions; deterministic code validates and
applies them.  All fields are required (including on ``keep``) to avoid
conditional omission logic in the LLM output.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from continuity_state_contract import (
    ContinuityStateContractError,
    VALID_BLOCK_FOCUSES,
    VALID_GOAL_HORIZON_TYPES,
    _optional_iso_date,
    _require_enum,
    _require_non_empty_str,
)


class ContinuityRecommendationError(ContinuityStateContractError):
    """Raised when a continuity_recommendation violates the contract."""


VALID_TRANSITION_ACTIONS = {"keep", "focus_shift", "phase_shift", "reset_block"}


@dataclass(frozen=True)
class ContinuityRecommendation:
    recommended_goal_horizon_type: str    # GoalHorizonType enum value
    recommended_phase: str                # Canonical phase label
    recommended_block_focus: str          # BlockFocus enum value
    recommended_transition_action: str    # keep | focus_shift | phase_shift | reset_block
    recommended_transition_reason: str    # Short description
    recommended_goal_event_date: Optional[str]  # ISO date or None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommended_goal_horizon_type": self.recommended_goal_horizon_type,
            "recommended_phase": self.recommended_phase,
            "recommended_block_focus": self.recommended_block_focus,
            "recommended_transition_action": self.recommended_transition_action,
            "recommended_transition_reason": self.recommended_transition_reason,
            "recommended_goal_event_date": self.recommended_goal_event_date,
        }

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ContinuityRecommendation":
        """Validate and construct from a dict.

        Raises ContinuityRecommendationError on invalid input.
        """
        if not isinstance(payload, dict):
            raise ContinuityRecommendationError(
                f"Expected dict, got {type(payload).__name__}"
            )

        required = {
            "recommended_goal_horizon_type",
            "recommended_phase",
            "recommended_block_focus",
            "recommended_transition_action",
            "recommended_transition_reason",
        }
        missing = required - set(payload.keys())
        if missing:
            raise ContinuityRecommendationError(
                f"Missing required fields: {sorted(missing)}"
            )

        try:
            return cls(
                recommended_goal_horizon_type=_require_enum(
                    "recommended_goal_horizon_type",
                    payload["recommended_goal_horizon_type"],
                    VALID_GOAL_HORIZON_TYPES,
                ),
                recommended_phase=_require_non_empty_str(
                    "recommended_phase",
                    payload["recommended_phase"],
                ),
                recommended_block_focus=_require_enum(
                    "recommended_block_focus",
                    payload["recommended_block_focus"],
                    VALID_BLOCK_FOCUSES,
                ),
                recommended_transition_action=_require_enum(
                    "recommended_transition_action",
                    payload["recommended_transition_action"],
                    VALID_TRANSITION_ACTIONS,
                ),
                recommended_transition_reason=_require_non_empty_str(
                    "recommended_transition_reason",
                    payload["recommended_transition_reason"],
                ),
                recommended_goal_event_date=_optional_iso_date(
                    "recommended_goal_event_date",
                    payload.get("recommended_goal_event_date"),
                ),
            )
        except ContinuityStateContractError as exc:
            raise ContinuityRecommendationError(str(exc)) from exc
