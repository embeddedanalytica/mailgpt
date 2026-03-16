import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import response_generation_bench_runner


def _scenario() -> dict:
    return {
        "id": "RG-001",
        "name": "sample_scenario",
        "response_brief": {
            "reply_mode": "normal_coaching",
            "athlete_context": {"goal_summary": "10k in 8 weeks"},
            "decision_context": {"risk_flag": "green"},
            "validated_plan": {"plan_summary": "Simple plan"},
            "delivery_context": {"response_channel": "email"},
            "memory_context": {
                "pre_reply_refresh_attempted": False,
                "post_reply_refresh_eligible": True,
                "memory_notes": [],
                "continuity_summary": None,
                "memory_available": False,
            },
        },
        "review_focus": ["tone", "clarity"],
        "notes": "test notes",
    }


class TestResponseGenerationBenchRunner(unittest.TestCase):
    def test_scenario_filtering(self):
        scenarios = [_scenario(), {**_scenario(), "id": "RG-002", "name": "other"}]
        selected = response_generation_bench_runner.select_scenarios(scenarios, ["rg-002"])
        self.assertEqual([item["id"] for item in selected], ["RG-002"])

    def test_run_single_attempt_success_shape(self):
        with mock.patch.object(
            response_generation_bench_runner,
            "run_response_generation_workflow",
            return_value={"final_email_body": "Keep this week controlled.\n\nOne quality session only."},
        ):
            result = response_generation_bench_runner.run_single_attempt(
                scenario=_scenario(),
                attempt=1,
                model_name="gpt-5-mini",
            )
        self.assertEqual(result["status"], response_generation_bench_runner.OK)
        self.assertEqual(result["line_count"], 2)
        self.assertGreater(result["char_count"], 10)
        self.assertIn("final_email_body", result)

    def test_run_single_attempt_failure_capture(self):
        with mock.patch.object(
            response_generation_bench_runner,
            "run_response_generation_workflow",
            side_effect=response_generation_bench_runner.ResponseGenerationProposalError("invalid_json_response"),
        ):
            result = response_generation_bench_runner.run_single_attempt(
                scenario=_scenario(),
                attempt=1,
                model_name=None,
            )
        self.assertEqual(result["status"], response_generation_bench_runner.ERROR)
        self.assertIn("invalid_json_response", result["error"])
        self.assertEqual(result["char_count"], 0)

    def test_summary_writers_emit_expected_sections(self):
        scenario = _scenario()
        runs = [
            {
                "scenario_id": "RG-001",
                "scenario_name": "sample_scenario",
                "attempt": 1,
                "started_at": "2026-01-01T00:00:00+00:00",
                "ended_at": "2026-01-01T00:00:01+00:00",
                "model_name": "gpt-5-mini",
                "review_focus": ["tone"],
                "notes": "n1",
                "status": response_generation_bench_runner.OK,
                "error": None,
                "duration_seconds": 1.0,
                "final_email_body": "Good work.\nKeep it controlled.",
                "line_count": 2,
                "char_count": 30,
                "response_payload": {"final_email_body": "Good work.\nKeep it controlled."},
            },
            {
                "scenario_id": "RG-001",
                "scenario_name": "sample_scenario",
                "attempt": 2,
                "started_at": "2026-01-01T00:00:02+00:00",
                "ended_at": "2026-01-01T00:00:03+00:00",
                "model_name": "gpt-5-mini",
                "review_focus": ["tone"],
                "notes": "n1",
                "status": response_generation_bench_runner.ERROR,
                "error": "response generation failed",
                "duration_seconds": 1.1,
                "final_email_body": "",
                "line_count": 0,
                "char_count": 0,
                "response_payload": None,
            },
        ]
        summary = response_generation_bench_runner.aggregate_results(
            scenarios=[scenario],
            runs=runs,
            runs_per_scenario=2,
            max_parallel=1,
            bench_path=Path("/tmp/response_generation_quality_bench.md"),
            output_dir=Path("/tmp/out"),
        )

        with tempfile.TemporaryDirectory() as td:
            summary_path = Path(td) / "summary.md"
            results_path = Path(td) / "results.json"
            response_generation_bench_runner.write_summary_markdown(summary, summary_path)
            response_generation_bench_runner.write_results_json(summary, results_path)
            summary_text = summary_path.read_text(encoding="utf-8")
            results_text = results_path.read_text(encoding="utf-8")

        self.assertIn("## Per-Scenario Status", summary_text)
        self.assertIn("## Run Outcomes", summary_text)
        self.assertIn("RG-001", summary_text)
        self.assertIn('"total_runs": 2', results_text)


if __name__ == "__main__":
    unittest.main()
