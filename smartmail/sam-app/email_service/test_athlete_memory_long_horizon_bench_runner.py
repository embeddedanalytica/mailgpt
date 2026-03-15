import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import athlete_memory_long_horizon_bench_runner


def _note(note_id: int, summary: str, *, importance: str = "medium") -> dict:
    return {
        "memory_note_id": note_id,
        "fact_type": "other",
        "fact_key": f"other:note_{note_id}",
        "summary": summary,
        "importance": importance,
        "status": "active",
        "created_at": 1773273600,
        "updated_at": 1773273600 + note_id,
        "last_confirmed_at": 1773273600 + note_id,
    }


def _continuity(summary: str, recommendation: str, loop: str) -> dict:
    return {
        "summary": summary,
        "last_recommendation": recommendation,
        "open_loops": [loop],
        "updated_at": 1773273600,
    }


def _fact(label: str, *signals: str, importance: str = "medium") -> dict:
    return {
        "label": label,
        "signals": list(signals or [label]),
        "importance": importance,
    }


def _checkpoint(
    label: str,
    *,
    durable_truths=None,
    active_context=None,
    retired_truths=None,
    routine_noise=None,
    coach_should_adjust_for=None,
    coach_should_not_do=None,
) -> dict:
    return {
        "label": label,
        "durable_truths": durable_truths or [],
        "active_context": active_context or [],
        "retired_truths": retired_truths or [],
        "routine_noise": routine_noise or [],
        "coach_should_adjust_for": coach_should_adjust_for or [],
        "coach_should_not_do": coach_should_not_do or [],
    }


def _phase(phase_id: str, phase_goal: str, start_step: int, checkpoint_assertions: dict, event_tag: str = "routine_checkin") -> dict:
    return {
        "phase_id": phase_id,
        "phase_goal": phase_goal,
        "messages": [
            {
                "step": step,
                "email": f"email {step}",
                "synthetic_coach_reply": f"reply {step}",
                "event_tags": [event_tag],
            }
            for step in range(start_step, start_step + 4)
        ],
        "checkpoint_assertions": checkpoint_assertions,
    }


def _scenario() -> dict:
    return {
        "id": "AM-LH-T1",
        "athlete_name": "Test Athlete",
        "sport": "running",
        "profile_hint": "test",
        "phases": [
            _phase(
                "onboarding",
                "establish durable schedule",
                1,
                _checkpoint(
                    "onboarding checkpoint",
                    durable_truths=[
                        _fact("marathon goal", "fall marathon", importance="high"),
                        _fact("before 7am", "before 7am", importance="high"),
                    ],
                    coach_should_adjust_for=[_fact("protect sunday long run", "sunday long run")],
                ),
            ),
            _phase(
                "normal_churn",
                "ignore routine status updates",
                5,
                _checkpoint(
                    "normal churn checkpoint",
                    durable_truths=[
                        _fact("marathon goal", "fall marathon", importance="high"),
                        _fact("before 7am", "before 7am", importance="high"),
                    ],
                    routine_noise=[_fact("smooth tempo", "tempo felt smooth")],
                    coach_should_adjust_for=[_fact("keep same structure", "same structure")],
                ),
            ),
            _phase(
                "travel",
                "handle temporary disruption",
                9,
                _checkpoint(
                    "travel checkpoint",
                    durable_truths=[
                        _fact("marathon goal", "fall marathon", importance="high"),
                        _fact("before 7am", "before 7am", importance="high"),
                    ],
                    active_context=[_fact("denver travel", "hotel treadmill", importance="high")],
                    coach_should_adjust_for=[_fact("resume when home", "resume normal training")],
                ),
                event_tag="temporary_disruption",
            ),
            _phase(
                "durable_change",
                "capture durable saturday opening",
                13,
                _checkpoint(
                    "durable change checkpoint",
                    durable_truths=[
                        _fact("marathon goal", "fall marathon", importance="high"),
                        _fact("before 7am", "before 7am", importance="high"),
                        _fact("saturday available", "saturday is open", importance="high"),
                    ],
                    retired_truths=[_fact("saturday unavailable", "no saturday training")],
                    coach_should_adjust_for=[_fact("use saturday", "use saturday")],
                    coach_should_not_do=[_fact("old saturday restriction", "no saturday training")],
                ),
                event_tag="durable_change",
            ),
            _phase(
                "late_retrieval",
                "preserve the important truths under pressure",
                17,
                _checkpoint(
                    "late retrieval checkpoint",
                    durable_truths=[
                        _fact("marathon goal", "fall marathon", importance="high"),
                        _fact("before 7am", "before 7am", importance="high"),
                        _fact("saturday available", "saturday is open", importance="high"),
                        _fact("tuesday strength", "tuesday strength", importance="medium"),
                    ],
                    retired_truths=[_fact("saturday unavailable", "no saturday training")],
                    routine_noise=[_fact("weekly split", "tempo felt smooth")],
                    coach_should_adjust_for=[_fact("use saturday", "use saturday")],
                    coach_should_not_do=[_fact("old saturday restriction", "no saturday training")],
                ),
                event_tag="memory_pressure",
            ),
        ],
        "final_assertions": {
            "final_durable_truths": [
                _fact("marathon goal", "fall marathon", importance="high"),
                _fact("before 7am", "before 7am", importance="high"),
                _fact("saturday available", "saturday is open", importance="high"),
            ],
            "final_retrieval_support": [
                _fact("marathon goal", "fall marathon", importance="high"),
                _fact("saturday available", "saturday is open", importance="high"),
            ],
            "final_retired_truths": [
                _fact("saturday unavailable", "no saturday training", importance="high")
            ],
        },
    }


