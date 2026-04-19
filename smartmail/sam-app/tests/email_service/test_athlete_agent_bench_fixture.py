import json
import tempfile
import textwrap
import unittest
from pathlib import Path

import athlete_agent_bench_fixture


def _valid_scenario(scenario_id: str = "LAS-001") -> dict:
    return {
        "id": scenario_id,
        "name": "sample",
        "athlete_brief": "Athlete brief",
        "judge_brief": "Judge brief",
        "opening_message": "First message",
        "evaluation_focus": ["focus one", "focus two"],
        "min_turns": 10,
        "max_turns": 12,
        "conversation_phases": [
            {
                "label": "intake",
                "start_turn": 1,
                "end_turn": 3,
                "objective": "Share constraints",
                "suggested_reveals": ["schedule"],
                "suggested_actions": ["ask for a first plan"],
            }
        ],
    }


class TestAthleteAgentBenchFixture(unittest.TestCase):
    def _write_fixture(self, payload: list[dict]) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(
            "# fixture\n\n```json\n" + json.dumps(payload, indent=2) + "\n```\n",
            encoding="utf-8",
        )
        return path

    def test_loads_real_fixture(self):
        scenarios = athlete_agent_bench_fixture.load_athlete_agent_bench_scenarios(
            athlete_agent_bench_fixture.DEFAULT_BENCH_PATH
        )
        self.assertGreaterEqual(len(scenarios), 3)
        self.assertTrue(all(item["min_turns"] == 20 for item in scenarios))
        self.assertTrue(all(item["max_turns"] == 25 for item in scenarios))
        first = scenarios[0]
        self.assertIn("half marathon in the autumn", first["athlete_brief"])
        self.assertIn("spring full marathon", first["athlete_brief"])
        self.assertIn("long-horizon", first["judge_brief"])
        self.assertIn("20-25 turns", first["athlete_brief"])
        self.assertIn("turns 5-6", first["athlete_brief"])
        self.assertIn("resting HR roughly 55-75", first["athlete_brief"])
        self.assertGreaterEqual(len(first["conversation_phases"]), 3)
        self.assertEqual(first["conversation_phases"][0]["label"], "intake")
        self.assertGreaterEqual(len(first["communication_style_preferences"]), 1)

    def test_duplicate_ids_fail(self):
        fixture = self._write_fixture([_valid_scenario("LAS-001"), _valid_scenario("LAS-001")])
        with self.assertRaisesRegex(ValueError, "Duplicate scenario id"):
            athlete_agent_bench_fixture.load_athlete_agent_bench_scenarios(fixture)

    def test_turn_bounds_fail_when_min_exceeds_max(self):
        scenario = _valid_scenario()
        scenario["min_turns"] = 13
        scenario["max_turns"] = 12
        fixture = self._write_fixture([scenario])
        with self.assertRaisesRegex(ValueError, "min_turns cannot be greater than max_turns"):
            athlete_agent_bench_fixture.load_athlete_agent_bench_scenarios(fixture)

    def test_conversation_phases_must_be_ordered_and_within_bounds(self):
        scenario = _valid_scenario()
        scenario["conversation_phases"] = [
            {
                "label": "late",
                "start_turn": 4,
                "end_turn": 6,
                "objective": "Later",
            },
            {
                "label": "early",
                "start_turn": 3,
                "end_turn": 4,
                "objective": "Earlier",
            },
        ]
        fixture = self._write_fixture([scenario])
        with self.assertRaisesRegex(ValueError, "start_turn must be greater than the previous end_turn"):
            athlete_agent_bench_fixture.load_athlete_agent_bench_scenarios(fixture)

    def test_missing_json_block_fails(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(textwrap.dedent("# fixture\n\nno json block\n"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "No JSON block"):
            athlete_agent_bench_fixture.load_athlete_agent_bench_scenarios(path)

    def test_malformed_json_fails(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(
            textwrap.dedent(
                """
                # fixture
                ```json
                [{"id":"LAS-001","name":"bad","athlete_brief":"a","judge_brief":"b"}
                ```
                """
            ),
            encoding="utf-8",
        )
        with self.assertRaisesRegex(ValueError, "Invalid JSON block"):
            athlete_agent_bench_fixture.load_athlete_agent_bench_scenarios(path)


if __name__ == "__main__":
    unittest.main()
