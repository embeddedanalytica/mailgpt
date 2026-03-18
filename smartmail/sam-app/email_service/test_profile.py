"""Unit tests for refined profile extraction and gating."""
import unittest
from unittest import mock

import profile as profile_module
from skills.planner import ProfileExtractionProposalError


class TestParseProfileUpdates(unittest.TestCase):
    @mock.patch("profile.run_profile_extraction_workflow")
    def test_parses_refined_profile_fields(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "run a marathon  ",
            "time_availability": {"sessions_per_week": 4, "hours_per_week": 6},
            "experience_level": "Intermediate",
            "experience_level_note": "returning after break",
            "constraints": [
                {"type": "injury", "summary": "left knee pain", "severity": "medium", "active": True},
                {"type": "schedule", "summary": "weekday mornings only"},
            ],
        }
        body = "My goal is marathon. I can do 4 sessions or 6 hours weekly."
        updates = profile_module.parse_profile_updates_from_email(body)
        self.assertEqual(updates.get("primary_goal"), "run a marathon")
        self.assertEqual(updates.get("time_availability", {}).get("sessions_per_week"), 4)
        self.assertEqual(updates.get("time_availability", {}).get("hours_per_week"), 6.0)
        self.assertEqual(updates.get("experience_level"), "intermediate")
        self.assertEqual(updates.get("experience_level_note"), "returning after break")
        self.assertEqual(len(updates.get("constraints", [])), 2)

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_defaults_experience_to_unknown_when_missing(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "stay healthy",
            "time_availability": {"hours_per_week": 3},
        }
        body = "I want to stay healthy."
        updates = profile_module.parse_profile_updates_from_email(body)
        self.assertEqual(updates.get("experience_level"), "unknown")

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_llm_failure_fails_closed(self, mock_extract):
        mock_extract.side_effect = ProfileExtractionProposalError("boom")
        body = "Goal: run a marathon"
        updates = profile_module.parse_profile_updates_from_email(body)
        # On extraction failure, no updates are applied.
        self.assertEqual(updates, {})

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_spelled_schedule_phrase_is_applied_when_extractor_returns_sessions(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": None,
            "time_availability": {"sessions_per_week": 4, "hours_per_week": None},
            "experience_level": "intermediate",
            "experience_level_note": None,
            "constraints": None,
        }
        body = "I can train four days a week most weeks if we keep it realistic."
        updates = profile_module.parse_profile_updates_from_email(body)
        self.assertEqual(updates.get("time_availability", {}).get("sessions_per_week"), 4)

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_nullable_unknown_time_availability_keeps_time_missing(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "build consistency",
            "time_availability": None,
            "experience_level": "unknown",
            "experience_level_note": None,
            "constraints": [],
        }
        updates = profile_module.parse_profile_updates_from_email("Not sure on schedule yet.")
        self.assertNotIn("time_availability", updates)


class TestGetMissingRequiredProfileFields(unittest.TestCase):
    def test_all_missing(self):
        self.assertEqual(
            profile_module.get_missing_required_profile_fields({}),
            ["primary_goal", "time_availability", "experience_level", "constraints"],
        )

    def test_none_missing(self):
        profile = {
            "primary_goal": "10k PR",
            "time_availability": {"hours_per_week": 4.5},
            "experience_level": "unknown",
            "constraints": [],
        }
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), [])

    def test_missing_constraints_list_is_invalid(self):
        profile = {
            "primary_goal": "10k PR",
            "time_availability": {"sessions_per_week": 3},
            "experience_level": "beginner",
        }
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), ["constraints"])

    def test_null_time_availability_is_missing(self):
        profile = {
            "primary_goal": "10k PR",
            "time_availability": None,
            "experience_level": "unknown",
            "constraints": [],
        }
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), ["time_availability"])

if __name__ == "__main__":
    unittest.main()
