"""Unit tests for continuity_recommendation_contract and continuity_updater."""

import unittest
from datetime import date

from continuity_state_contract import ContinuityState
from continuity_recommendation_contract import (
    ContinuityRecommendation,
    ContinuityRecommendationError,
    VALID_TRANSITION_ACTIONS,
)
from continuity_updater import apply_continuity_recommendation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _base_state(**overrides):
    base = {
        "goal_horizon_type": "general_fitness",
        "current_phase": "base",
        "current_block_focus": "controlled_load_progression",
        "block_started_at": "2026-02-01",
        "goal_event_date": None,
        "last_transition_reason": "bootstrap_initial_state",
        "last_transition_date": "2026-02-01",
    }
    base.update(overrides)
    return ContinuityState.from_dict(base)


def _rec(**overrides):
    base = {
        "recommended_goal_horizon_type": "general_fitness",
        "recommended_phase": "base",
        "recommended_block_focus": "controlled_load_progression",
        "recommended_transition_action": "keep",
        "recommended_transition_reason": "No change needed",
        "recommended_goal_event_date": None,
    }
    base.update(overrides)
    return ContinuityRecommendation.from_dict(base)


TODAY = date(2026, 3, 25)


# ---------------------------------------------------------------------------
# Recommendation contract tests
# ---------------------------------------------------------------------------

class TestContinuityRecommendationContract(unittest.TestCase):

    def test_valid_round_trip(self):
        r = _rec()
        self.assertEqual(ContinuityRecommendation.from_dict(r.to_dict()), r)

    def test_all_transition_actions(self):
        for action in VALID_TRANSITION_ACTIONS:
            r = _rec(recommended_transition_action=action)
            self.assertEqual(r.recommended_transition_action, action)

    def test_missing_required_field(self):
        d = _rec().to_dict()
        del d["recommended_transition_action"]
        with self.assertRaises(ContinuityRecommendationError):
            ContinuityRecommendation.from_dict(d)

    def test_invalid_transition_action(self):
        with self.assertRaises(ContinuityRecommendationError):
            _rec(recommended_transition_action="yolo")

    def test_invalid_block_focus(self):
        with self.assertRaises(ContinuityRecommendationError):
            _rec(recommended_block_focus="go_hard")

    def test_invalid_horizon_type(self):
        with self.assertRaises(ContinuityRecommendationError):
            _rec(recommended_goal_horizon_type="marathon")

    def test_optional_event_date_none(self):
        r = _rec(recommended_goal_event_date=None)
        self.assertIsNone(r.recommended_goal_event_date)

    def test_optional_event_date_valid(self):
        r = _rec(recommended_goal_event_date="2026-10-01")
        self.assertEqual(r.recommended_goal_event_date, "2026-10-01")

    def test_non_dict_input(self):
        with self.assertRaises(ContinuityRecommendationError):
            ContinuityRecommendation.from_dict("not a dict")


# ---------------------------------------------------------------------------
# Updater: keep
# ---------------------------------------------------------------------------

class TestUpdaterKeep(unittest.TestCase):

    def test_keep_preserves_all_fields(self):
        state = _base_state()
        rec = _rec(recommended_transition_action="keep")
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result, state)

    def test_keep_ignores_different_phase(self):
        state = _base_state()
        rec = _rec(
            recommended_transition_action="keep",
            recommended_phase="build",
            recommended_block_focus="event_specific_build",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.current_phase, "base")
        self.assertEqual(result.current_block_focus, "controlled_load_progression")
        self.assertEqual(result.block_started_at, "2026-02-01")

    def test_keep_updates_event_date(self):
        state = _base_state()
        rec = _rec(
            recommended_transition_action="keep",
            recommended_goal_event_date="2026-10-01",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_event_date, "2026-10-01")
        # Auto-promotes horizon when event date introduced on keep
        self.assertEqual(result.goal_horizon_type, "event")
        # Everything else preserved
        self.assertEqual(result.block_started_at, "2026-02-01")
        self.assertEqual(result.current_phase, "base")

    def test_keep_event_date_change_does_not_promote_horizon_when_already_set(self):
        """When prior state already has an event date, changing it should not
        alter the horizon type (it's already event or whatever the user set)."""
        state = _base_state(goal_horizon_type="event", goal_event_date="2026-09-01")
        rec = _rec(
            recommended_transition_action="keep",
            recommended_goal_event_date="2026-11-01",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_event_date, "2026-11-01")
        self.assertEqual(result.goal_horizon_type, "event")

    def test_keep_rejects_past_event_date(self):
        state = _base_state(goal_event_date="2026-06-01")
        rec = _rec(
            recommended_transition_action="keep",
            recommended_goal_event_date="2026-01-01",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_event_date, "2026-06-01")


# ---------------------------------------------------------------------------
# Updater: focus_shift
# ---------------------------------------------------------------------------

class TestUpdaterFocusShift(unittest.TestCase):

    def test_focus_shift_resets_block_started_at(self):
        state = _base_state()
        rec = _rec(
            recommended_transition_action="focus_shift",
            recommended_block_focus="maintain_through_constraints",
            recommended_transition_reason="Work travel for 2 weeks",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.block_started_at, "2026-03-25")
        self.assertEqual(result.current_block_focus, "maintain_through_constraints")
        self.assertEqual(result.last_transition_reason, "Work travel for 2 weeks")
        self.assertEqual(result.last_transition_date, "2026-03-25")
        # Phase unchanged on focus_shift
        self.assertEqual(result.current_phase, "base")

    def test_focus_shift_with_horizon_change(self):
        state = _base_state(goal_horizon_type="general_fitness")
        rec = _rec(
            recommended_transition_action="focus_shift",
            recommended_goal_horizon_type="event",
            recommended_block_focus="event_specific_build",
            recommended_goal_event_date="2026-10-15",
            recommended_transition_reason="Athlete signed up for a half marathon",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_horizon_type, "event")
        self.assertEqual(result.goal_event_date, "2026-10-15")


