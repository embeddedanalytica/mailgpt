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
