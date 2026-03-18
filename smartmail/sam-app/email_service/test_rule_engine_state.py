"""Unit tests for RE1-FU.2 rule-state store contract."""

from decimal import Decimal
import unittest
from unittest import mock

import rule_engine_state


class _RuleStateTable:
    def __init__(self):
        self.items = {}

    def get_item(self, **kwargs):
        athlete_id = kwargs.get("Key", {}).get("athlete_id")
        item = self.items.get(athlete_id)
        return {"Item": dict(item)} if isinstance(item, dict) else {}

    def put_item(self, **kwargs):
        item = kwargs.get("Item", {})
        athlete_id = item.get("athlete_id")
        if isinstance(athlete_id, str) and athlete_id:
            self.items[athlete_id] = dict(item)
        self.last_put_item = dict(item)
        return {}


class _RoutingDynamo:
    def __init__(self, table):
        self.table = table

    def Table(self, _name):  # noqa: N802
        return self.table


class TestRuleStateStore(unittest.TestCase):
    def setUp(self):
        super().setUp()
        self.table = _RuleStateTable()
        self._patcher = mock.patch.object(
            rule_engine_state,
            "dynamodb",
            _RoutingDynamo(self.table),
        )
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        super().tearDown()

    def test_bootstrap_empty_state(self):
        state = rule_engine_state.load_rule_state("ath_fu_state_bootstrap")
        self.assertEqual(state["athlete_id"], "ath_fu_state_bootstrap")
        self.assertEqual(state["weekly_signals_last_4"], [])
        self.assertEqual(state["compliance_last_4"], [])
        self.assertEqual(state["phase_risk_time_last_6"], [])
        self.assertEqual(state["weeks_since_deload"], 0)
        self.assertEqual(state["phase_upgrade_streak"], 0)
        self.assertEqual(state["main_sport_transition_weeks_remaining"], 0)
        self.assertEqual(state["main_sport_frozen_until_week_start"], "")
        self.assertEqual(state["last_main_sport_switch_week_start"], "")
        self.assertIsNone(state["last_main_sport"])
        self.assertEqual(state["last_updated_week_start"], "")

    def test_rolling_windows_are_capped(self):
        athlete_id = "ath_fu_state_window"
        for idx in range(1, 8):
            week = f"2026-01-{idx:02d}"
            rule_engine_state.update_rule_state(
                athlete_id,
                {
                    "week_start": week,
                    "pain_score": idx,
                    "energy_score": 6,
                    "sleep_score": 6,
                    "stress_score": 6,
                    "sports_last_week": [{"sport": "run", "minutes": 30 + idx}],
                    "planned_sessions_count": 4,
                    "completed_sessions_count": 3,
                    "time_bucket": "4_6h",
                },
                {"phase": "build", "risk_flag": "yellow"},
            )

        state = rule_engine_state.load_rule_state(athlete_id)
        self.assertEqual(len(state["weekly_signals_last_4"]), 4)
        self.assertEqual(len(state["compliance_last_4"]), 4)
        self.assertEqual(len(state["phase_risk_time_last_6"]), 6)
        self.assertEqual(state["weekly_signals_last_4"][-1]["week_start"], "2026-01-07")
        self.assertEqual(
            state["weekly_signals_last_4"][-1]["sports_minutes_by_sport"]["run"],
            37,
        )
        self.assertEqual(state["phase_risk_time_last_6"][-1]["week_start"], "2026-01-07")

    def test_same_week_is_deterministic_overwrite(self):
        athlete_id = "ath_fu_state_overwrite"
        rule_engine_state.update_rule_state(
            athlete_id,
            {
                "week_start": "2026-02-01",
                "pain_score": 2,
                "planned_sessions_count": 4,
                "completed_sessions_count": 3,
            },
            {"phase": "base", "risk_flag": "green"},
        )
        rule_engine_state.update_rule_state(
            athlete_id,
            {
                "week_start": "2026-02-01",
                "pain_score": 5,
                "planned_sessions_count": 5,
                "completed_sessions_count": 4,
            },
            {"phase": "build", "risk_flag": "yellow"},
        )
        state = rule_engine_state.load_rule_state(athlete_id)
        self.assertEqual(len(state["weekly_signals_last_4"]), 1)
        self.assertEqual(state["weekly_signals_last_4"][0]["pain_score"], 5.0)
        self.assertEqual(state["phase_risk_time_last_6"][0]["phase"], "build")

    def test_switch_state_written_then_decremented(self):
        athlete_id = "ath_fu_state_switch"
        rule_engine_state.update_rule_state(
            athlete_id,
            {"week_start": "2026-03-01"},
            {"main_sport_switched": True, "previous_main_sport": "run"},
        )
        state_after_switch = rule_engine_state.load_rule_state(athlete_id)
        self.assertEqual(state_after_switch["main_sport_transition_weeks_remaining"], 2)
        self.assertEqual(state_after_switch["last_main_sport_switch_week_start"], "2026-03-01")
        self.assertEqual(state_after_switch["last_main_sport"], "run")

        rule_engine_state.update_rule_state(athlete_id, {"week_start": "2026-03-08"}, {})
        state_after_week = rule_engine_state.load_rule_state(athlete_id)
        self.assertEqual(state_after_week["main_sport_transition_weeks_remaining"], 1)

    def test_invalid_input_types_raise(self):
        with self.assertRaises(rule_engine_state.RuleEngineStateError):
            rule_engine_state.load_rule_state("")
        with self.assertRaises(rule_engine_state.RuleEngineStateError):
            rule_engine_state.update_rule_state("ath_fu_invalid", [], {})
        with self.assertRaises(rule_engine_state.RuleEngineStateError):
            rule_engine_state.update_rule_state("ath_fu_invalid", {}, [])

    def test_put_item_serializes_float_scores_to_decimal(self):
        athlete_id = "ath_fu_state_decimal"
        rule_engine_state.update_rule_state(
            athlete_id,
            {
                "week_start": "2026-03-15",
                "pain_score": 2.5,
                "energy_score": 6.5,
                "sleep_score": 7.25,
                "stress_score": 4.5,
                "planned_sessions_count": 4,
                "completed_sessions_count": 3,
                "sports_last_week": [{"sport": "run", "minutes": 55}],
            },
            {"phase": "build", "risk_flag": "yellow"},
        )
        stored = self.table.last_put_item
        weekly_signal = stored["weekly_signals_last_4"][0]
        self.assertIsInstance(weekly_signal["pain_score"], Decimal)
        self.assertEqual(weekly_signal["pain_score"], Decimal("2.5"))
        self.assertIsInstance(weekly_signal["energy_score"], Decimal)
        self.assertEqual(weekly_signal["sleep_score"], Decimal("7.25"))
        state = rule_engine_state.load_rule_state(athlete_id)
        self.assertEqual(state["weekly_signals_last_4"][0]["pain_score"], 2.5)

    def test_serializer_rejects_non_finite_floats(self):
        with self.assertRaises(rule_engine_state.RuleEngineStateError):
            rule_engine_state._serialize_dynamodb_payload({"bad": float("nan")})
