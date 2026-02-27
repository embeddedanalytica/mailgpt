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
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "goal": "10k",
                "weekly_time_budget_minutes": 120,
                "sports": ["running"],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = "Current plan - Goal: 10k."
            create_token.return_value = "tok_123"
            reply = coaching.build_profile_gated_reply(
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
            ensure_plan.assert_called_once_with("user@example.com", fallback_goal="10k")

    def test_returns_collection_prompt_when_profile_incomplete(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan:
            get_profile.return_value = {}
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            reply = coaching.build_profile_gated_reply(
                "user@example.com",
                "Hi.",
                log_outcome=None,
            )
            self.assertIn("need a bit more context", reply)
            self.assertIn("training goal", reply)
            ensure_plan.assert_called_once_with("user@example.com", fallback_goal=None)

    def test_applies_updates_from_email_and_then_checks_profile(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.side_effect = [
                {},
                {"goal": "marathon", "weekly_time_budget_minutes": 180, "sports": ["running"]},
            ]
            parse_updates.return_value = {
                "goal": "marathon",
                "weekly_time_budget_minutes": 180,
                "sports": ["running"],
            }
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = "tok_456"
            reply = coaching.build_profile_gated_reply(
                "user@example.com",
                "Goal: marathon. I have 3 hours per week. Sports: running.",
                log_outcome=None,
            )
            self.assertIn("ready for coaching", reply)
            self.assertIn("https://geniml.com/action/tok_456", reply)
            merge.assert_called_once()
            ensure_plan.assert_called_once_with("user@example.com", fallback_goal="marathon")

    def test_calls_log_outcome_when_provided(self):
        log_calls = []
        def capture(**kwargs):
            log_calls.append(kwargs)
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {"goal": "10k", "weekly_time_budget_minutes": 60, "sports": ["running"]}
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = "tok_789"
            coaching.build_profile_gated_reply(
                "user@example.com",
                "Hi.",
                log_outcome=capture,
            )
            self.assertGreater(len(log_calls), 0)
            self.assertTrue(any("result" in c for c in log_calls))

    def test_ready_message_skips_strava_link_when_token_creation_fails(self):
        with mock.patch.object(coaching, "get_coach_profile") as get_profile, \
             mock.patch.object(coaching, "parse_profile_updates_from_email") as parse_updates, \
             mock.patch.object(coaching, "merge_coach_profile_fields") as merge, \
             mock.patch.object(coaching, "ensure_current_plan") as ensure_plan, \
             mock.patch.object(coaching, "fetch_current_plan_summary") as fetch_summary, \
             mock.patch.object(coaching, "create_action_token") as create_token, \
             mock.patch.object(coaching, "ACTION_BASE_URL", "https://geniml.com/action/"):
            get_profile.return_value = {
                "goal": "10k",
                "weekly_time_budget_minutes": 120,
                "sports": ["running"],
            }
            parse_updates.return_value = {}
            merge.return_value = True
            ensure_plan.return_value = True
            fetch_summary.return_value = None
            create_token.return_value = None
            reply = coaching.build_profile_gated_reply(
                "user@example.com",
                "Hi, just checking in.",
                log_outcome=None,
            )
            self.assertIn("ready for coaching", reply)
            self.assertNotIn("CONNECT STRAVA FOR MORE PERSONALIZED COACHING", reply)


if __name__ == "__main__":
    unittest.main()
