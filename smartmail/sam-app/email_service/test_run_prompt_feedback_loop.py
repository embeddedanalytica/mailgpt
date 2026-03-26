import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import run_prompt_feedback_loop


class TestRunPromptFeedbackLoop(unittest.TestCase):
    def test_main_defaults_bench_to_fixture(self):
        observed = {}

        def fake_workflow_main(argv):
            observed["argv"] = list(argv)
            return 0

        with mock.patch.object(run_prompt_feedback_loop.prompt_feedback_loop, "main", side_effect=fake_workflow_main):
            exit_code = run_prompt_feedback_loop.main([])

        self.assertEqual(exit_code, 0)
        self.assertEqual(observed["argv"][0:2], ["--bench", str(run_prompt_feedback_loop.DEFAULT_BENCH_PATH.resolve())])

    def test_main_forwards_zero_start_workflow_arguments(self):
        with tempfile.TemporaryDirectory() as td:
            bench_path = Path(td) / "bench.md"
            output_dir = Path(td) / "workflow"
            bench_path.write_text("# bench\n", encoding="utf-8")
            observed = {}

            def fake_workflow_main(argv):
                observed["argv"] = list(argv)
                return 0

            with mock.patch.object(run_prompt_feedback_loop.prompt_feedback_loop, "main", side_effect=fake_workflow_main):
                exit_code = run_prompt_feedback_loop.main(
                    [
                        "--bench",
                        str(bench_path),
                        "--scenario",
                        "SCENARIO_A",
                        "--max-rounds",
                        "2",
                        "--output-dir",
                        str(output_dir),
                        "--activate",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertEqual(
            observed["argv"],
            [
                "--bench",
                str(bench_path.resolve()),
                "--runs-per-scenario",
                "1",
                "--min-turns",
                "100",
                "--max-turns",
                "100",
                "--max-parallel",
                "1",
                "--max-rounds",
                "2",
                "--scenario",
                "SCENARIO_A",
                "--output-dir",
                str(output_dir.resolve()),
                "--auto-promote",
                "--activate",
            ],
        )

    def test_main_can_disable_auto_promotion(self):
        with tempfile.TemporaryDirectory() as td:
            bench_path = Path(td) / "bench.md"
            bench_path.write_text("# bench\n", encoding="utf-8")
            observed = {}

            def fake_workflow_main(argv):
                observed["argv"] = list(argv)
                return 0

            with mock.patch.object(run_prompt_feedback_loop.prompt_feedback_loop, "main", side_effect=fake_workflow_main):
                exit_code = run_prompt_feedback_loop.main(
                    [
                        "--bench",
                        str(bench_path),
                        "--no-auto-promote",
                    ]
                )

        self.assertEqual(exit_code, 0)
        self.assertIn("--no-auto-promote", observed["argv"])
        self.assertNotIn("--aggregate", observed["argv"])


if __name__ == "__main__":
    unittest.main()
