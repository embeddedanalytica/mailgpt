import sys
import types
import unittest
from pathlib import Path
from contextlib import nullcontext
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[3]
TOOLS_PATH = REPO_ROOT / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

short_bench_stub = types.ModuleType("athlete_memory_bench_runner")
short_bench_stub.OK = "OK"
short_bench_stub.ASSERTION_FAILED = "ASSERTION_FAILED"
short_bench_stub.REFRESH_ERROR = "REFRESH_ERROR"
short_bench_stub.STORE_ERROR = "STORE_ERROR"
short_bench_stub.EXCEPTION = "EXCEPTION"
short_bench_stub.COACH_READY = "COACH_READY"
short_bench_stub.MEMORY_OK_BUT_NOISY = "MEMORY_OK_BUT_NOISY"
short_bench_stub.UNSAFE_FOR_COACHING = "UNSAFE_FOR_COACHING"
short_bench_stub._note_texts = lambda notes: [str(item.get("summary", "")).lower() for item in notes if isinstance(item, dict)]
short_bench_stub._match_labels = lambda facts, texts: ([], [])
short_bench_stub._fact_matches_any_text = lambda fact, texts: False
short_bench_stub._dimension_state = lambda score: "pass" if score >= 1.0 else "fail"
short_bench_stub.evaluate_step_result = lambda current_notes, continuity_summary, expectations: {
    "dimensions": {},
    "key_misses": [],
    "findings": [],
    "critical_failures": [],
    "stale_assumption_risks": [],
    "over_retention_flags": [],
}
short_bench_stub.apply_benchmark_memory_refresh = lambda athlete_id, latest_interaction_context: {}
short_bench_stub.get_benchmark_memory_notes = lambda athlete_id: {"memory_notes": []}
short_bench_stub.get_benchmark_retrieval_context = lambda athlete_id: {"memory_notes": []}
short_bench_stub.evaluate_final_retrieval = lambda current_notes, retrieval_context, final_assertions: {
    "status": "OK",
    "score": 1.0,
    "findings": [],
    "durable_missing": [],
    "retrieval_missing": [],
    "retired_present": [],
}
short_bench_stub.local_fake_storage = nullcontext
short_bench_stub.nullcontext = nullcontext
short_bench_stub.use_live_dynamo = lambda: False
short_bench_stub.require_prerequisites = lambda bench_path, max_parallel=1: None
sys.modules.setdefault("athlete_memory_bench_runner", short_bench_stub)

import athlete_memory_long_horizon_bench_runner as runner


class TestAthleteMemoryLongHorizonBenchRunner(unittest.TestCase):
    def test_run_single_scenario_records_assertion_failure_and_continues(self):
        scenario = {
            "id": "AM-LH-T1",
            "athlete_name": "Test Athlete",
            "sport": "running",
            "profile_hint": "test",
            "phases": [
                {
                    "phase_id": "phase_1",
                    "phase_goal": "exercise checkpoint failure handling",
                    "messages": [
                        {
                            "step": 1,
                            "email": "first update",
                            "synthetic_coach_reply": "reply one",
                        },
                        {
                            "step": 2,
                            "email": "second update",
                            "synthetic_coach_reply": "reply two",
                        },
                    ],
                    "checkpoint_assertions": {
                        "label": "phase one checkpoint",
                        "durable_truths": [],
                        "active_context": [],
                        "retired_truths": [],
                        "routine_noise": [],
                        "coach_should_adjust_for": [],
                        "coach_should_not_do": [],
                    },
                }
            ],
            "final_assertions": {
                "final_durable_truths": [],
                "final_retrieval_support": [],
                "final_retired_truths": [],
            },
        }

        memory_state = {"memory_notes": [{"summary": "kept fact"}]}
        retrieval_context = {"memory_notes": ["kept fact"]}

        with (
            patch.object(runner.short_bench, "apply_benchmark_memory_refresh", return_value={}),
            patch.object(runner.short_bench, "get_benchmark_memory_notes", return_value=memory_state),
            patch.object(runner.dynamodb_models, "get_continuity_summary", return_value={"summary": "continuity"}),
            patch.object(runner.short_bench, "get_benchmark_retrieval_context", return_value=retrieval_context),
            patch.object(
                runner,
                "evaluate_checkpoint_result",
                return_value={
                    "status": runner.ASSERTION_FAILED,
                    "label": runner.UNSAFE_FOR_COACHING,
                    "score": 0.0,
                    "critical_failures": ["durable_memory_quality"],
                    "findings": ["checkpoint assertion failed"],
                    "key_misses": ["durable fact"],
                    "stale_assumption_risks": [],
                    "over_retention_flags": [],
                    "dimensions": {},
                },
            ) as evaluate_checkpoint_result,
            patch.object(
                runner.short_bench,
                "evaluate_final_retrieval",
                return_value={
                    "status": runner.OK,
                    "score": 1.0,
                    "findings": [],
                    "durable_missing": [],
                    "retrieval_missing": [],
                    "retired_present": [],
                },
            ) as evaluate_final_retrieval,
        ):
            result = runner.run_single_scenario(scenario)

        self.assertEqual(result["status"], runner.ASSERTION_FAILED)
        self.assertEqual(len(result["step_results"]), 2)
        self.assertEqual(len(result["checkpoint_results"]), 1)
        self.assertIsNotNone(result["final_evaluation"])
        self.assertEqual(result["final_evaluation"]["status"], runner.OK)
        evaluate_checkpoint_result.assert_called_once()
        evaluate_final_retrieval.assert_called_once()


if __name__ == "__main__":
    unittest.main()
