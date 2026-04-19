import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

TOOLS_PATH = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import planner_bench_runner


def _scenario() -> dict:
    return {
        "id": "PS-001",
        "name": "new_athlete_constrained_start",
        "profile": {
            "goal_category": "general_consistency",
            "main_sport_current": "run",
            "time_bucket": "2_3h",
            "structure_preference": "structure",
        },
        "checkin": {"days_available": 3, "structure_preference": "structure", "has_upcoming_event": False},
        "phase": "base",
        "risk_flag": "yellow",
        "track": "general_low_time",
        "effective_performance_intent": False,
        "fallback_skeleton": ["easy_aerobic", "strength", "easy_aerobic"],
        "required_goal_tokens": ["easy_aerobic", "strength"],
    }


class TestPlannerBenchRunner(unittest.TestCase):
    def test_scenario_filtering(self):
        scenarios = [_scenario(), {**_scenario(), "id": "PS-002", "name": "other"}]
        selected = planner_bench_runner.select_scenarios(scenarios, ["ps-002"])
        self.assertEqual([item["id"] for item in selected], ["PS-002"])

    def test_run_single_attempt_raw_valid(self):
        with mock.patch.object(
            planner_bench_runner.PlanningLLM,
            "propose_plan",
            return_value={
                "plan_proposal": {"weekly_skeleton": ["easy_aerobic", "strength"]},
                "rationale": "safe",
                "non_binding_state_suggestions": [],
            },
        ):
            result = planner_bench_runner.run_single_attempt(
                scenario=_scenario(),
                attempt=1,
                model_name=None,
            )
        self.assertEqual(result["status"], planner_bench_runner.OK_RAW_VALID)
        self.assertTrue(result["validation"]["is_valid"])

    def test_run_single_attempt_repaired(self):
        with mock.patch.object(
            planner_bench_runner.PlanningLLM,
            "propose_plan",
            return_value={
                "plan_proposal": {"weekly_skeleton": ["unknown_tag", "tempo"]},
                "rationale": "unsafe",
                "non_binding_state_suggestions": [],
            },
        ):
            result = planner_bench_runner.run_single_attempt(
                scenario=_scenario(),
                attempt=1,
                model_name=None,
            )
        self.assertEqual(result["status"], planner_bench_runner.OK_REPAIRED)
        self.assertIn("unknown_session_tag", result["validation"]["errors"])
        self.assertIsInstance(result["repair_result"], dict)

    def test_aggregate_distinct_shape_counts(self):
        scenario = _scenario()
        runs = [
            {
                "scenario_id": "PS-001",
                "scenario_name": scenario["name"],
                "attempt": 1,
                "status": planner_bench_runner.OK_RAW_VALID,
                "raw_plan_proposal": {"weekly_skeleton": ["easy_aerobic", "strength"]},
            },
            {
                "scenario_id": "PS-001",
                "scenario_name": scenario["name"],
                "attempt": 2,
                "status": planner_bench_runner.OK_RAW_VALID,
                "raw_plan_proposal": {"weekly_skeleton": ["strength", "easy_aerobic"]},
            },
            {
                "scenario_id": "PS-001",
                "scenario_name": scenario["name"],
                "attempt": 3,
                "status": planner_bench_runner.OK_REPAIRED,
                "raw_plan_proposal": {"weekly_skeleton": ["tempo", "unknown_tag"]},
            },
        ]
        summary = planner_bench_runner.aggregate_results(
            scenarios=[scenario],
            runs=runs,
            attempts=3,
            max_parallel=1,
            bench_path=Path("/tmp/bench.md"),
            output_dir=Path("/tmp/out"),
        )
        per = summary["per_scenario"][0]
        self.assertEqual(per["unique_raw_valid_skeleton_count"], 2)
        self.assertEqual(per["unique_raw_skeleton_count"], 3)
        self.assertTrue(per["diverse_valid_output"])

    def test_write_summary_contains_sections(self):
        summary = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "benchmark_path": "/tmp/bench.md",
            "output_dir": "/tmp/out",
            "total_scenarios": 1,
            "total_runs": 2,
            "raw_valid_runs": 1,
            "repaired_runs": 1,
            "failed_runs": 0,
            "raw_valid_rate": 0.5,
            "per_scenario": [
                {
                    "scenario_id": "PS-001",
                    "scenario_name": "s1",
                    "raw_valid_count": 1,
                    "attempts": 2,
                    "repaired_count": 1,
                    "failed_count": 0,
                    "unique_raw_valid_skeleton_count": 1,
                }
            ],
            "runs": [
                {
                    "scenario_id": "PS-001",
                    "attempt": 2,
                    "status": planner_bench_runner.OK_REPAIRED,
                    "repair_result": {"source": "deterministic_fallback"},
                    "validation": {"errors": ["unknown_session_tag"]},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            summary_path = Path(td) / "summary.md"
            planner_bench_runner.write_summary(summary, summary_path)
            text = summary_path.read_text(encoding="utf-8")
        self.assertIn("## Per-Scenario Results", text)
        self.assertIn("## Low Diversity Scenarios", text)
        self.assertIn("## Invalid Raw Outputs", text)


if __name__ == "__main__":
    unittest.main()
