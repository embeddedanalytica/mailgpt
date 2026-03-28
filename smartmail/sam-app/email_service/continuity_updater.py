"""
Deterministic continuity state updater.

Takes a prior ContinuityState + a ContinuityRecommendation and returns the
next ContinuityState.  Pure function — no persistence, no LLM calls.

Guardrails are narrow and do not replace doctrine-based judgment:
- Reject invalid enums / malformed dates
- Reject impossible event-date transitions (past dates)
- Veto premature phase_shift (weeks_in_current_block < 2) unless
  reason indicates injury, setback, return-from-break, or new event context
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Optional

from continuity_state_contract import (
    ContinuityState,
    ContinuityStateContractError,
)
from continuity_recommendation_contract import (
    ContinuityRecommendation,
    ContinuityRecommendationError,
)

logger = logging.getLogger(__name__)

# Keywords in transition_reason that bypass the minimum-tenure guardrail.
_BYPASS_KEYWORDS = frozenset({
    "injury", "injured",
    "setback",
    "return", "returning",
    "illness", "sick",
    "new event", "new race", "signed up",
    "break",
})


def _reason_bypasses_guardrail(reason: str) -> bool:
    """Check if the transition reason indicates a situation that bypasses
    the minimum-tenure guardrail for phase_shift."""
    reason_lower = reason.lower()
    return any(kw in reason_lower for kw in _BYPASS_KEYWORDS)


def _is_past_event_date(event_date_str: Optional[str], today: date) -> bool:
    """Return True if the event date is strictly in the past."""
    if event_date_str is None:
        return False
    try:
        event = date.fromisoformat(event_date_str)
        return event < today
    except (ValueError, TypeError):
        return True  # unparseable → treat as invalid


def apply_continuity_recommendation(
    prior_state: ContinuityState,
    recommendation: Optional[ContinuityRecommendation],
    today: date,
) -> ContinuityState:
    """Apply a continuity recommendation to produce the next state.

    Args:
        prior_state: The current persisted continuity state.
        recommendation: The LLM's recommendation, or None if absent/failed.
        today: Current date for timestamp updates and guardrail checks.

    Returns:
        The next ContinuityState.  On any error or missing recommendation,
        returns prior_state unchanged.
    """
    if recommendation is None:
        return prior_state

    # Validate the recommendation (may already be validated, but be safe)
    try:
        rec = ContinuityRecommendation.from_dict(recommendation.to_dict())
    except ContinuityRecommendationError as exc:
        logger.warning("Invalid continuity recommendation, keeping prior state: %s", exc)
        return prior_state

    action = rec.recommended_transition_action
    today_iso = today.isoformat()

    # --- keep: preserve everything, only event date may update ---
    if action == "keep":
        new_event_date = rec.recommended_goal_event_date
        if new_event_date is not None and _is_past_event_date(new_event_date, today):
            new_event_date = prior_state.goal_event_date  # reject past date
        elif new_event_date is None:
            new_event_date = prior_state.goal_event_date

        if new_event_date == prior_state.goal_event_date:
            return prior_state  # truly no change

        # Auto-promote horizon to event when keep introduces an event date
        horizon = prior_state.goal_horizon_type
        if new_event_date is not None and prior_state.goal_event_date is None:
            horizon = "event"

        return ContinuityState(
            goal_horizon_type=horizon,
            current_phase=prior_state.current_phase,
            current_block_focus=prior_state.current_block_focus,
            block_started_at=prior_state.block_started_at,
            goal_event_date=new_event_date,
            last_transition_reason=prior_state.last_transition_reason,
            last_transition_date=prior_state.last_transition_date,
        )

    # --- Shared validation for mutating actions ---

    # Reject past event dates
    if rec.recommended_goal_event_date is not None and _is_past_event_date(
        rec.recommended_goal_event_date, today
    ):
        logger.warning(
            "Continuity recommendation has past event date %s, keeping prior state",
            rec.recommended_goal_event_date,
        )
        return prior_state

    # Guardrail: veto premature phase_shift
    if action == "phase_shift":
        weeks = prior_state.weeks_in_current_block(today)
        if weeks < 2 and not _reason_bypasses_guardrail(rec.recommended_transition_reason):
            logger.warning(
                "Vetoing premature phase_shift: weeks_in_current_block=%d, reason=%r",
                weeks,
                rec.recommended_transition_reason,
            )
            return prior_state

    # --- Apply mutating actions ---
    new_event_date = rec.recommended_goal_event_date
    if new_event_date is None:
        new_event_date = prior_state.goal_event_date

    if action == "focus_shift":
        return ContinuityState(
            goal_horizon_type=rec.recommended_goal_horizon_type,
            current_phase=prior_state.current_phase,
            current_block_focus=rec.recommended_block_focus,
            block_started_at=today_iso,
            goal_event_date=new_event_date,
            last_transition_reason=rec.recommended_transition_reason,
            last_transition_date=today_iso,
        )

    if action == "phase_shift":
        return ContinuityState(
            goal_horizon_type=rec.recommended_goal_horizon_type,
            current_phase=rec.recommended_phase,
            current_block_focus=rec.recommended_block_focus,
            block_started_at=today_iso,
            goal_event_date=new_event_date,
            last_transition_reason=rec.recommended_transition_reason,
            last_transition_date=today_iso,
        )

    if action == "reset_block":
        return ContinuityState(
            goal_horizon_type=rec.recommended_goal_horizon_type,
            current_phase=rec.recommended_phase,
            current_block_focus=rec.recommended_block_focus,
            block_started_at=today_iso,
            goal_event_date=new_event_date,
            last_transition_reason=rec.recommended_transition_reason,
            last_transition_date=today_iso,
        )

    # Unknown action — should not happen given enum validation, but be safe
    logger.warning("Unknown transition action %r, keeping prior state", action)
    return prior_state
