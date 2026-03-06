"""Unit tests for inbound rule-engine routing."""

from _test_support import install_boto_stubs
import unittest
from unittest import mock

install_boto_stubs()

import inbound_rule_router as router

class TestInboundRuleRouter(unittest.TestCase):
    def _email_data(self):
        return {
            "body": "I have 4 days this week. pain 2/10.",
            "message_id": "msg-1",
            "subject": "Weekly check in",
        }

    def test_intent_matrix_modes(self):
        with mock.patch.object(router, "get_coach_profile", return_value={"time_bucket": "4_6h"}), mock.patch.object(
            router.SessionCheckinExtractor,
            "extract_session_checkin_fields",
            return_value={
                "days_available": 4,
                "pain_score": 2,
                "risk_candidate": "green",
                "event_date": None,
                "has_upcoming_event": False,
            },
        ), mock.patch.object(router, "list_missing_or_low_confidence_critical_fields", return_value=[]), mock.patch.object(
            router,
            "run_rule_engine_for_week",
        ) as run_re:
            run_re.return_value = mock.Mock(to_dict=lambda: {"plan_update_status": "updated", "track": "main_build", "risk_flag": "green"})

            check_in = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "check_in"},
            )
            question = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "question"},
            )
            off_topic = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "off_topic"},
            )
            availability_update = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "availability_update"},
            )
            safety_concern = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "safety_concern"},
            )

        self.assertEqual(check_in["mode"], "mutate")
        self.assertEqual(question["mode"], "read_only")
        self.assertEqual(off_topic["mode"], "skip")
        self.assertEqual(availability_update["mode"], "mutate")
        self.assertEqual(safety_concern["mode"], "skip")
        self.assertEqual(safety_concern["reply_strategy"], "safety_concern")

    def test_extractor_failure_forces_no_mutate(self):
        with mock.patch.object(router, "get_coach_profile", return_value={}), mock.patch.object(
            router.SessionCheckinExtractor,
            "extract_session_checkin_fields",
            side_effect=router.SessionCheckinExtractionError("fail"),
        ), mock.patch.object(router, "run_rule_engine_for_week") as run_re:
            decision = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "check_in"},
            )

        self.assertEqual(decision["mode"], "skip")
        self.assertTrue(decision["clarification_needed"])
        run_re.assert_not_called()

    def test_mutate_path_runs_re_and_updates_plan(self):
        engine_output = mock.Mock(
            to_dict=lambda: {
                "plan_update_status": "updated",
                "track": "main_build",
                "risk_flag": "green",
            }
        )
        with mock.patch.object(router, "get_coach_profile", return_value={"time_bucket": "4_6h"}), mock.patch.object(
            router.SessionCheckinExtractor,
            "extract_session_checkin_fields",
            return_value={
                "days_available": 4,
                "pain_score": 2,
                "risk_candidate": "green",
                "event_date": None,
                "has_upcoming_event": False,
            },
        ), mock.patch.object(router, "list_missing_or_low_confidence_critical_fields", return_value=[]), mock.patch.object(
            router,
            "run_rule_engine_for_week",
            return_value=engine_output,
        ) as run_re, mock.patch.object(
            router,
            "apply_rule_engine_plan_update",
            return_value={"status": "applied", "plan_version": 2, "error_code": None},
        ) as apply_update:
            decision = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "check_in"},
            )

        self.assertTrue(decision["rule_engine_ran"])
        self.assertEqual(decision["mode"], "mutate")
        run_re.assert_called_once()
        self.assertTrue(run_re.call_args.kwargs["persist_state"])
        apply_update.assert_called_once()

    def test_read_only_path_runs_re_without_state_or_plan_writes(self):
        engine_output = mock.Mock(
            to_dict=lambda: {
                "plan_update_status": "updated",
                "track": "main_build",
                "risk_flag": "green",
            }
        )
        with mock.patch.object(router, "get_coach_profile", return_value={"time_bucket": "4_6h"}), mock.patch.object(
            router.SessionCheckinExtractor,
            "extract_session_checkin_fields",
            return_value={
                "days_available": 3,
                "pain_score": 1,
                "risk_candidate": "green",
                "event_date": None,
                "has_upcoming_event": False,
            },
        ), mock.patch.object(router, "list_missing_or_low_confidence_critical_fields", return_value=[]), mock.patch.object(
            router,
            "run_rule_engine_for_week",
            return_value=engine_output,
        ) as run_re, mock.patch.object(router, "apply_rule_engine_plan_update") as apply_update:
            decision = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "question"},
            )

        self.assertEqual(decision["mode"], "read_only")
        self.assertTrue(decision["rule_engine_ran"])
        self.assertFalse(run_re.call_args.kwargs["persist_state"])
        apply_update.assert_not_called()

    def test_mutate_path_skips_plan_update_when_output_not_updated(self):
        engine_output = mock.Mock(
            to_dict=lambda: {
                "plan_update_status": "unchanged_infeasible_week",
                "track": "main_build",
                "risk_flag": "yellow",
            }
        )
        with mock.patch.object(router, "get_coach_profile", return_value={}), mock.patch.object(
            router.SessionCheckinExtractor,
            "extract_session_checkin_fields",
            return_value={
                "days_available": 2,
                "pain_score": 1,
                "risk_candidate": "yellow",
                "event_date": None,
                "has_upcoming_event": False,
            },
        ), mock.patch.object(router, "list_missing_or_low_confidence_critical_fields", return_value=[]), mock.patch.object(
            router,
            "run_rule_engine_for_week",
            return_value=engine_output,
        ), mock.patch.object(router, "apply_rule_engine_plan_update") as apply_update:
            decision = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "check_in"},
            )

        self.assertEqual(decision["plan_update_result"]["status"], "skipped")
        apply_update.assert_not_called()

    def test_logs_required_telemetry_fields(self):
        logs = []

        def capture(**kwargs):
            logs.append(kwargs)

        with mock.patch.object(router, "get_coach_profile", return_value={}), mock.patch.object(
            router.SessionCheckinExtractor,
            "extract_session_checkin_fields",
            side_effect=router.SessionCheckinExtractionError("fail"),
        ):
            router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "check_in"},
                log_outcome=capture,
            )

        self.assertGreaterEqual(len(logs), 1)
        routed = [entry for entry in logs if entry.get("result") == "rule_engine_routed"]
        self.assertEqual(len(routed), 1)
        entry = routed[0]
        self.assertIn("rule_engine_mode", entry)
        self.assertIn("rule_engine_status", entry)
        self.assertIn("plan_update_status", entry)
        self.assertIn("plan_update_result_status", entry)
        self.assertIn("clarification_needed", entry)
        self.assertIn("intent", entry)