class TestAthleteMemoryLongHorizonBenchRunner(unittest.TestCase):
    def test_evaluate_checkpoint_result_rewards_active_context(self):
        evaluation = athlete_memory_long_horizon_bench_runner.evaluate_checkpoint_result(
            current_notes=[_note(1, "training for a fall marathon"), _note(2, "must finish before 7am")],
            continuity_summary=_continuity("hotel treadmill only during travel week", "resume normal training", "when home"),
            checkpoint_assertions=_checkpoint(
                "travel checkpoint",
                durable_truths=[_fact("goal", "fall marathon", importance="high")],
                active_context=[_fact("travel", "hotel treadmill", importance="high")],
                coach_should_adjust_for=[_fact("resume", "resume normal training")],
            ),
        )
        self.assertEqual(evaluation["label"], athlete_memory_long_horizon_bench_runner.COACH_READY)
        self.assertEqual(evaluation["dimensions"]["active_context_quality"]["state"], "pass")

    def test_salience_scoring_penalizes_missing_core_truth(self):
        evaluation = athlete_memory_long_horizon_bench_runner.evaluate_checkpoint_result(
            current_notes=[_note(1, "tempo felt smooth this week")],
            continuity_summary=_continuity("routine week", "same structure", "next week"),
            checkpoint_assertions=_checkpoint(
                "pressure checkpoint",
                durable_truths=[
                    _fact("goal", "fall marathon", importance="high"),
                    _fact("secondary", "tuesday strength", importance="medium"),
                ],
                routine_noise=[_fact("tempo noise", "tempo felt smooth")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["salience_under_pressure"]["state"], "fail")
        self.assertEqual(evaluation["label"], athlete_memory_long_horizon_bench_runner.UNSAFE_FOR_COACHING)

    def test_retirement_handling_clears_stale_truth(self):
        evaluation = athlete_memory_long_horizon_bench_runner.evaluate_checkpoint_result(
            current_notes=[_note(1, "saturday is open again"), _note(2, "fall marathon build")],
            continuity_summary=_continuity("saturday is now open", "use saturday", "confirm long run"),
            checkpoint_assertions=_checkpoint(
                "retirement checkpoint",
                durable_truths=[_fact("goal", "fall marathon", importance="high")],
                retired_truths=[_fact("old saturday restriction", "no saturday training", importance="high")],
                coach_should_not_do=[_fact("old saturday restriction", "no saturday training", importance="high")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["retirement_quality"]["state"], "pass")

    def test_final_retrieval_supports_late_coach_adjustment(self):
        evaluation = athlete_memory_long_horizon_bench_runner.short_bench.evaluate_final_retrieval(
            current_notes=[_note(1, "training for a fall marathon"), _note(2, "saturday is open again")],
            retrieval_context={"memory_notes": [_note(1, "fall marathon"), _note(2, "saturday is open again")]},
            final_assertions={
                "final_durable_truths": [_fact("goal", "fall marathon", importance="high")],
                "final_retrieval_support": [_fact("saturday", "saturday is open", importance="high")],
                "final_retired_truths": [_fact("old saturday restriction", "no saturday training", importance="high")],
            },
        )
        self.assertEqual(evaluation["status"], athlete_memory_long_horizon_bench_runner.OK)

    def test_run_single_scenario_scores_checkpoints_only(self):
        responses = []
        goal_note = _note(1, "training for a fall marathon", importance="high")
        early_note = _note(2, "must finish before 7am")
        saturday_note = _note(3, "saturday is open again")
        strength_note = _note(4, "tuesday strength slot remains available")

        responses.extend(
            {
                "memory_notes": [goal_note, early_note],
                "continuity_summary": _continuity("build week", "protect sunday long run", "long run"),
                "pre_reply_route": "long_term",
                "post_reply_route": "short_term",
            }
            for _ in range(4)
        )
        responses.extend(
            {
                "memory_notes": [goal_note, early_note],
                "continuity_summary": _continuity("tempo felt smooth", "same structure", "same structure"),
                "pre_reply_route": "neither",
                "post_reply_route": "short_term",
            }
            for _ in range(4)
        )
        responses.extend(
            {
                "memory_notes": [goal_note, early_note],
                "continuity_summary": _continuity("hotel treadmill only during travel week", "resume normal training", "when home"),
                "pre_reply_route": "neither",
                "post_reply_route": "short_term",
            }
            for _ in range(4)
        )
        responses.extend(
            {
                "memory_notes": [goal_note, early_note, saturday_note],
                "continuity_summary": _continuity("saturday is now open", "use saturday", "confirm long run"),
                "pre_reply_route": "long_term",
                "post_reply_route": "short_term",
            }
            for _ in range(4)
        )
        responses.extend(
            {
                "memory_notes": [goal_note, early_note, saturday_note, strength_note],
                "continuity_summary": _continuity("late-season check-in", "use saturday", "confirm long run"),
                "pre_reply_route": "long_term",
                "post_reply_route": "short_term",
            }
            for _ in range(4)
        )

        def _persisting_refresh(*, athlete_id, latest_interaction_context):
            response = responses.pop(0)
            athlete_memory_long_horizon_bench_runner.dynamodb_models.replace_memory_notes(
                athlete_id,
                response["memory_notes"],
            )
            athlete_memory_long_horizon_bench_runner.dynamodb_models.replace_continuity_summary(
                athlete_id,
                response["continuity_summary"],
            )
            return response

        with athlete_memory_long_horizon_bench_runner.short_bench.local_fake_storage(), mock.patch.object(
            athlete_memory_long_horizon_bench_runner.short_bench,
            "apply_benchmark_memory_refresh",
            side_effect=_persisting_refresh,
        ):
            result = athlete_memory_long_horizon_bench_runner.run_single_scenario(_scenario())
        self.assertEqual(result["status"], athlete_memory_long_horizon_bench_runner.OK)
        self.assertEqual(len(result["step_results"]), 20)
        self.assertEqual(len(result["checkpoint_results"]), 5)
        self.assertTrue(all("memory_notes" in step for step in result["step_results"]))
        self.assertTrue(all("pre_reply_route" in step for step in result["step_results"]))
        self.assertTrue(all("post_reply_route" in step for step in result["step_results"]))
        self.assertEqual(result["step_results"][0]["pre_reply_route"], "long_term")
        self.assertEqual(result["step_results"][0]["post_reply_route"], "short_term")
        self.assertTrue(all("label" in checkpoint for checkpoint in result["checkpoint_results"]))

    def test_write_summary_contains_long_horizon_sections(self):
        summary = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "benchmark_path": "/tmp/bench.md",
            "output_dir": "/tmp/out",
            "storage_mode": "local_fake",
            "total_scenarios": 1,
            "per_scenario": [
                {
                    "scenario_id": "AM-LH-T1",
                    "sport": "running",
                    "status": "ok",
                    "duration_seconds": 50.0,
                    "average_checkpoint_score": 0.91,
                    "unsafe_checkpoint_count": 0,
                    "final_score": 1.0,
                    "slowest_step": {"step": 4, "api_duration_seconds": 2.5},
                }
            ],
            "runs": [
                {
                    "scenario_id": "AM-LH-T1",
                    "checkpoint_results": [
                        {
                            "phase_id": "travel",
                            "dimensions": {
                                "durable_memory_quality": {"missing": []},
                                "active_context_quality": {"missing": ["travel hotel treadmill"]},
                                "salience_under_pressure": {"missing": [], "findings": []},
                            },
                            "stale_assumption_risks": [],
                        }
                    ],
                    "step_results": [
                        {"phase_id": "travel", "step": 9, "status": "ok", "api_duration_seconds": 2.5}
                    ],
                    "final_evaluation": {"findings": ["retrieval note"], "retired_present": []},
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "summary.md"
            athlete_memory_long_horizon_bench_runner.write_summary(summary, path)
            text = path.read_text(encoding="utf-8")
        self.assertIn("## Checkpoint Readiness", text)
        self.assertIn("## Durable Truth Survival", text)
        self.assertIn("## Temporary Context Lifecycle", text)
        self.assertIn("## Stale Assumption Risks", text)
        self.assertIn("## Salience / Compression Failures", text)
        self.assertIn("## Final Coach Retrieval", text)


if __name__ == "__main__":
    unittest.main()
