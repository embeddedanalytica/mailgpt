"""Integration-oriented tests for RE2 orchestrator wiring."""

import unittest
from datetime import date
from unittest import mock

from _test_support import install_boto_stubs, valid_engine_output_payload

install_boto_stubs()

import rule_engine_orchestrator


class TestApplyRuleEnginePlanUpdate(unittest.TestCase):
    def test_skip_write_when_not_updated(self):
        result = rule_engine_orchestrator.apply_rule_engine_plan_update(
            athlete_id="ath_1",
            engine_output=valid_engine_output_payload(plan_update_status="unchanged_infeasible_week"),
            logical_request_id="req-1",
        )
        self.assertEqual(result["status"], "skipped")

    def test_updated_path_calls_update_current_plan_once(self):
        with mock.patch.object(
            rule_engine_orchestrator,
            "update_current_plan",
            return_value={"status": "applied", "plan_version": 2, "error_code": None},
        ) as update_plan:
            result = rule_engine_orchestrator.apply_rule_engine_plan_update(
                athlete_id="ath_1",
                engine_output=valid_engine_output_payload(
                    risk_flag="green",
                    weekly_skeleton=["easy_aerobic", "tempo", "strength"],
                ),
                logical_request_id="req-2",
            )

        self.assertEqual(result["status"], "applied")
        update_plan.assert_called_once()
        updates = update_plan.call_args.args[1]
        self.assertEqual(updates["weekly_skeleton"], ["easy_aerobic", "tempo", "strength"])
        self.assertEqual(updates["plan_update_status"], "updated")