# ---------------------------------------------------------------------------
# Updater: phase_shift
# ---------------------------------------------------------------------------

class TestUpdaterPhaseShift(unittest.TestCase):

    def test_phase_shift_resets_block_started_at(self):
        state = _base_state()  # block started 2026-02-01, ~7 weeks ago
        rec = _rec(
            recommended_transition_action="phase_shift",
            recommended_phase="build",
            recommended_block_focus="event_specific_build",
            recommended_transition_reason="Ready to progress to build phase",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.current_phase, "build")
        self.assertEqual(result.current_block_focus, "event_specific_build")
        self.assertEqual(result.block_started_at, "2026-03-25")

    def test_phase_shift_guardrail_veto(self):
        """Veto phase_shift when weeks_in_current_block < 2 and no bypass reason."""
        state = _base_state(block_started_at="2026-03-20")  # 5 days ago → week 1
        rec = _rec(
            recommended_transition_action="phase_shift",
            recommended_phase="build",
            recommended_block_focus="event_specific_build",
            recommended_transition_reason="Athlete feels ready",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        # Should be vetoed — prior state returned
        self.assertEqual(result.current_phase, "base")
        self.assertEqual(result.block_started_at, "2026-03-20")

    def test_phase_shift_guardrail_bypass_injury(self):
        """Injury reason should bypass the minimum-tenure guardrail."""
        state = _base_state(block_started_at="2026-03-20")
        rec = _rec(
            recommended_transition_action="phase_shift",
            recommended_phase="return_to_training",
            recommended_block_focus="return_safely",
            recommended_transition_reason="New injury reported, need to return safely",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.current_phase, "return_to_training")
        self.assertEqual(result.current_block_focus, "return_safely")

    def test_phase_shift_guardrail_bypass_setback(self):
        state = _base_state(block_started_at="2026-03-20")
        rec = _rec(
            recommended_transition_action="phase_shift",
            recommended_phase="base",
            recommended_block_focus="rebuild_consistency",
            recommended_transition_reason="Significant setback after illness",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.current_block_focus, "rebuild_consistency")

    def test_phase_shift_guardrail_bypass_new_event(self):
        state = _base_state(block_started_at="2026-03-20")
        rec = _rec(
            recommended_transition_action="phase_shift",
            recommended_phase="build",
            recommended_block_focus="event_specific_build",
            recommended_goal_event_date="2026-10-01",
            recommended_transition_reason="Athlete signed up for new event",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.current_phase, "build")


# ---------------------------------------------------------------------------
# Updater: reset_block
# ---------------------------------------------------------------------------

class TestUpdaterResetBlock(unittest.TestCase):

    def test_reset_block(self):
        state = _base_state()
        rec = _rec(
            recommended_transition_action="reset_block",
            recommended_goal_horizon_type="return_to_training",
            recommended_phase="return_to_training",
            recommended_block_focus="return_safely",
            recommended_transition_reason="Major illness, need full reset",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_horizon_type, "return_to_training")
        self.assertEqual(result.current_phase, "return_to_training")
        self.assertEqual(result.current_block_focus, "return_safely")
        self.assertEqual(result.block_started_at, "2026-03-25")
        self.assertEqual(result.last_transition_reason, "Major illness, need full reset")


# ---------------------------------------------------------------------------
# Updater: general_fitness → event transition
# ---------------------------------------------------------------------------

class TestUpdaterHorizonTransition(unittest.TestCase):

    def test_general_fitness_to_event(self):
        state = _base_state(goal_horizon_type="general_fitness", goal_event_date=None)
        rec = _rec(
            recommended_transition_action="focus_shift",
            recommended_goal_horizon_type="event",
            recommended_block_focus="event_specific_build",
            recommended_goal_event_date="2026-10-15",
            recommended_transition_reason="Athlete registered for half marathon",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_horizon_type, "event")
        self.assertEqual(result.goal_event_date, "2026-10-15")

    def test_event_date_update(self):
        state = _base_state(
            goal_horizon_type="event",
            goal_event_date="2026-06-01",
        )
        rec = _rec(
            recommended_transition_action="focus_shift",
            recommended_goal_horizon_type="event",
            recommended_block_focus="event_specific_build",
            recommended_goal_event_date="2026-07-15",
            recommended_transition_reason="Event date changed",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_event_date, "2026-07-15")


# ---------------------------------------------------------------------------
# Updater: fallbacks
# ---------------------------------------------------------------------------

class TestUpdaterFallbacks(unittest.TestCase):

    def test_none_recommendation(self):
        state = _base_state()
        result = apply_continuity_recommendation(state, None, TODAY)
        self.assertEqual(result, state)

    def test_past_event_date_rejected_on_mutate(self):
        state = _base_state()
        rec = _rec(
            recommended_transition_action="focus_shift",
            recommended_block_focus="event_specific_build",
            recommended_goal_event_date="2025-01-01",
            recommended_transition_reason="Event change",
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        # Past event date → prior state returned
        self.assertEqual(result, state)

    def test_none_event_date_in_recommendation_preserves_existing(self):
        state = _base_state(
            goal_horizon_type="event",
            goal_event_date="2026-06-15",
        )
        rec = _rec(
            recommended_transition_action="focus_shift",
            recommended_block_focus="taper_for_event",
            recommended_transition_reason="Entering taper",
            recommended_goal_event_date=None,
        )
        result = apply_continuity_recommendation(state, rec, TODAY)
        self.assertEqual(result.goal_event_date, "2026-06-15")


if __name__ == "__main__":
    unittest.main()
