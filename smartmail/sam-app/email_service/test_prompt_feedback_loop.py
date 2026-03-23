import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import prompt_feedback_loop


def _write_json(path: Path, payload: dict) -> None:
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
            "editable_surfaces": ["response_generation.system_prompt"],
        },
    )
    _write_json(target / "response_generation.json", {"system_prompt_lines": [version], "directive_system_prompt_lines": [f"{version}-d"]})
    _write_json(target / "coaching_reasoning.json", {"base_prompt_lines": [f"{version}-c"]})
    return target


def _write_aggregate(path: Path) -> None:
    _write_json(
        path,
        {
            "run_id": "agg-run",
            "input_dir": "/tmp/agg",
            "issue_tag_counts": {"too_vague": 2},
            "examples": [
                {
                    "scenario_id": "SCENARIO_A",
                    "scenario_name": "Scenario A",
                    "attempt": 1,
                    "turn": 1,
                    "headline": "headline",
                    "what_missed": ["missing specificity"],
                    "issue_tags": ["too_vague"],
                    "improved_reply_example": "Try 4 x 5 minutes.",
                }
            ],
        },
    )


class TestPromptFeedbackLoop(unittest.TestCase):
    def test_end_to_end_workflow_without_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt_root = root / "prompt_packs"
            _write_prompt_pack(prompt_root, "v1")
            aggregate_path = root / "aggregate.json"
            bench_path = root / "bench.md"
            output_dir = root / "workflow"
            _write_aggregate(aggregate_path)
            bench_path.write_text("# bench\n", encoding="utf-8")

            observed = {}

            def fake_regression_main(argv):
                observed["argv"] = list(argv)
                report_path = output_dir / "regression_report.json"
                _write_json(
                    report_path,
                    {
                        "decision": "reject",
                        "base_version": "v1",
                        "proposed_version": "v1-proposal",
                    },
                )
                return 0

            prompt_feedback_loop.prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()
            with mock.patch.object(prompt_feedback_loop.prompt_pack_loader, "PROMPT_PACKS_ROOT", prompt_root), mock.patch.object(
                prompt_feedback_loop.prompt_patch_apply, "PROMPT_PACKS_ROOT", prompt_root
            ), mock.patch.object(
                prompt_feedback_loop.prompt_patch_regression,
                "main",
                side_effect=fake_regression_main,
            ):
                exit_code = prompt_feedback_loop.main(
                    [
                        "--aggregate",
                        str(aggregate_path),
                        "--base-version",
                        "v1",
                        "--bench",
                        str(bench_path),
                        "--output-dir",
                        str(output_dir),
                    ]
                )
            prompt_feedback_loop.prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()

            summary = json.loads((output_dir / "workflow_summary.json").read_text(encoding="utf-8"))
            proposal_exists = (output_dir / "proposal.json").exists()
            candidate_exists = (prompt_root / "coach_reply" / "v1-proposal").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["regression_decision"], "reject")
        self.assertEqual(summary["promoted_version"], None)
        self.assertIn("--bench", observed["argv"])
        self.assertIn("--base-version", observed["argv"])
        self.assertIn("v1-proposal", observed["argv"])
        self.assertTrue(proposal_exists)
        self.assertTrue(candidate_exists)

    def test_end_to_end_workflow_with_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt_root = root / "prompt_packs"
            _write_prompt_pack(prompt_root, "v1")
            aggregate_path = root / "aggregate.json"
            bench_path = root / "bench.md"
            output_dir = root / "workflow"
            _write_aggregate(aggregate_path)
            bench_path.write_text("# bench\n", encoding="utf-8")

            def fake_regression_main(argv):
                _write_json(
                    output_dir / "regression_report.json",
                    {
                        "decision": "promote",
                        "base_version": "v1",
                        "proposed_version": "v1-proposal",
                        "base_metrics": {},
                        "proposed_metrics": {},
                        "score_deltas": {},
                    },
                )
                return 0

            prompt_feedback_loop.prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()
            with mock.patch.object(prompt_feedback_loop.prompt_pack_loader, "PROMPT_PACKS_ROOT", prompt_root), mock.patch.object(
                prompt_feedback_loop.prompt_patch_apply, "PROMPT_PACKS_ROOT", prompt_root
            ), mock.patch.object(
                prompt_feedback_loop.prompt_pack_promote, "PROMPT_PACKS_ROOT", prompt_root
            ), mock.patch.object(
                prompt_feedback_loop.prompt_patch_regression,
                "main",
                side_effect=fake_regression_main,
            ):
                exit_code = prompt_feedback_loop.main(
                    [
                        "--aggregate",
                        str(aggregate_path),
                        "--base-version",
                        "v1",
                        "--bench",
                        str(bench_path),
                        "--output-dir",
                        str(output_dir),
                        "--promote",
                        "--promoted-version",
                        "v2",
                        "--activate",
                    ]
                )
            prompt_feedback_loop.prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()

            summary = json.loads((output_dir / "workflow_summary.json").read_text(encoding="utf-8"))
            active_version = (prompt_root / "coach_reply" / "ACTIVE_VERSION").read_text(encoding="utf-8").strip()
            promoted_dir_exists = (prompt_root / "coach_reply" / "v2").exists()

        self.assertEqual(exit_code, 0)
        self.assertEqual(summary["regression_decision"], "promote")
        self.assertEqual(summary["promoted_version"], "v2")
        self.assertEqual(active_version, "v2")
        self.assertTrue(promoted_dir_exists)

    def test_failing_regression_blocks_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            prompt_root = root / "prompt_packs"
            _write_prompt_pack(prompt_root, "v1")
            aggregate_path = root / "aggregate.json"
            bench_path = root / "bench.md"
            output_dir = root / "workflow"
            _write_aggregate(aggregate_path)
            bench_path.write_text("# bench\n", encoding="utf-8")

            def fake_regression_main(argv):
                _write_json(
                    output_dir / "regression_report.json",
                    {
                        "decision": "reject",
                        "base_version": "v1",
                        "proposed_version": "v1-proposal",
                    },
                )
                return 0

            prompt_feedback_loop.prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()
            with mock.patch.object(prompt_feedback_loop.prompt_pack_loader, "PROMPT_PACKS_ROOT", prompt_root), mock.patch.object(
                prompt_feedback_loop.prompt_patch_apply, "PROMPT_PACKS_ROOT", prompt_root
            ), mock.patch.object(
                prompt_feedback_loop.prompt_pack_promote, "PROMPT_PACKS_ROOT", prompt_root
            ), mock.patch.object(
                prompt_feedback_loop.prompt_patch_regression,
                "main",
                side_effect=fake_regression_main,
            ):
                exit_code = prompt_feedback_loop.main(
                    [
                        "--aggregate",
                        str(aggregate_path),
                        "--base-version",
                        "v1",
                        "--bench",
                        str(bench_path),
                        "--output-dir",
                        str(output_dir),
                        "--promote",
                        "--promoted-version",
                        "v2",
                    ]
                )
            prompt_feedback_loop.prompt_pack_loader.load_coach_reply_prompt_pack.cache_clear()

        self.assertEqual(exit_code, 1)
        self.assertFalse((prompt_root / "coach_reply" / "v2").exists())


if __name__ == "__main__":
    unittest.main()
