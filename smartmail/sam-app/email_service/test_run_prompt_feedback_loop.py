import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import run_prompt_feedback_loop


def _write_attempt(run_dir: Path) -> None:
    attempt_path = run_dir / "scenario-attempt1.jsonl"
    summary_path = run_dir / "scenario-attempt1.summary.json"
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
                        "understanding": 4,
                        "memory_continuity": 4,
                        "personalization": 4,
                        "coaching_quality": 4,
                        "tone_trust": 4,
                        "safety": 5,
                    },
                    "what_missed": ["specific guidance"],
                    "issue_tags": ["too_vague"],
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
                "run_id": "run-1",
            }
        ),
        encoding="utf-8",
    )


class TestRunPromptFeedbackLoop(unittest.TestCase):
    def test_main_aggregates_run_dir_and_invokes_workflow_with_defaults(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "live-run"
            run_dir.mkdir(parents=True)
            _write_attempt(run_dir)
            observed = {}

            def fake_workflow_main(argv):
                observed["argv"] = list(argv)
                return 0

            with mock.patch.object(run_prompt_feedback_loop.prompt_feedback_loop, "main", side_effect=fake_workflow_main):
                exit_code = run_prompt_feedback_loop.main(["--run-dir", str(run_dir)])

            aggregate_path = run_dir / "aggregate.json"
            aggregate = json.loads(aggregate_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(aggregate["judge_result_count"], 1)
        self.assertIn("--aggregate", observed["argv"])
        self.assertIn(str(aggregate_path.resolve()), observed["argv"])
        self.assertIn("--bench", observed["argv"])
        self.assertIn("--output-dir", observed["argv"])
        self.assertIn(str((run_dir / "prompt-feedback-loop").resolve()), observed["argv"])

    def test_main_requires_promoted_version_when_promoting(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "live-run"
            run_dir.mkdir(parents=True)
            _write_attempt(run_dir)

            exit_code = run_prompt_feedback_loop.main(["--run-dir", str(run_dir), "--promote"])

        self.assertEqual(exit_code, 1)

    def test_main_rejects_activate_without_promote(self):
        with tempfile.TemporaryDirectory() as td:
            run_dir = Path(td) / "live-run"
            run_dir.mkdir(parents=True)
            _write_attempt(run_dir)

            exit_code = run_prompt_feedback_loop.main(["--run-dir", str(run_dir), "--activate"])

        self.assertEqual(exit_code, 1)


if __name__ == "__main__":
    unittest.main()
