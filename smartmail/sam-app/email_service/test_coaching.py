"""Unit tests for coaching (profile-gated reply). DynamoDB/merge mocked."""
import sys
import unittest
from unittest import mock

# Allow running without boto: stub dynamodb_models before coaching imports it
try:
    import coaching
except ModuleNotFoundError as e:
    if "boto" in str(e).lower() or "botocore" in str(e).lower():
        coaching = None  # type: ignore
    else:
        raise


@unittest.skipIf(coaching is None, "boto3/botocore not installed; skip coaching tests")
class TestBuildProfileGatedReply(unittest.TestCase):
    def test_returns_ready_message_when_profile_complete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: 10k."
            create_token.return_value = "tok_123"
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, just checking in.",
                log_outcome=None,
            )
            self.assertIn("ready for coaching", reply)
            self.assertIn("Share your latest training question", reply)
            self.assertIn("CONNECT STRAVA FOR MORE PERSONALIZED COACHING", reply)
            self.assertIn("https://geniml.com/action/tok_123", reply)
            self.assertIn("Benefit: synced workouts improve load and recovery guidance.", reply)
            self.assertIn("Current plan - Goal: 10k.", reply)
            ensure_plan.assert_called_once_with("ath_1", fallback_goal="10k")

    def test_returns_collection_prompt_when_profile_incomplete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan:
            get_profile.return_value = {}
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                log_outcome=None,
            )
            self.assertIn("need a bit more context", reply)
            self.assertIn("primary goal", reply.lower())
            ensure_plan.assert_called_once_with("ath_1", fallback_goal=None)

    def test_applies_updates_from_email_and_then_checks_profile(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.side_effect = [
                {},
                {
                    "primary_goal": "marathon",
                    "time_availability": {"sessions_per_week": 4},
                    "experience_level": "unknown",
                    "constraints": [],
                },
            ]
            parse_updates.return_value = {
                "primary_goal": "marathon",
                "time_availability": {"sessions_per_week": 4},
                "experience_level": "unknown",
                "constraints": [],
            }
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = "tok_456"
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Goal: marathon. I have 3 hours per week. Sports: running.",
                log_outcome=None,
            )
            self.assertIn("ready for coaching", reply)
            self.assertIn("https://geniml.com/action/tok_456", reply)
            merge.assert_called_once()
            ensure_plan.assert_called_once_with("ath_1", fallback_goal="marathon")

    def test_calls_log_outcome_when_provided(self):
        log_calls = []
        def capture(**kwargs):
            log_calls.append(kwargs)
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 1.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = "tok_789"
            coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi.",
                log_outcome=capture,
            )
            self.assertGreater(len(log_calls), 0)
            self.assertTrue(any("result" in c for c in log_calls))

    def test_ready_message_skips_strava_link_when_token_creation_fails(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = None
            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi, just checking in.",
                log_outcome=None,
            )
            self.assertIn("ready for coaching", reply)
            self.assertNotIn("CONNECT STRAVA FOR MORE PERSONALIZED COACHING", reply)

    def test_profile_complete_uses_selected_model_for_llm_reply(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "OpenAIResponder") as responder, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: 10k."
            create_token.return_value = "tok_123"
            responder.generate_response.return_value = "LLM routed reply"

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Can you adjust my next sessions?",
                inbound_subject="Plan help",
                selected_model_name="gpt-5-nano",
                log_outcome=None,
            )

            self.assertEqual(reply, "LLM routed reply")
            responder.generate_response.assert_called_once()
            kwargs = responder.generate_response.call_args.kwargs
            self.assertEqual(kwargs["model_name"], "gpt-5-nano")
            self.assertEqual(kwargs["subject"], "Plan help")
            self.assertIn("Current plan context", kwargs["body"])

    def test_rule_engine_decision_context_is_included_in_reply(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "create_action_token", return_value=None):
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi",
                rule_engine_decision={
                    "clarification_needed": True,
                    "engine_output": {
                        "track": "main_build",
                        "risk_flag": "yellow",
                        "plan_update_status": "unchanged_clarification_needed",
                    },
                },
                log_outcome=None,
            )

            self.assertIn("need a clearer weekly check-in", reply)
            self.assertIn("Rule-engine context:", reply)

    def test_rule_engine_guided_reply_uses_deterministic_payload_and_bypasses_llm(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "OpenAIResponder") as responder:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "Hi",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={
                    "reply_strategy": "rule_engine_guided",
                    "engine_output": {
                        "classification_label": "deterministic_re3_transition",
                        "track": "return_or_risk_managed",
                        "phase": "build",
                        "risk_flag": "yellow",
                        "weekly_skeleton": ["easy_aerobic", "strength"],
                        "today_action": "prioritize_big_2_anchors",
                        "plan_update_status": "updated",
                        "adjustments": ["prioritize_big_2_anchors"],
                        "next_email_payload": {
                            "subject_hint": "This week: stay safe and keep it steady",
                            "summary": "This is a risk-managed week.",
                            "sessions": ["Priority: long easy aerobic session", "Priority: strength session"],
                            "plan_focus_line": "Use safety and consistency as the primary filter.",
                            "technique_cue": "Keep cadence light and posture tall.",
                            "recovery_target": "Prioritize recovery basics before adding any load.",
                            "if_then_rules": ["If symptoms rise, remove intensity immediately."],
                            "disclaimer_short": "",
                            "safety_note": "No hard sessions when risk is red-tier.",
                        },
                    },
                },
                log_outcome=None,
            )

            self.assertIn("This week: stay safe and keep it steady", reply)
            self.assertIn("Current plan - Goal: 10k.", reply)
            self.assertIn("Priority: long easy aerobic session", reply)
            responder.generate_response.assert_not_called()

    def test_safety_reply_strategy_bypasses_llm_generation(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None), \
             mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True), \
             mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}), \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary", return_value=None), \
             mock.patch.object(coaching, "create_action_token", return_value=None), \
             mock.patch.object(coaching, "OpenAIResponder") as responder:
            get_profile.return_value = {
                "primary_goal": "10k",
                "time_availability": {"hours_per_week": 2.0},
                "experience_level": "unknown",
                "constraints": [],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True

            reply = coaching.build_profile_gated_reply(
                "ath_1",
                "user@example.com",
                "I have sharp knee pain, should I run?",
                selected_model_name="gpt-5-nano",
                rule_engine_decision={"reply_strategy": "safety_concern"},
                log_outcome=None,
            )

            self.assertEqual(reply, coaching.EmailCopy.SAFETY_CONCERN_REPLY)
            responder.generate_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
