"""Unit tests for continuity_state_contract and continuity_bootstrap."""

import unittest
from datetime import date

from continuity_state_contract import (
    BlockFocus,
    ContinuityState,
    ContinuityStateContractError,
    GoalHorizonType,
    VALID_BLOCK_FOCUSES,
    VALID_GOAL_HORIZON_TYPES,
)
from continuity_bootstrap import bootstrap_continuity_state


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _valid_state_dict(**overrides):
    base = {
        "goal_horizon_type": "event",
        "current_phase": "base",
        "current_block_focus": "controlled_load_progression",
        "block_started_at": "2026-03-01",
        "goal_event_date": "2026-06-15",
        "last_transition_reason": "bootstrap_initial_state",
        "last_transition_date": "2026-03-01",
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# ContinuityState contract tests
# ---------------------------------------------------------------------------

class TestContinuityStateFromDict(unittest.TestCase):

    def test_valid_round_trip(self):
        d = _valid_state_dict()
        state = ContinuityState.from_dict(d)
        self.assertEqual(state.to_dict(), d)

    def test_all_goal_horizon_types(self):
        for ght in VALID_GOAL_HORIZON_TYPES:
            d = _valid_state_dict(goal_horizon_type=ght)
            state = ContinuityState.from_dict(d)
            self.assertEqual(state.goal_horizon_type, ght)

    def test_all_block_focuses(self):
        for bf in VALID_BLOCK_FOCUSES:
            d = _valid_state_dict(current_block_focus=bf)
            state = ContinuityState.from_dict(d)
            self.assertEqual(state.current_block_focus, bf)

    def test_no_event_date(self):
        d = _valid_state_dict(goal_event_date=None)
        state = ContinuityState.from_dict(d)
        self.assertIsNone(state.goal_event_date)

    def test_missing_required_field(self):
        d = _valid_state_dict()
        del d["current_phase"]
        with self.assertRaises(ContinuityStateContractError) as ctx:
            ContinuityState.from_dict(d)
        self.assertIn("current_phase", str(ctx.exception))

    def test_invalid_goal_horizon_type(self):
        d = _valid_state_dict(goal_horizon_type="marathon")
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict(d)

    def test_invalid_block_focus(self):
        d = _valid_state_dict(current_block_focus="go_hard")
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict(d)

    def test_invalid_date_format(self):
        d = _valid_state_dict(block_started_at="March 1, 2026")
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict(d)

    def test_invalid_event_date_format(self):
        d = _valid_state_dict(goal_event_date="not-a-date")
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict(d)

    def test_empty_transition_reason(self):
        d = _valid_state_dict(last_transition_reason="  ")
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict(d)

    def test_non_dict_input(self):
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict("not a dict")

    def test_non_string_phase(self):
        d = _valid_state_dict(current_phase=42)
        with self.assertRaises(ContinuityStateContractError):
            ContinuityState.from_dict(d)


# ---------------------------------------------------------------------------
# Derivation helpers
# ---------------------------------------------------------------------------

class TestWeeksInCurrentBlock(unittest.TestCase):

    def test_same_day(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(block_started_at="2026-03-25")
        )
        self.assertEqual(state.weeks_in_current_block(date(2026, 3, 25)), 1)

    def test_day_six(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(block_started_at="2026-03-19")
        )
        self.assertEqual(state.weeks_in_current_block(date(2026, 3, 25)), 1)

    def test_day_seven(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(block_started_at="2026-03-18")
        )
        self.assertEqual(state.weeks_in_current_block(date(2026, 3, 25)), 2)

    def test_multi_week(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(block_started_at="2026-01-01")
        )
        # Jan 1 to Mar 25 = 83 days → ceil(84/7) = 12
        self.assertEqual(state.weeks_in_current_block(date(2026, 3, 25)), 12)

    def test_future_start_returns_one(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(block_started_at="2026-04-01")
        )
        self.assertEqual(state.weeks_in_current_block(date(2026, 3, 25)), 1)


class TestWeeksUntilEvent(unittest.TestCase):

    def test_no_event(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(goal_event_date=None)
        )
        self.assertIsNone(state.weeks_until_event(date(2026, 3, 25)))

    def test_event_same_day(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(goal_event_date="2026-03-25")
        )
        self.assertEqual(state.weeks_until_event(date(2026, 3, 25)), 0)

    def test_event_past(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(goal_event_date="2026-03-20")
        )
        self.assertEqual(state.weeks_until_event(date(2026, 3, 25)), 0)

    def test_event_one_week_out(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(goal_event_date="2026-04-01")
        )
        self.assertEqual(state.weeks_until_event(date(2026, 3, 25)), 1)

    def test_event_twelve_weeks_out(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(goal_event_date="2026-06-15")
        )
        # Mar 25 to Jun 15 = 82 days → ceil(82/7) = 12
        self.assertEqual(state.weeks_until_event(date(2026, 3, 25)), 12)


class TestContinuityContext(unittest.TestCase):

    def test_with_event(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(
                block_started_at="2026-03-01",
                goal_event_date="2026-06-15",
            )
        )
        ctx = state.to_continuity_context(date(2026, 3, 25))
        self.assertEqual(ctx["goal_horizon_type"], "event")
        self.assertEqual(ctx["current_phase"], "base")
        self.assertEqual(ctx["current_block_focus"], "controlled_load_progression")
        self.assertIn("weeks_in_current_block", ctx)
        self.assertIn("weeks_until_event", ctx)
        self.assertIn("goal_event_date", ctx)

    def test_without_event(self):
        state = ContinuityState.from_dict(
            _valid_state_dict(
                goal_horizon_type="general_fitness",
                goal_event_date=None,
            )
        )
        ctx = state.to_continuity_context(date(2026, 3, 25))
        self.assertNotIn("weeks_until_event", ctx)
        self.assertNotIn("goal_event_date", ctx)


# ---------------------------------------------------------------------------
# Bootstrap tests
# ---------------------------------------------------------------------------

class TestBootstrapContinuityState(unittest.TestCase):

    def test_event_athlete(self):
        profile = {"event_date": "2026-06-15"}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.goal_horizon_type, "event")
        self.assertEqual(state.goal_event_date, "2026-06-15")
        self.assertEqual(state.current_phase, "base")
        self.assertEqual(state.current_block_focus, "initial_assessment")
        self.assertEqual(state.block_started_at, "2026-03-25")
        self.assertEqual(state.last_transition_reason, "bootstrap_initial_state")

    def test_general_fitness_athlete(self):
        profile = {}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.goal_horizon_type, "general_fitness")
        self.assertIsNone(state.goal_event_date)
        self.assertEqual(state.current_block_focus, "initial_assessment")

    def test_return_to_training_phase(self):
        profile = {}
        state = bootstrap_continuity_state(
            profile, "return_to_training", date(2026, 3, 25)
        )
        self.assertEqual(state.current_block_focus, "return_safely")
        self.assertEqual(state.current_phase, "return_to_training")

    def test_newly_returning_flag(self):
        profile = {"newly_returning": True}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.current_block_focus, "return_safely")

    def test_active_injury_status(self):
        profile = {"injury_status": "active"}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.current_block_focus, "return_safely")

    def test_recovering_injury_status(self):
        profile = {"injury_status": "recovering"}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.current_block_focus, "return_safely")

    def test_invalid_event_date_ignored(self):
        profile = {"event_date": "not-a-date"}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.goal_horizon_type, "general_fitness")
        self.assertIsNone(state.goal_event_date)

    def test_empty_event_date_ignored(self):
        profile = {"event_date": ""}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.goal_horizon_type, "general_fitness")
        self.assertIsNone(state.goal_event_date)

    def test_past_event_date_ignored(self):
        profile = {"event_date": "2026-03-24"}
        state = bootstrap_continuity_state(profile, "base", date(2026, 3, 25))
        self.assertEqual(state.goal_horizon_type, "general_fitness")
        self.assertIsNone(state.goal_event_date)

    def test_result_is_valid_continuity_state(self):
        """Bootstrap output must pass from_dict validation."""
        profile = {"event_date": "2026-06-15"}
        state = bootstrap_continuity_state(profile, "build", date(2026, 3, 25))
        roundtrip = ContinuityState.from_dict(state.to_dict())
        self.assertEqual(roundtrip, state)

    def test_empty_phase_defaults_to_base(self):
        profile = {}
        state = bootstrap_continuity_state(profile, "", date(2026, 3, 25))
        self.assertEqual(state.current_phase, "base")


if __name__ == "__main__":
    unittest.main()
