import tempfile
import textwrap
import unittest
from pathlib import Path

import planner_bench_fixture


class TestPlannerBenchFixture(unittest.TestCase):
    def _write_fixture(self, body: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        path = Path(temp_dir.name) / "fixture.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_loads_json_block(self):
        fixture = self._write_fixture(
            textwrap.dedent(
                """
                # Fixture
                ```json
                [
                  {
                    "id": "PS-001",
                    "name": "sample",
                    "profile": {"goal_category": "general_consistency"},
                    "checkin": {"days_available": 3},
                    "phase": "base",
                    "risk_flag": "green",
                    "track": "general_low_time",
                    "effective_performance_intent": false,
                    "fallback_skeleton": ["easy_aerobic"],
                    "required_goal_tokens": ["easy_aerobic"]
                  }
                ]
                ```
                """
            )
        )
        scenarios = planner_bench_fixture.load_plan_bench_scenarios(fixture)
        self.assertEqual(len(scenarios), 1)
        self.assertEqual(scenarios[0]["id"], "PS-001")
        self.assertEqual(scenarios[0]["fallback_skeleton"], ["easy_aerobic"])

    def test_missing_required_fields(self):
        fixture = self._write_fixture(
            textwrap.dedent(
                """
                ```json
                [
                  {
                    "id": "PS-001",
                    "name": "missing_fields"
                  }
                ]
                ```
                """
            )
        )
        with self.assertRaisesRegex(ValueError, "missing fields"):
            planner_bench_fixture.load_plan_bench_scenarios(fixture)

    def test_duplicate_ids(self):
        fixture = self._write_fixture(
            textwrap.dedent(
                """
                ```json
                [
                  {
                    "id": "PS-001",
                    "name": "one",
                    "profile": {},
                    "checkin": {},
                    "phase": "base",
                    "risk_flag": "green",
                    "track": "general_low_time",
                    "effective_performance_intent": false,
                    "fallback_skeleton": ["easy_aerobic"],
                    "required_goal_tokens": ["easy_aerobic"]
                  },
                  {
                    "id": "PS-001",
                    "name": "two",
                    "profile": {},
                    "checkin": {},
                    "phase": "base",
                    "risk_flag": "green",
                    "track": "general_low_time",
                    "effective_performance_intent": false,
                    "fallback_skeleton": ["easy_aerobic"],
                    "required_goal_tokens": ["easy_aerobic"]
                  }
                ]
                ```
                """
            )
        )
        with self.assertRaisesRegex(ValueError, "Duplicate scenario id"):
            planner_bench_fixture.load_plan_bench_scenarios(fixture)

    def test_invalid_scenario_shape(self):
        fixture = self._write_fixture(
            textwrap.dedent(
                """
                ```json
                [
                  {
                    "id": "PS-001",
                    "name": "invalid_shape",
                    "profile": {},
                    "checkin": {},
                    "phase": "base",
                    "risk_flag": "green",
                    "track": "general_low_time",
                    "effective_performance_intent": "false",
                    "fallback_skeleton": ["easy_aerobic"],
                    "required_goal_tokens": ["easy_aerobic"]
                  }
                ]
                ```
                """
            )
        )
        with self.assertRaisesRegex(ValueError, "must be a boolean"):
            planner_bench_fixture.load_plan_bench_scenarios(fixture)


if __name__ == "__main__":
    unittest.main()
