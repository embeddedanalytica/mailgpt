"""Unit tests for profile extraction and gating."""
import unittest
from unittest import mock

import profile as profile_module
from skills.planner import ProfileExtractionProposalError

_INJURY_STATUS_NONE = {"has_injuries": False}
_INJURY_STATUS_YES = {"has_injuries": True}
_INJURY_KNEE = {"type": "injury", "summary": "Left knee pain", "severity": "medium", "active": True}


class TestParseProfileUpdates(unittest.TestCase):
    @mock.patch("profile.run_profile_extraction_workflow")
    def test_parses_core_fields(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "run a marathon  ",
            "time_availability": {"sessions_per_week": 4, "hours_per_week": 6},
            "experience_level": "Intermediate",
            "experience_level_note": "returning after break",
            "constraints": [{"type": "schedule", "summary": "weekday mornings only", "severity": "low", "active": True}],
            "injury_status": _INJURY_STATUS_YES,
            "injury_constraints": [_INJURY_KNEE],
        }
        updates = profile_module.parse_profile_updates_from_email("body")
        self.assertEqual(updates.get("primary_goal"), "run a marathon")
        self.assertEqual(updates.get("time_availability", {}).get("sessions_per_week"), 4)
        self.assertEqual(updates.get("time_availability", {}).get("hours_per_week"), 6.0)
        self.assertEqual(updates.get("experience_level"), "intermediate")
        self.assertEqual(updates.get("experience_level_note"), "returning after break")
        self.assertEqual(len(updates.get("constraints", [])), 1)
        self.assertEqual(updates.get("injury_status"), _INJURY_STATUS_YES)
        self.assertEqual(len(updates.get("injury_constraints", [])), 1)

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_injury_status_no_injuries_persisted(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": None,
            "time_availability": None,
            "experience_level": "unknown",
            "experience_level_note": None,
            "constraints": None,
            "injury_status": _INJURY_STATUS_NONE,
            "injury_constraints": None,
        }
        updates = profile_module.parse_profile_updates_from_email("No injuries at all.")
        self.assertEqual(updates.get("injury_status"), _INJURY_STATUS_NONE)
        self.assertNotIn("injury_constraints", updates)

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_null_injury_status_not_persisted(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "stay fit",
            "time_availability": None,
            "experience_level": "unknown",
            "experience_level_note": None,
            "constraints": None,
            "injury_status": None,
            "injury_constraints": None,
        }
        updates = profile_module.parse_profile_updates_from_email("I want to stay fit.")
        self.assertNotIn("injury_status", updates)
        self.assertNotIn("injury_constraints", updates)

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_empty_constraints_list_not_persisted(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "build consistency",
            "time_availability": None,
            "experience_level": "unknown",
            "experience_level_note": None,
            "constraints": [],
            "injury_status": None,
            "injury_constraints": None,
        }
        updates = profile_module.parse_profile_updates_from_email("Not sure on schedule yet.")
        self.assertNotIn("time_availability", updates)
        self.assertNotIn("constraints", updates)
        self.assertNotIn("injury_status", updates)
        self.assertNotIn("injury_constraints", updates)

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_defaults_experience_to_unknown_when_missing(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": "stay healthy",
            "time_availability": {"hours_per_week": 3},
        }
        updates = profile_module.parse_profile_updates_from_email("I want to stay healthy.")
        self.assertEqual(updates.get("experience_level"), "unknown")

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_llm_failure_fails_closed(self, mock_extract):
        mock_extract.side_effect = ProfileExtractionProposalError("boom")
        updates = profile_module.parse_profile_updates_from_email("Goal: run a marathon")
        self.assertEqual(updates, {})

    @mock.patch("profile.run_profile_extraction_workflow")
    def test_sessions_per_week_extracted(self, mock_extract):
        mock_extract.return_value = {
            "primary_goal": None,
            "time_availability": {"sessions_per_week": 4, "hours_per_week": None},
            "experience_level": "intermediate",
            "experience_level_note": None,
            "constraints": None,
            "injury_constraints": None,
        }
        updates = profile_module.parse_profile_updates_from_email("I can train four days a week.")
        self.assertEqual(updates.get("time_availability", {}).get("sessions_per_week"), 4)


class TestGetMissingRequiredProfileFields(unittest.TestCase):
    def _complete_profile(self, **overrides):
        base = {
            "primary_goal": "10k PR",
            "time_availability": {"hours_per_week": 4.5},
            "experience_level": "unknown",
            "injury_status": _INJURY_STATUS_NONE,
        }
        base.update(overrides)
        return base

    def test_all_missing_on_empty_profile(self):
        self.assertEqual(
            profile_module.get_missing_required_profile_fields({}),
            ["primary_goal", "time_availability", "experience_level", "injury_status"],
        )

    def test_none_missing_when_profile_complete(self):
        self.assertEqual(
            profile_module.get_missing_required_profile_fields(self._complete_profile()),
            [],
        )

    def test_injury_missing_when_no_injury_status(self):
        profile = self._complete_profile()
        del profile["injury_status"]
        self.assertIn("injury_status", profile_module.get_missing_required_profile_fields(profile))

    def test_injury_missing_when_injury_status_null(self):
        profile = self._complete_profile(injury_status=None)
        self.assertIn("injury_status", profile_module.get_missing_required_profile_fields(profile))

    def test_schedule_only_profile_still_missing_injury(self):
        # Having a general constraint (schedule) does NOT complete the injury gate.
        profile = self._complete_profile()
        del profile["injury_status"]
        profile["constraints"] = [{"type": "schedule", "summary": "mornings only", "severity": "low", "active": True}]
        self.assertIn("injury_status", profile_module.get_missing_required_profile_fields(profile))

    def test_null_time_availability_is_missing(self):
        profile = self._complete_profile(time_availability=None)
        self.assertIn("time_availability", profile_module.get_missing_required_profile_fields(profile))

    def test_missing_primary_goal(self):
        profile = self._complete_profile(primary_goal="")
        self.assertIn("primary_goal", profile_module.get_missing_required_profile_fields(profile))

    def test_injury_status_true_completes_gate(self):
        profile = self._complete_profile(
            injury_status=_INJURY_STATUS_YES,
            injury_constraints=[_INJURY_KNEE],
        )
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), [])

    def test_injury_status_false_completes_gate(self):
        profile = self._complete_profile(injury_status=_INJURY_STATUS_NONE)
        self.assertEqual(profile_module.get_missing_required_profile_fields(profile), [])


if __name__ == "__main__":
    unittest.main()
