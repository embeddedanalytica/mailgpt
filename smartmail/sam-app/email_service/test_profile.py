"""Unit tests for profile extraction (goal, weekly time, sports)."""
import unittest
from unittest import mock

import profile as profile_module
from openai_responder import ProfileExtractionError


class TestParseProfileUpdates(unittest.TestCase):
    @mock.patch("profile.ProfileExtractor.extract_profile_fields")
    def test_parses_goal_weekly_sports_from_llm(self, mock_extract):
        mock_extract.return_value = {
            "goal": "run a marathon  ",
            "weekly_time_budget_minutes": 300,
            "sports": ["Running", "strength", "running"],
        }
        body = (
            "Goal: run a marathon\n"
            "I can train 5 hours per week.\n"
            "Sports: running, strength."
        )
        updates = profile_module.parse_profile_updates_from_email(body)
        self.assertEqual(updates.get("goal"), "run a marathon")
        self.assertEqual(updates.get("weekly_time_budget_minutes"), 300)
        self.assertEqual(sorted(updates.get("sports", [])), ["running", "strength"])

    @mock.patch("profile.ProfileExtractor.extract_profile_fields")
    def test_unknown_markers_from_llm_flags(self, mock_extract):
        mock_extract.return_value = {
            "goal": None,
            "goal_unknown": True,
            "weekly_time_budget_minutes": None,
            "weekly_time_budget_unknown": True,
            "sports": None,
            "sports_unknown": True,
        }
        body = "User did not specify details."
        updates = profile_module.parse_profile_updates_from_email(body)
        self.assertTrue(updates.get("goal_unknown"))
        self.assertTrue(updates.get("weekly_time_budget_unknown"))
        self.assertTrue(updates.get("sports_unknown"))

    @mock.patch("profile.ProfileExtractor.extract_profile_fields")
    def test_unknown_markers_from_text_fallback(self, mock_extract):
        # LLM omits unknown flags, but text contains explicit unknown markers.
        mock_extract.return_value = {}
        body = "My goal is unknown. Weekly time not sure. Sports n/a"
        updates = profile_module.parse_profile_updates_from_email(body)
        self.assertTrue(updates.get("goal_unknown"))
        self.assertTrue(updates.get("weekly_time_budget_unknown"))
        self.assertTrue(updates.get("sports_unknown"))

    @mock.patch("profile.ProfileExtractor.extract_profile_fields")
    def test_llm_failure_fails_closed(self, mock_extract):
        mock_extract.side_effect = ProfileExtractionError("boom")
        body = "Goal: run a marathon"
        updates = profile_module.parse_profile_updates_from_email(body)
        # On extraction failure, no updates are applied.
        self.assertEqual(updates, {})


class TestGetMissingRequiredProfileFields(unittest.TestCase):
    def test_all_missing(self):
        self.assertEqual(
            profile_module.get_missing_required_profile_fields({}),
            ["goal", "weekly_time_budget_minutes", "sports"],
        )

    def test_none_missing(self):
        profile = {
            "goal": "10k",
            "weekly_time_budget_minutes": 60,
            "sports": ["running"],
        }
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), [])

    def test_unknown_markers_count_as_provided(self):
        profile = {"goal_unknown": True, "weekly_time_budget_unknown": True, "sports_unknown": True}
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), [])


class TestBuildProfileCollectionReply(unittest.TestCase):
    def test_lists_missing_fields(self):
        reply = profile_module.build_profile_collection_reply(
            ["goal", "weekly_time_budget_minutes", "sports"]
        )
        self.assertIn("training goal", reply)
        self.assertIn("weekly time budget", reply)
        self.assertIn("Sports", reply)
        self.assertIn("unknown", reply)


if __name__ == "__main__":
    unittest.main()
