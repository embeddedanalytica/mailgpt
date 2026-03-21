"""Unit tests for AM3 unified memory refresh reducer."""

import unittest

from athlete_memory_reducer import apply_unified_refresh


class TestApplyUnifiedRefresh(unittest.TestCase):
    """Tests for apply_unified_refresh (AM3 reducer)."""

    def setUp(self):
        self.apply = apply_unified_refresh
        self.now = 1710700000

    def _make_llm_output(self, **overrides):
        base = {
            "backbone": {
                "primary_goal": "Run a sub-3:30 marathon in October",
                "weekly_structure": "4 days/week: Tue, Thu, Sat, Sun",
                "hard_constraints": "No running before 6am due to family",
                "training_preferences": None,
            },
            "context_notes": [
                {"label": "Power meter", "summary": "Owns a Garmin power meter for cycling"},
            ],
            "continuity": {
                "summary": "Athlete completed first tempo run this week",
                "last_recommendation": "Add strides to easy runs next week",
                "open_loops": ["Confirm tempo pace felt manageable"],
            },
        }
        base.update(overrides)
        return base

    def test_full_output_structure(self):
        result = self.apply(self._make_llm_output(), self.now)
        self.assertIn("backbone", result)
        self.assertIn("context_notes", result)
        self.assertIn("continuity_summary", result)

    def test_backbone_timestamps_populated_slots(self):
        result = self.apply(self._make_llm_output(), self.now)
        bb = result["backbone"]
        self.assertEqual(bb["primary_goal"]["summary"], "Run a sub-3:30 marathon in October")
        self.assertEqual(bb["primary_goal"]["updated_at"], self.now)
        self.assertEqual(bb["weekly_structure"]["updated_at"], self.now)
        self.assertEqual(bb["hard_constraints"]["updated_at"], self.now)

    def test_backbone_null_slots_preserved(self):
        result = self.apply(self._make_llm_output(), self.now)
        bb = result["backbone"]
        self.assertIsNone(bb["training_preferences"]["summary"])
        self.assertIsNone(bb["training_preferences"]["updated_at"])

    def test_all_backbone_null(self):
        llm = self._make_llm_output(backbone={
            "primary_goal": None,
            "weekly_structure": None,
            "hard_constraints": None,
            "training_preferences": None,
        })
        result = self.apply(llm, self.now)
        for key in ("primary_goal", "weekly_structure", "hard_constraints", "training_preferences"):
            self.assertIsNone(result["backbone"][key]["summary"])
            self.assertIsNone(result["backbone"][key]["updated_at"])

    def test_context_notes_timestamped(self):
        result = self.apply(self._make_llm_output(), self.now)
        notes = result["context_notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["label"], "Power meter")
        self.assertEqual(notes[0]["updated_at"], self.now)

    def test_context_notes_empty(self):
        llm = self._make_llm_output(context_notes=[])
        result = self.apply(llm, self.now)
        self.assertEqual(result["context_notes"], [])

    def test_context_notes_truncated_to_max(self):
        notes = [
            {"label": f"Note {i}", "summary": f"Summary {i}"}
            for i in range(6)
        ]
        llm = self._make_llm_output(context_notes=notes)
        result = self.apply(llm, self.now)
        self.assertEqual(len(result["context_notes"]), 4)

    def test_continuity_summary_structure(self):
        result = self.apply(self._make_llm_output(), self.now)
        cs = result["continuity_summary"]
        self.assertEqual(cs["summary"], "Athlete completed first tempo run this week")
        self.assertEqual(cs["last_recommendation"], "Add strides to easy runs next week")
        self.assertEqual(cs["open_loops"], ["Confirm tempo pace felt manageable"])
        self.assertEqual(cs["updated_at"], self.now)

    def test_continuity_empty_open_loops(self):
        llm = self._make_llm_output()
        llm["continuity"]["open_loops"] = []
        result = self.apply(llm, self.now)
        self.assertEqual(result["continuity_summary"]["open_loops"], [])

    def test_round_trip_through_contract(self):
        """Result should be valid when re-read through contract validators."""
        from athlete_memory_contract import validate_backbone_slots, validate_context_note_list, ContinuitySummary
        result = self.apply(self._make_llm_output(), self.now)
        bb = validate_backbone_slots(result["backbone"])
        self.assertEqual(bb.primary_goal.summary, "Run a sub-3:30 marathon in October")
        notes = validate_context_note_list(result["context_notes"])
        self.assertEqual(len(notes), 1)
        cs = ContinuitySummary.from_dict(result["continuity_summary"])
        self.assertEqual(cs.summary, "Athlete completed first tempo run this week")


if __name__ == "__main__":
    unittest.main()
