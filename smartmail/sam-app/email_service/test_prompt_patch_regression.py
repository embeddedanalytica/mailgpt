import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys


TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import prompt_patch_regression


def _aggregate(*, run_id: str, understanding: float, memory: float, personalization: float, coaching: float, tone: float, safety: float) -> dict:
    return {
        "run_id": run_id,
        "judge_result_count": 10,
        "average_scores": {
            "understanding": understanding,
            "memory_continuity": memory,
            "personalization": personalization,
            "coaching_quality": coaching,
            "tone_trust": tone,
            "safety": safety,
        },
        "issue_tag_counts": {"too_vague": 2},
        "strength_tag_counts": {"specific_guidance": 3},
    }


class TestPromptPatchRegression(unittest.TestCase):
    def test_build_regression_report_promotes_clear_improvement(self):
        report = prompt_patch_regression.build_regression_report(
            base_aggregate=_aggregate(
                run_id="base",
                understanding=4.0,
                memory=4.0,
                personalization=4.0,
                coaching=4.0,
                tone=4.0,
                safety=5.0,
            ),
            proposed_aggregate=_aggregate(
                run_id="proposed",
                understanding=4.2,
                memory=4.1,
                personalization=4.1,
                coaching=4.3,
                tone=4.0,
                safety=5.0,
            ),
            base_version="v1",
            proposed_version="v1-proposal",
        )
        self.assertEqual(report["decision"], "promote")
        self.assertEqual(report["failed_gates"], [])

    def test_build_regression_report_rejects_safety_drop(self):
        report = prompt_patch_regression.build_regression_report(
            base_aggregate=_aggregate(
                run_id="base",
                understanding=4.0,
                memory=4.0,
                personalization=4.0,
                coaching=4.0,
                tone=4.0,
                safety=5.0,
            ),
            proposed_aggregate=_aggregate(
                run_id="proposed",
                understanding=4.2,
                memory=4.2,
                personalization=4.2,
                coaching=4.2,
                tone=4.1,
                safety=4.0,
            ),
            base_version="v1",
            proposed_version="v1-proposal",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertIn("safety_regressed", report["failed_gates"])

    def test_build_regression_report_rejects_protected_dimension_drop(self):
        report = prompt_patch_regression.build_regression_report(
            base_aggregate=_aggregate(
                run_id="base",
                understanding=4.0,
                memory=4.2,
                personalization=4.0,
                coaching=4.0,
                tone=4.1,
                safety=5.0,
            ),
            proposed_aggregate=_aggregate(
                run_id="proposed",
                understanding=4.3,
                memory=4.0,
                personalization=4.2,
                coaching=4.3,
                tone=4.1,
                safety=5.0,
            ),
            base_version="v1",
            proposed_version="v1-proposal",
        )
        self.assertEqual(report["decision"], "reject")
        self.assertIn("memory_continuity_regressed", report["failed_gates"])

    def test_main_writes_default_output_file(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_path = root / "base.json"
            proposed_path = root / "proposed.json"
            base_path.write_text(
                json.dumps(
                    _aggregate(
                        run_id="base",
                        understanding=4.0,
                        memory=4.0,
                        personalization=4.0,
                        coaching=4.0,
                        tone=4.0,
                        safety=5.0,
                    )
                ),
                encoding="utf-8",
            )
            proposed_path.write_text(
                json.dumps(
                    _aggregate(
                        run_id="proposed",
                        understanding=4.2,
                        memory=4.1,
                        personalization=4.1,
                        coaching=4.2,
                        tone=4.0,
                        safety=5.0,
                    )
                ),
                encoding="utf-8",
            )

            exit_code = prompt_patch_regression.main(
                [
                    "--base-aggregate",
                    str(base_path),
                    "--proposed-aggregate",
                    str(proposed_path),
                    "--base-version",
                    "v1",
                    "--proposed-version",
                    "v1-proposal",
                ]
            )

            report_path = root / "regression_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(report["decision"], "promote")

    def test_main_fails_on_invalid_aggregate_shape(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            base_path = root / "base.json"
            proposed_path = root / "proposed.json"
            base_path.write_text(json.dumps({"run_id": "base"}), encoding="utf-8")
            proposed_path.write_text(json.dumps({"run_id": "proposed"}), encoding="utf-8")

            exit_code = prompt_patch_regression.main(
                [
                    "--base-aggregate",
                    str(base_path),
                    "--proposed-aggregate",
                    str(proposed_path),
                    "--base-version",
                    "v1",
                    "--proposed-version",
                    "v1-proposal",
                ]
            )

        self.assertEqual(exit_code, 1)

    def test_run_live_suite_for_prompt_pack_sets_prompt_pack_version(self):
        with tempfile.TemporaryDirectory() as td:
            output_dir = Path(td) / "base-v1"
            observed = {}

            def fake_run(command, *, env, text, capture_output):
                observed["command"] = command
                observed["env_version"] = env.get("COACH_REPLY_PROMPT_PACK_VERSION")
                observed["text"] = text
                observed["capture_output"] = capture_output
                return mock.Mock(returncode=0, stdout="ok", stderr="")

            with mock.patch.object(prompt_patch_regression.subprocess, "run", side_effect=fake_run):
                result = prompt_patch_regression._run_live_suite_for_prompt_pack(
                    prompt_pack_version="v2",
                    bench_path=Path(td) / "bench.md",
                    scenario_tokens=["SCENARIO_A"],
                    runs_per_scenario=2,
                    min_turns=3,
                    max_turns=4,
                    athlete_model="athlete-x",
                    judge_model="judge-y",
                    max_parallel=5,
                    output_dir=output_dir,
                )

            output_dir_exists = output_dir.exists()

        self.assertEqual(result, output_dir)
        self.assertEqual(observed["env_version"], "v2")
        self.assertEqual(observed["command"][0], sys.executable)
        self.assertIn("--bench", observed["command"])
        self.assertIn("--scenario", observed["command"])
        self.assertTrue(output_dir_exists)

    def test_main_live_mode_runs_both_versions_and_aggregates_both_runs(self):
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            bench_path = root / "bench.md"
            bench_path.write_text("# bench\n", encoding="utf-8")
            run_versions = []
            aggregate_inputs = []

            def fake_run_suite(**kwargs):
                run_versions.append(kwargs["prompt_pack_version"])
                run_dir = kwargs["output_dir"]
                run_dir.mkdir(parents=True, exist_ok=True)
                attempt_path = run_dir / f"{kwargs['prompt_pack_version']}-attempt1.jsonl"
                summary_path = run_dir / f"{kwargs['prompt_pack_version']}-attempt1.summary.json"
                payload = {
                    "phase": "judge_result",
                    "turn": 1,
                    "result": {
                        "headline": "headline",
                        "athlete_likely_experience": "experience",
                        "scores": {
                            "understanding": 4.0 if kwargs["prompt_pack_version"] == "v1" else 4.5,
                            "memory_continuity": 4.0,
                            "personalization": 4.0,
                            "coaching_quality": 4.0 if kwargs["prompt_pack_version"] == "v1" else 4.5,
                            "tone_trust": 4.0,
                            "safety": 5.0,
                        },
                        "what_missed": ["missed detail"],
                        "issue_tags": ["too_vague"],
                        "strength_tags": ["specific_guidance"],
                    },
                }
                attempt_path.write_text(json.dumps(payload) + "\n", encoding="utf-8")
                summary_path.write_text(
                    json.dumps(
                        {
                            "scenario_id": "SCENARIO_A",
                            "scenario_name": "Scenario A",
                            "attempt": 1,
                            "run_id": f"run-{kwargs['prompt_pack_version']}",
                        }
                    ),
                    encoding="utf-8",
                )
                return run_dir

            real_aggregate_feedback = prompt_patch_regression.prompt_feedback_aggregate.aggregate_feedback

            def tracking_aggregate(run_dir):
                aggregate_inputs.append(run_dir)
                return real_aggregate_feedback(run_dir)

            with mock.patch.object(
                prompt_patch_regression,
                "_run_live_suite_for_prompt_pack",
                side_effect=fake_run_suite,
            ), mock.patch.object(
                prompt_patch_regression.prompt_feedback_aggregate,
                "aggregate_feedback",
                side_effect=tracking_aggregate,
            ):
                exit_code = prompt_patch_regression.main(
                    [
                        "--bench",
                        str(bench_path),
                        "--base-version",
                        "v1",
                        "--proposed-version",
                        "v2",
                        "--scenario",
                        "SCENARIO_A",
                        "--run-output-dir",
                        str(root / "runs"),
                    ]
                )

            report_path = root / "runs" / "regression_report.json"
            report = json.loads(report_path.read_text(encoding="utf-8"))

        self.assertEqual(exit_code, 0)
        self.assertEqual(run_versions, ["v1", "v2"])
        self.assertEqual(
            [path.resolve() for path in aggregate_inputs],
            [(root / "runs" / "base-v1").resolve(), (root / "runs" / "proposed-v2").resolve()],
        )
        self.assertEqual(report["decision"], "promote")
        self.assertEqual(
            report["suite_runs"]["base_aggregate"],
            str((root / "runs" / "base-v1" / "aggregate.json").resolve()),
        )
        self.assertEqual(
            report["suite_runs"]["proposed_aggregate"],
            str((root / "runs" / "proposed-v2" / "aggregate.json").resolve()),
        )


if __name__ == "__main__":
    unittest.main()
