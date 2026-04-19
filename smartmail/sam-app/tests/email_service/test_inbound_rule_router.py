"""Unit tests for inbound routing without authoritative rule-engine usage."""

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
        with mock.patch.object(
            router,
            "run_session_checkin_extraction_workflow",
            return_value={"days_available": 4, "pain_score": 2},
        ), mock.patch.object(
            router,
            "list_missing_or_low_confidence_critical_fields",
            return_value=[],
        ):
            coaching = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "coaching"},
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
            safety_concern = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "safety_concern"},
            )

        self.assertEqual(coaching["mode"], "mutate")
        self.assertEqual(question["mode"], "read_only")
        self.assertEqual(off_topic["mode"], "skip")
        self.assertEqual(safety_concern["mode"], "skip")
        self.assertEqual(safety_concern["reply_strategy"], "safety_concern")
        self.assertFalse(coaching["rule_engine_ran"])
        self.assertIsNone(coaching["engine_output"])

    def test_extractor_failure_forces_clarification_without_engine_run(self):
        with mock.patch.object(
            router,
            "run_session_checkin_extraction_workflow",
            side_effect=router.SessionCheckinExtractionProposalError("fail"),
        ):
            decision = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "coaching"},
            )

        self.assertEqual(decision["mode"], "skip")
        self.assertTrue(decision["clarification_needed"])
        self.assertEqual(decision["reply_strategy"], "clarification")
        self.assertEqual(decision["rule_engine_status"], "clarification_needed")

    def test_requested_action_drives_mode_without_engine_side_effects(self):
        with mock.patch.object(
            router,
            "run_session_checkin_extraction_workflow",
            return_value={"days_available": 4},
        ), mock.patch.object(
            router,
            "list_missing_or_low_confidence_critical_fields",
            return_value=[],
        ):
            mutate = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "question", "requested_action": "plan_update"},
            )
            read_only = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "coaching", "requested_action": "answer_question"},
            )

        self.assertEqual(mutate["mode"], "mutate")
        self.assertEqual(read_only["mode"], "read_only")
        self.assertEqual(mutate["rule_engine_status"], "inactive")
        self.assertIsNone(mutate["plan_update_result"])

    def test_logs_required_telemetry_fields(self):
        logs = []

        def capture(**kwargs):
            logs.append(kwargs)

        with mock.patch.object(
            router,
            "run_session_checkin_extraction_workflow",
            side_effect=router.SessionCheckinExtractionProposalError("fail"),
        ):
            router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {"intent": "coaching"},
                log_outcome=capture,
            )

        routed = [entry for entry in logs if entry.get("result") == "rule_engine_routed"]
        self.assertEqual(len(routed), 1)
        entry = routed[0]
        self.assertIn("rule_engine_mode", entry)
        self.assertIn("rule_engine_status", entry)
        self.assertIn("plan_update_status", entry)
        self.assertIn("plan_update_result_status", entry)
        self.assertIn("clarification_needed", entry)
        self.assertIn("intent", entry)

    def test_carries_brevity_preference_and_missing_or_low_confidence(self):
        with mock.patch.object(
            router,
            "run_session_checkin_extraction_workflow",
            return_value={"days_available": 4},
        ), mock.patch.object(
            router,
            "list_missing_or_low_confidence_critical_fields",
            return_value=["pain_score"],
        ):
            decision = router.route_inbound_with_rule_engine(
                "ath_1",
                "u@example.com",
                self._email_data(),
                {
                    "intent": "coaching",
                    "requested_action": "plan_update",
                    "brevity_preference": "brief",
                },
            )

        self.assertEqual(decision["brevity_preference"], "brief")
        self.assertEqual(decision["missing_or_low_confidence"], ["pain_score"])
        self.assertEqual(decision["extracted_checkin"], {"days_available": 4})
        self.assertEqual(decision["mode"], "mutate")


if __name__ == "__main__":
    unittest.main()
