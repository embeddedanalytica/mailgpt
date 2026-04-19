import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


TOOLS_PATH = Path(__file__).resolve().parents[3] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

EMAIL_SERVICE_PATH = Path(__file__).resolve().parents[2] / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

import prompt_feedback_loop
import prompt_pack_loader


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def _write_prompt_pack(root: Path, version: str) -> Path:
    target = root / "coach_reply" / version
    target.mkdir(parents=True, exist_ok=True)
    _write_json(
        target / "manifest.json",
        {
            "version": version,
            "created_at": "2026-03-22T00:00:00Z",
            "parent_version": None,
            "editable_surfaces": [
                "response_generation.directive_system_prompt",
                "coaching_reasoning.base_prompt",
            ],
        },
    )
    _write_json(
        target / "response_generation.json",
        {
            "directive_system_prompt_lines": [f"{version}-directive"],
        },
    )
    _write_json(target / "coaching_reasoning.json", {"base_prompt_lines": [f"{version}-coaching"]})
    return target


def _write_attempt(run_dir: Path, *, version: str, issue_tag: str = "too_vague") -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    attempt_path = run_dir / f"{version}-attempt1.jsonl"
    summary_path = run_dir / f"{version}-attempt1.summary.json"
    attempt_path.write_text(
        json.dumps(
            {
                "phase": "judge_result",
                "turn": 1,
                "result": {
                    "headline": "headline",
                    "athlete_likely_experience": "experience",
                    "improved_reply_example": "Do 4 x 5 minutes steady.",
                    "scores": {
                        "understanding": 4.0,
                        "memory_continuity": 4.0,
                        "personalization": 4.0,
                        "coaching_quality": 4.0,
                        "tone_trust": 4.0,
                        "communication_style_fit": 4.0,
                        "safety": 5.0,
                    },
                    "what_missed": ["specific guidance"],
                    "issue_tags": [issue_tag],
                    "strength_tags": ["specific_guidance"],
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(
            {
                "scenario_id": "SCENARIO_A",
                "scenario_name": "Scenario A",
                "attempt": 1,
                "run_id": f"run-{version}",
            }
        ),
        encoding="utf-8",
    )


def _candidate_aggregate(run_id: str) -> dict:
    return {
        "run_id": run_id,
        "judge_result_count": 1,
        "average_scores": {
            "understanding": 4.5,
            "memory_continuity": 4.2,
            "personalization": 4.1,
            "coaching_quality": 4.5,
            "tone_trust": 4.0,
            "communication_style_fit": 4.0,
            "safety": 5.0,
        },
        "issue_tag_counts": {"too_vague": 1},
        "strength_tag_counts": {"specific_guidance": 2},
        "examples": [
            {
                "scenario_id": "SCENARIO_A",
                "scenario_name": "Scenario A",
                "attempt": 1,
                "turn": 1,
                "headline": "headline",
                "what_missed": ["specific guidance"],
                "issue_tags": ["too_vague"],
                "improved_reply_example": "Do 4 x 5 minutes steady.",
            }
        ],
    }


class TestPromptFeedbackLoop(unittest.TestCase):
    def setUp(self) -> None:
        prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()

    def tearDown(self) -> None:
        prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()

    def test_zero_start_workflow_runs_multiple_rounds_and_writes_summary(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt_root = root / "prompt_packs"
            bench_path = root / "bench.md"
            output_dir = root / "workflow"
            _write_prompt_pack(prompt_root, "v1")
            bench_path.write_text("# bench\n", encoding="utf-8")

            def fake_run_live_suite(**kwargs):
                _write_attempt(kwargs["output_dir"], version=kwargs["prompt_pack_version"])
                return kwargs["output_dir"]

            def fake_run_regression(**kwargs):
                round_dir = kwargs["round_dir"]
                report_path = round_dir / "regression-report.json"
                proposed_run_dir = round_dir / "regression_runs" / f"proposed-{kwargs['candidate_version']}"
                proposed_run_dir.mkdir(parents=True, exist_ok=True)
                aggregate_path = proposed_run_dir / "aggregate.json"
                _write_json(aggregate_path, _candidate_aggregate(f"run-{kwargs['candidate_version']}"))
                _write_json(
                    report_path,
                    {
                        "decision": "promote",
                        "base_version": kwargs["base_version"],
                        "proposed_version": kwargs["candidate_version"],
                        "failed_gates": [],
                        "score_deltas": {
                            "understanding": 0.5,
                            "memory_continuity": 0.2,
                            "personalization": 0.1,
                            "coaching_quality": 0.5,
                            "tone_trust": 0.0,
                            "communication_style_fit": 0.0,
                            "safety": 0.0,
                            "overall_average_score": 0.217,
                        },
                        "suite_runs": {
                            "proposed_run_dir": str(proposed_run_dir.resolve()),
                            "proposed_aggregate": str(aggregate_path.resolve()),
                        },
                    },
                )
                return json.loads(report_path.read_text(encoding="utf-8"))

            with mock.patch.object(prompt_pack_loader, "PROMPT_PACKS_ROOT", prompt_root), mock.patch.object(
                prompt_feedback_loop, "_run_live_suite", side_effect=fake_run_live_suite
            ), mock.patch.object(
                prompt_feedback_loop, "_run_regression", side_effect=fake_run_regression
            ):
                exit_code = prompt_feedback_loop.main(
                    [
                        "--bench",
                        str(bench_path),
                        "--start-version",
                        "v1",
                        "--output-dir",
                        str(output_dir),
                        "--max-rounds",
                        "2",
                        "--activate",
                    ]
                )

            summary = json.loads((output_dir / "workflow_summary.json").read_text(encoding="utf-8"))
            round_one_info = json.loads((output_dir / "round-1" / "candidate-pack-info.json").read_text(encoding="utf-8"))
            round_two_promotion = json.loads((output_dir / "round-2" / "promotion.json").read_text(encoding="utf-8"))
            active_version = (prompt_root / "coach_reply" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
            base_aggregate_exists = (output_dir / "round-0" / "base-aggregate.json").exists()
            proposal_exists = (output_dir / "round-1" / "proposal.json").exists()
            regression_exists = (output_dir / "round-2" / "regression-report.json").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["start_version"], "v1")
        self.assertEqual(summary["rounds_attempted"], 2)
        self.assertEqual(summary["rounds_promoted"], 2)
        self.assertEqual(summary["final_decision"], "max_rounds_reached")
        self.assertTrue(summary["activated"])
        self.assertEqual(summary["final_version"], round_two_promotion["promoted_version"])
        self.assertEqual(active_version, summary["final_version"])
        self.assertIn("candidate", round_one_info["candidate_version"])
        self.assertTrue(base_aggregate_exists)
        self.assertTrue(proposal_exists)
        self.assertTrue(regression_exists)

    def test_workflow_stops_when_proposal_has_no_supported_changes(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt_root = root / "prompt_packs"
            bench_path = root / "bench.md"
            output_dir = root / "workflow"
            _write_prompt_pack(prompt_root, "v1")
            bench_path.write_text("# bench\n", encoding="utf-8")

            def fake_run_live_suite(**kwargs):
                _write_attempt(kwargs["output_dir"], version=kwargs["prompt_pack_version"], issue_tag="unsupported_tag")
                return kwargs["output_dir"]

            with mock.patch.object(prompt_pack_loader, "PROMPT_PACKS_ROOT", prompt_root), mock.patch.object(
                prompt_feedback_loop, "_run_live_suite", side_effect=fake_run_live_suite
            ):
                exit_code = prompt_feedback_loop.main(
                    [
                        "--bench",
                        str(bench_path),
                        "--start-version",
                        "v1",
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            summary = json.loads((output_dir / "workflow_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["rounds_attempted"], 0)
        self.assertEqual(summary["rounds_promoted"], 0)
        self.assertEqual(summary["final_decision"], "no_supported_changes")
        self.assertFalse((output_dir / "round-1" / "candidate-pack-info.json").exists())

    def test_workflow_stops_after_rejected_candidate(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt_root = root / "prompt_packs"
            bench_path = root / "bench.md"
            output_dir = root / "workflow"
            _write_prompt_pack(prompt_root, "v1")
            bench_path.write_text("# bench\n", encoding="utf-8")

            def fake_run_live_suite(**kwargs):
                _write_attempt(kwargs["output_dir"], version=kwargs["prompt_pack_version"])
                return kwargs["output_dir"]

            def fake_run_regression(**kwargs):
                round_dir = kwargs["round_dir"]
                report_path = round_dir / "regression-report.json"
                proposed_run_dir = round_dir / "regression_runs" / f"proposed-{kwargs['candidate_version']}"
                proposed_run_dir.mkdir(parents=True, exist_ok=True)
                aggregate_path = proposed_run_dir / "aggregate.json"
                _write_json(aggregate_path, _candidate_aggregate(f"run-{kwargs['candidate_version']}"))
                _write_json(
                    report_path,
                    {
                        "decision": "reject",
                        "base_version": kwargs["base_version"],
                        "proposed_version": kwargs["candidate_version"],
                        "failed_gates": ["safety_regressed"],
                        "score_deltas": {"overall_average_score": -0.1, "safety": -0.5},
                        "suite_runs": {
                            "proposed_run_dir": str(proposed_run_dir.resolve()),
                            "proposed_aggregate": str(aggregate_path.resolve()),
                        },
                    },
                )
                return json.loads(report_path.read_text(encoding="utf-8"))

            with mock.patch.object(prompt_pack_loader, "PROMPT_PACKS_ROOT", prompt_root), mock.patch.object(
                prompt_feedback_loop, "_run_live_suite", side_effect=fake_run_live_suite
            ), mock.patch.object(
                prompt_feedback_loop, "_run_regression", side_effect=fake_run_regression
            ):
                exit_code = prompt_feedback_loop.main(
                    [
                        "--bench",
                        str(bench_path),
                        "--start-version",
                        "v1",
                        "--output-dir",
                        str(output_dir),
                    ]
                )

            summary = json.loads((output_dir / "workflow_summary.json").read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["rounds_attempted"], 1)
        self.assertEqual(summary["rounds_promoted"], 0)
        self.assertEqual(summary["final_decision"], "candidate_rejected")
        self.assertEqual(summary["rounds"][1]["failed_gates"], ["safety_regressed"])
        self.assertFalse((output_dir / "round-1" / "promotion.json").exists())


if __name__ == "__main__":
    unittest.main()
