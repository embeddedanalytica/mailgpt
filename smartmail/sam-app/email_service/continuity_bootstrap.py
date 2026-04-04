"""
Deterministic bootstrap for continuity_state.

Creates the initial continuity_state on an athlete's first coaching turn,
or when existing state is missing/corrupt.  Pure function — no persistence,
no LLM calls.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, Optional

from continuity_state_contract import (
    BlockFocus,
    ContinuityState,
    GoalHorizonType,
)


def _parse_event_date(profile: Dict[str, Any], today_date: date) -> Optional[str]:
    """Extract a valid future-or-today ISO date string from the profile."""
    raw = profile.get("event_date")
    if raw is None:
        return None
    raw_str = str(raw).strip()
    if not raw_str:
        return None
    try:
        parsed = datetime.strptime(raw_str, "%Y-%m-%d").date()
        if parsed < today_date:
            return None
        return raw_str
    except ValueError:
        return None


def _is_return_context(rule_engine_phase: str, profile: Dict[str, Any]) -> bool:
    """Detect whether the athlete is in a return-from-break/injury context."""
    if rule_engine_phase == "return_to_training":
        return True
    for key in (
        "return_to_training",
        "newly_returning",
        "returning_from_break",
        "hard_return_context",
    ):
        val = profile.get(key)
        if val is True or str(val).strip().lower() in ("true", "yes", "1"):
            return True
    injury = profile.get("injury_status", "")
    if isinstance(injury, str) and injury.strip().lower() in ("active", "recovering"):
        return True
    return False


def bootstrap_continuity_state(
    profile: Dict[str, Any],
    rule_engine_phase: str,
    today_date: date,
) -> ContinuityState:
    """Create the initial continuity_state for an athlete.

    Args:
        profile: The athlete's coach_profiles record.
        rule_engine_phase: Phase derived by the rule engine for this turn.
        today_date: Current date.

    Returns:
        A validated ContinuityState with safe defaults.
    """
    event_date = _parse_event_date(profile, today_date)

    if event_date is not None:
        goal_horizon = GoalHorizonType.EVENT.value
    else:
        goal_horizon = GoalHorizonType.GENERAL_FITNESS.value

    if _is_return_context(rule_engine_phase, profile):
        block_focus = BlockFocus.RETURN_SAFELY.value
    else:
        block_focus = BlockFocus.INITIAL_ASSESSMENT.value

    today_iso = today_date.isoformat()

    return ContinuityState(
        goal_horizon_type=goal_horizon,
        current_phase=rule_engine_phase or "base",
        current_block_focus=block_focus,
        block_started_at=today_iso,
        goal_event_date=event_date,
        last_transition_reason="bootstrap_initial_state",
        last_transition_date=today_iso,
    )