class TestRunRuleEngineForWeek(unittest.TestCase):
    def test_phase_upgrade_requires_two_consecutive_qualifying_checkins(self):
        with mock.patch.object(
            rule_engine_orchestrator,
            "load_rule_state",
            return_value={
                "phase_risk_time_last_6": [{"week_start": "2026-03-01", "phase": "base", "risk_flag": "green"}],
                "phase_upgrade_streak": 0,
            },
        ), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ) as update_state:
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "main_sport_current": "run", "time_bucket": "4_6h"},
                checkin={
                    "has_upcoming_event": False,
                    "days_available": 4,
                    "performance_intent_this_week": True,
                },
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(output.phase, "base")
        decisions = update_state.call_args.args[2]
        self.assertEqual(decisions["phase_upgrade_streak"], 1)

    def test_second_consecutive_upgrade_allows_phase_advance(self):
        with mock.patch.object(
            rule_engine_orchestrator,
            "load_rule_state",
            return_value={
                "phase_risk_time_last_6": [{"week_start": "2026-03-01", "phase": "base", "risk_flag": "green"}],
                "phase_upgrade_streak": 1,
            },
        ), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ) as update_state:
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "main_sport_current": "run", "time_bucket": "4_6h"},
                checkin={
                    "has_upcoming_event": False,
                    "days_available": 4,
                    "performance_intent_this_week": True,
                },
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(output.phase, "build")
        decisions = update_state.call_args.args[2]
        self.assertEqual(decisions["phase_upgrade_streak"], 0)

    def test_red_tier_downgrade_applies_immediately(self):
        with mock.patch.object(
            rule_engine_orchestrator,
            "load_rule_state",
            return_value={
                "phase_risk_time_last_6": [{"week_start": "2026-03-01", "phase": "peak_taper", "risk_flag": "green"}],
                "phase_upgrade_streak": 1,
            },
        ), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "event_8_16w", "main_sport_current": "run", "time_bucket": "4_6h"},
                checkin={
                    "has_upcoming_event": True,
                    "event_date": "2026-03-18",
                    "days_available": 4,
                    "pain_score": 5,
                },
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(output.phase, "build")
        self.assertEqual(output.risk_flag, "red_a")

    def test_clarification_sets_unchanged_status(self):
        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "event_8_16w", "time_bucket": "4_6h"},
                checkin={"has_upcoming_event": True, "event_date": None, "days_available": 4},
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(output.plan_update_status, "unchanged_clarification_needed")

    def test_switch_decision_is_consumed_during_skeleton_build(self):
        observed = {}

        def _capture_build(profile, checkin, track, phase, risk_flag, effective_performance_intent, rule_state):
            observed["main_sport_current"] = profile.get("main_sport_current")
            return {
                "track": track,
                "phase": phase,
                "risk_flag": risk_flag,
                "time_bucket": "4_6h",
                "weekly_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic"],
                "adjustments": [],
                "plan_update_status": "updated",
                "infeasible": False,
            }

        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "should_switch_main_sport",
            return_value=True,
        ), mock.patch.object(
            rule_engine_orchestrator,
            "resolve_main_sport_after_guardrails",
            return_value="bike",
        ), mock.patch.object(rule_engine_orchestrator, "build_weekly_skeleton", side_effect=_capture_build), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ):
            rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "main_sport_current": "run", "time_bucket": "4_6h"},
                checkin={"has_upcoming_event": False, "days_available": 4},
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(observed["main_sport_current"], "bike")

    def test_deload_applies_before_final_emission(self):
        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "should_trigger_main_sport_deload",
            return_value=True,
        ), mock.patch.object(
            rule_engine_orchestrator,
            "apply_main_sport_deload_adjustments",
            return_value=["easy_aerobic", "strength", "deload_volume_reduce_20pct"],
        ), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "main_sport_current": "run", "time_bucket": "4_6h"},
                checkin={"has_upcoming_event": False, "days_available": 4},
                today_date=date(2026, 3, 4),
            )

        self.assertIn("deload_volume_reduce_20pct", output.weekly_skeleton)

    def test_infeasible_week_output_uses_unchanged_status(self):
        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "time_bucket": "4_6h"},
                checkin={"has_upcoming_event": False, "days_available": 1},
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(output.plan_update_status, "unchanged_infeasible_week")
        self.assertEqual(output.weekly_skeleton, [])

    def test_routing_and_payload_use_re3_logic(self):
        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "time_bucket": "4_6h"},
                checkin={
                    "has_upcoming_event": False,
                    "days_available": 4,
                    "week_chaotic": True,
                    "energy_score": 9,
                },
                today_date=date(2026, 3, 4),
            )

        self.assertEqual(output.today_action, "prioritize_big_2_anchors")
        self.assertTrue(any(item.startswith("Priority: ") for item in output.next_email_payload["sessions"]))

    def test_re4_planner_validated_plan_is_used(self):
        rendered_payload = valid_engine_output_payload()["next_email_payload"]
        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ), mock.patch.object(
            rule_engine_orchestrator.PlanningLLM,
            "propose_plan",
            return_value={
                "plan_proposal": {"weekly_skeleton": ["easy_aerobic", "strength", "easy_aerobic"]},
                "rationale": "valid plan",
                "non_binding_state_suggestions": ["advisory_only"],
            },
        ), mock.patch.object(
            rule_engine_orchestrator.LanguageReplyRenderer,
            "render_reply",
            return_value=rendered_payload,
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "time_bucket": "4_6h"},
                checkin={"has_upcoming_event": False, "days_available": 4},
                today_date=date(2026, 3, 4),
            )
        self.assertEqual(output.classification_label, "deterministic_re4")
        self.assertEqual(output.weekly_skeleton, ["easy_aerobic", "strength", "easy_aerobic"])

    def test_re4_language_renderer_invalid_payload_falls_back_to_deterministic_payload(self):
        with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
            rule_engine_orchestrator,
            "update_rule_state",
            return_value={},
        ), mock.patch.object(
            rule_engine_orchestrator.PlanningLLM,
            "propose_plan",
            return_value={
                "plan_proposal": {"weekly_skeleton": ["easy_aerobic", "strength"]},
                "rationale": "valid plan",
                "non_binding_state_suggestions": [],
            },
        ), mock.patch.object(
            rule_engine_orchestrator.LanguageReplyRenderer,
            "render_reply",
            return_value={"subject_hint": "missing required fields"},
        ):
            output = rule_engine_orchestrator.run_rule_engine_for_week(
                athlete_id="ath_1",
                profile={"goal_category": "general_consistency", "time_bucket": "4_6h"},
                checkin={"has_upcoming_event": False, "days_available": 4, "week_chaotic": True},
                today_date=date(2026, 3, 4),
            )
        self.assertIn("subject_hint", output.next_email_payload)
        self.assertIn("sessions", output.next_email_payload)
