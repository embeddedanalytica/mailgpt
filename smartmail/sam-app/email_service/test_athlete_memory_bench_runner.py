import tempfile
import unittest
from pathlib import Path
from unittest import mock

import sys

TOOLS_PATH = Path(__file__).resolve().parents[2] / "tools"
if str(TOOLS_PATH) not in sys.path:
    sys.path.insert(0, str(TOOLS_PATH))

import athlete_memory_bench_runner


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


def _fact(label: str, *signals: str, importance: str = "medium", aliases=None, semantic_signals=None) -> dict:
    fact = {
        "label": label,
        "signals": list(signals or [label]),
        "importance": importance,
    }
    if aliases is not None:
        fact["aliases"] = list(aliases)
    if semantic_signals is not None:
        fact["semantic_signals"] = list(semantic_signals)
    return fact


def _message(
    step: int,
    *,
    durable_truths=None,
    active_context=None,
    active_context_mode="acceptable",
    retired_truths=None,
    routine_noise=None,
    coach_should_adjust_for=None,
    coach_should_not_do=None,
    message_intent="general",
) -> dict:
    return {
        "step": step,
        "email": f"email {step}",
        "synthetic_coach_reply": f"reply {step}",
        "durable_truths": durable_truths or [],
        "active_context": active_context or [],
        "active_context_mode": active_context_mode,
        "retired_truths": retired_truths or [],
        "routine_noise": routine_noise or [],
        "coach_should_adjust_for": coach_should_adjust_for or [],
        "coach_should_not_do": coach_should_not_do or [],
        "message_intent": message_intent,
    }


def _scenario() -> dict:
    return {
        "id": "AM-T1",
        "athlete_name": "Test Athlete",
        "sport": "running",
        "profile_hint": "test",
        "messages": [
            _message(
                1,
                durable_truths=[
                    _fact("early schedule", "before 7am", aliases=["7:00am due to school drop-off"]),
                    _fact("saturday unavailable", "no saturday training", "saturdays unavailable"),
                ],
                coach_should_adjust_for=[_fact("plan around sunday long run", "sunday long run")],
            ),
            _message(
                2,
                durable_truths=[
                    _fact("early schedule", "before 7am", aliases=["7:00am due to school drop-off"]),
                    _fact("saturday unavailable", "no saturday training", "saturdays unavailable"),
                ],
                routine_noise=[_fact("weekly workout log", "tempo felt smooth")],
                message_intent="routine_checkin",
                coach_should_adjust_for=[_fact("keep same structure", "same structure")],
            ),
            _message(
                3,
                durable_truths=[
                    _fact("early schedule", "before 7am", aliases=["7:00am due to school drop-off"]),
                    _fact("saturday unavailable", "no saturday training", "saturdays unavailable"),
                ],
                active_context=[_fact("travel week", "hotel gym", "travel week")],
                active_context_mode="required",
                coach_should_adjust_for=[_fact("resume normal training", "resume normal training")],
            ),
            _message(
                4,
                durable_truths=[
                    _fact("early schedule", "before 7am", aliases=["7:00am due to school drop-off"]),
                    _fact("saturday unavailable", "no saturday training", "saturdays unavailable"),
                    _fact("tuesday strength", "tuesday strength routine", "strength routine"),
                ],
                active_context=[_fact("travel week", "hotel gym", "travel week")],
                active_context_mode="acceptable",
                coach_should_adjust_for=[_fact("include durable strength slot", "durable update", "strength routine")],
            ),
            _message(
                5,
                durable_truths=[
                    _fact("early schedule", "before 7am", aliases=["7:00am due to school drop-off"]),
                    _fact("tuesday strength", "tuesday strength routine", "strength routine"),
                ],
                active_context=[_fact("travel week", "hotel gym", "travel week")],
                active_context_mode="expired",
                retired_truths=[_fact("saturday unavailable", "no saturday training", "saturdays unavailable")],
                coach_should_adjust_for=[_fact("use saturday now", "use saturday", "saturday is open")],
                coach_should_not_do=[_fact("keep old saturday restriction", "no saturday training", "saturdays unavailable")],
            ),
        ],
        "final_assertions": {
            "final_durable_truths": [
                _fact("early schedule", "before 7am", "7:00am due to school drop-off"),
                _fact("tuesday strength", "tuesday strength routine", "strength routine"),
            ],
            "final_retrieval_support": [
                _fact("early schedule", "before 7am", "7:00am due to school drop-off"),
                _fact("tuesday strength", "tuesday strength routine", "strength routine"),
            ],
            "final_retired_truths": [
                _fact("saturday unavailable", "no saturday training", "saturdays unavailable")
            ],
        },
    }


class TestAthleteMemoryBenchRunner(unittest.TestCase):
    def test_use_live_dynamo_flag(self):
        with mock.patch.dict("os.environ", {"ATHLETE_MEMORY_BENCH_USE_LIVE_DYNAMO": "true"}):
            self.assertTrue(athlete_memory_bench_runner.use_live_dynamo())
        with mock.patch.dict("os.environ", {"ATHLETE_MEMORY_BENCH_USE_LIVE_DYNAMO": "false"}):
            self.assertFalse(athlete_memory_bench_runner.use_live_dynamo())

    def test_evaluate_step_result_accepts_semantic_rewording(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "weekday training must finish by 7:00am due to school drop-off")],
            continuity_summary=_continuity("steady build week", "keep sunday long run", "check long run"),
            expectations=_message(
                1,
                durable_truths=[_fact("early schedule", "before 7am", "7:00am due to school drop-off")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["durable_memory_quality"]["state"], "pass")
        self.assertEqual(evaluation["label"], athlete_memory_bench_runner.COACH_READY)

    def test_evaluate_step_result_accepts_token_order_variation(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "attends masters swim every Wednesday night as the main recurring session")],
            continuity_summary=_continuity("steady build week", "anchor around masters", "confirm session"),
            expectations=_message(
                1,
                durable_truths=[_fact("wednesday masters", "Wednesday masters")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["durable_memory_quality"]["state"], "pass")

    def test_evaluate_step_result_accepts_broad_time_match(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "weekday workouts must finish by 7:00 AM due to school drop-off")],
            continuity_summary=_continuity("steady build week", "keep early sessions", "confirm timing"),
            expectations=_message(
                1,
                durable_truths=[_fact("early cutoff", "before 7am")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["durable_memory_quality"]["state"], "pass")

    def test_evaluate_step_result_accepts_saturday_open_flexibility_available_variants(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "saturdays are available for training now because childcare shifted")],
            continuity_summary=_continuity("steady build week", "use saturday when helpful", "confirm long run"),
            expectations=_message(
                1,
                durable_truths=[_fact("saturday opening", "Saturday flexibility", "saturdays are open")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["durable_memory_quality"]["state"], "pass")

    def test_evaluate_step_result_accepts_synonym_rewording_for_tri_goal_and_limiter(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[
                _note(1, "training for an Olympic-distance triathlon scheduled in late summer"),
                _note(2, "swimming is the athlete's primary limiter and should stay the main focus"),
            ],
            continuity_summary=_continuity("steady build week", "keep swim emphasis central", "confirm swim baseline"),
            expectations=_message(
                1,
                durable_truths=[
                    _fact("tri goal", "Olympic tri"),
                    _fact("swim limiter", "swim is the limiter"),
                ],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["durable_memory_quality"]["state"], "pass")

    def test_evaluate_step_result_rewards_active_context_in_continuity(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "training for a marathon")],
            continuity_summary=_continuity(
                "travel week with hotel gym access only",
                "resume normal training when home",
                "hotel gym",
            ),
            expectations=_message(
                3,
                active_context=[_fact("travel week", "travel week", "hotel gym")],
                active_context_mode="required",
                coach_should_adjust_for=[_fact("resume normal training", "resume normal training")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["active_context_quality"]["state"], "pass")
        self.assertEqual(evaluation["dimensions"]["coach_actionability"]["state"], "pass")

    def test_evaluate_step_result_does_not_penalize_acceptable_active_context_when_absent(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "training for a marathon")],
            continuity_summary=_continuity("back to normal structure", "use the regular plan", "next long run"),
            expectations=_message(
                4,
                active_context=[_fact("travel week", "hotel gym")],
                active_context_mode="acceptable",
            ),
        )
        self.assertEqual(evaluation["dimensions"]["active_context_quality"]["state"], "pass")

    def test_evaluate_step_result_flags_expired_active_context_when_still_operational(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "training for a marathon")],
            continuity_summary=_continuity("still planning around the hotel gym travel week", "keep hotel-gym plan", "travel week"),
            expectations=_message(
                5,
                active_context=[_fact("travel week", "hotel gym", importance="high")],
                active_context_mode="expired",
            ),
        )
        self.assertEqual(evaluation["dimensions"]["active_context_quality"]["state"], "fail")

    def test_evaluate_step_result_does_not_penalize_expired_context_only_in_open_loop(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "training for a marathon")],
            continuity_summary=_continuity(
                "back to the regular training structure",
                "use the normal plan again",
                "check in after the travel week",
            ),
            expectations=_message(
                5,
                active_context=[_fact("travel week", "travel week", "hotel gym", importance="high")],
                active_context_mode="expired",
            ),
        )
        self.assertEqual(evaluation["dimensions"]["active_context_quality"]["state"], "pass")

    def test_evaluate_step_result_treats_negated_retired_truth_as_cleared(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "available for training during lunch breaks and evenings; no longer restricted to after 8pm")],
            continuity_summary=_continuity(
                "schedule is no longer after-8pm only",
                "use midday when helpful",
                "confirm lunch window",
            ),
            expectations=_message(
                5,
                retired_truths=[_fact("after 8pm only", "after 8pm")],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["retirement_quality"]["state"], "pass")

    def test_evaluate_step_result_does_not_treat_broader_weekend_access_as_retired_truth_present(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "outdoor gravel rides occur on weekends (saturday and sunday)")],
            continuity_summary=_continuity(
                "drop the sunday-only assumption and plan outdoor gravel sessions on either weekend day",
                "use saturday or sunday for outdoor gravel work",
                "confirm which weekend day opens up first",
            ),
            expectations=_message(
                5,
                retired_truths=[
                    _fact(
                        "sunday-only outdoor",
                        "sunday-only outdoor",
                        aliases=["outdoor gravel rides mostly on sundays"],
                    )
                ],
                coach_should_not_do=[
                    _fact(
                        "sunday-only outdoor",
                        "sunday-only outdoor",
                        aliases=["outdoor gravel rides mostly on sundays"],
                    )
                ],
            ),
        )
        self.assertEqual(evaluation["dimensions"]["retirement_quality"]["state"], "pass")
        self.assertEqual(evaluation["dimensions"]["coach_actionability"]["state"], "pass")

    def test_evaluate_step_result_flags_routine_noise_promoted_to_memory(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "tempo felt smooth this week")],
            continuity_summary=_continuity("normal week", "keep same structure", "next long run"),
            expectations=_message(
                2,
                routine_noise=[_fact("weekly workout log", "tempo felt smooth")],
                message_intent="routine_checkin",
            ),
        )
        self.assertEqual(evaluation["dimensions"]["noise_control"]["state"], "fail")
        self.assertEqual(evaluation["label"], athlete_memory_bench_runner.MEMORY_OK_BUT_NOISY)

    def test_evaluate_step_result_flags_routine_count_rewrite_under_routine_checkin(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            previous_notes=[_note(1, "most sessions are court skill work with one conditioning day per week")],
            current_notes=[_note(1, "two court sessions and one conditioning day per week")],
            continuity_summary=_continuity("normal week", "stay with the same late schedule", "next hard session"),
            expectations=_message(
                2,
                durable_truths=[_fact("conditioning day", "conditioning day")],
                message_intent="routine_checkin",
            ),
        )
        self.assertEqual(evaluation["dimensions"]["noise_control"]["state"], "fail")

    def test_evaluate_final_retrieval_checks_coaching_usefulness(self):
        evaluation = athlete_memory_bench_runner.evaluate_final_retrieval(
            current_notes=[_note(1, "early sessions before 7am"), _note(2, "tuesday strength routine")],
            retrieval_context={"memory_notes": [_note(1, "before 7am schedule"), _note(2, "tuesday strength routine")]},
            final_assertions={
                "final_durable_truths": [
                    _fact("early schedule", "before 7am"),
                    _fact("tuesday strength", "tuesday strength routine"),
                ],
                "final_retrieval_support": [
                    _fact("early schedule", "before 7am"),
                    _fact("tuesday strength", "tuesday strength routine"),
                ],
                "final_retired_truths": [_fact("old saturday restriction", "no saturday training")],
            },
        )
        self.assertEqual(evaluation["status"], athlete_memory_bench_runner.OK)
        self.assertEqual(evaluation["findings"], [])

    def test_evaluate_final_retrieval_treats_medium_phrase_miss_as_warning(self):
        evaluation = athlete_memory_bench_runner.evaluate_final_retrieval(
            current_notes=[_note(1, "masters swimmer"), _note(2, "trains before work")],
            retrieval_context={"memory_notes": [_note(1, "masters swimmer"), _note(2, "trains before work")]},
            final_assertions={
                "final_durable_truths": [_fact("1500 free", "1500 free", importance="medium")],
                "final_retrieval_support": [_fact("before work", "before work", importance="high")],
                "final_retired_truths": [],
            },
        )
        self.assertEqual(evaluation["status"], athlete_memory_bench_runner.OK)
        self.assertTrue(evaluation["warnings"])

    def test_wording_nits_do_not_trigger_unsafe_for_coaching(self):
        evaluation = athlete_memory_bench_runner.evaluate_step_result(
            current_notes=[_note(1, "training for a marathon")],
            continuity_summary=_continuity("steady build", "keep current plan", "check long run"),
            expectations=_message(
                2,
                coach_should_adjust_for=[
                    _fact("recommendation uses part", "part"),
                    _fact("open loop: when, youre, home", "when home"),
                ],
            ),
        )
        self.assertNotEqual(evaluation["label"], athlete_memory_bench_runner.UNSAFE_FOR_COACHING)

    def test_apply_benchmark_memory_refresh_uses_split_am2_writes(self):
        long_term_notes = [_note(1, "early sessions before 7am"), _note(2, "no saturday training")]
        short_term_continuity = _continuity("travel week with hotel gym", "resume normal training", "hotel gym")
        interaction_context = {
            "inbound_email": "email 1",
            "inbound_subject": "running benchmark step 1",
            "coach_reply": "reply 1",
            "profile_updates_applied": [],
            "manual_activity_detected": False,
            "selected_model_name": "athlete_memory_bench",
            "rule_engine_decision": {"scenario_id": "AM-T1", "step": 1},
        }
        with athlete_memory_bench_runner.local_fake_storage(), mock.patch.object(
            athlete_memory_bench_runner,
            "run_memory_router",
            side_effect=[
                {"route": "long_term"},
                {"route": "short_term"},
            ],
        ), mock.patch.object(
            athlete_memory_bench_runner,
            "run_memory_refresh",
            side_effect=[
                {
                    "memory_notes": long_term_notes,
                    "continuity_summary": _continuity("existing continuity", "existing plan", "existing loop"),
                },
                {
                    "memory_notes": long_term_notes,
                    "continuity_summary": short_term_continuity,
                },
            ],
        ) as refresh_mock:
            result = athlete_memory_bench_runner.apply_benchmark_memory_refresh(
                athlete_id="bench_am_t1",
                latest_interaction_context=interaction_context,
            )
        self.assertEqual([note["memory_note_id"] for note in result["memory_notes"]], [1, 2])
        self.assertEqual(result["continuity_summary"]["summary"], "travel week with hotel gym")
        self.assertEqual(result["pre_reply_route"], "long_term")
        self.assertEqual(result["post_reply_route"], "short_term")
        self.assertEqual(result["routing_debug"]["pre_reply"]["parsed_routing"]["route"], "long_term")
        self.assertTrue(result["routing_debug"]["pre_reply"]["long_term_ran"])
        self.assertEqual(result["routing_debug"]["post_reply"]["parsed_routing"]["route"], "short_term")
        self.assertTrue(result["routing_debug"]["post_reply"]["short_term_ran"])
        self.assertEqual(refresh_mock.call_args_list[0].kwargs["routing_decision"], {"route": "long_term"})
        self.assertNotIn("coach_reply", refresh_mock.call_args_list[0].kwargs["latest_interaction_context"])
        self.assertEqual(refresh_mock.call_args_list[1].kwargs["routing_decision"], {"route": "short_term"})
        self.assertEqual(
            refresh_mock.call_args_list[1].kwargs["latest_interaction_context"]["coach_reply"],
            "reply 1",
        )

    def test_run_single_scenario_local_fake_persists_and_retrieves(self):
        responses = [
            {
                "memory_notes": [_note(1, "early sessions before 7am"), _note(2, "no saturday training")],
                "continuity_summary": _continuity("build week", "keep sunday long run", "check saturday constraint"),
                "pre_reply_route": "long_term",
                "post_reply_route": "short_term",
            },
            {
                "memory_notes": [_note(1, "early sessions before 7am"), _note(2, "no saturday training")],
                "continuity_summary": _continuity("tempo felt smooth", "same structure", "sunday long run"),
                "pre_reply_route": "neither",
                "post_reply_route": "short_term",
            },
            {
                "memory_notes": [_note(1, "early sessions before 7am"), _note(2, "no saturday training")],
                "continuity_summary": _continuity("travel week with hotel gym", "resume normal training", "hotel gym"),
                "pre_reply_route": "neither",
                "post_reply_route": "short_term",
            },
            {
                "memory_notes": [
                    _note(1, "early sessions before 7am"),
                    _note(2, "no saturday training"),
                    _note(3, "tuesday strength routine"),
                ],
                "continuity_summary": _continuity("new strength routine", "durable update", "routine settles"),
                "pre_reply_route": "long_term",
                "post_reply_route": "short_term",
            },
            {
                "memory_notes": [
                    _note(1, "early sessions before 7am"),
                    _note(3, "tuesday strength routine"),
                ],
                "continuity_summary": _continuity("saturday is open", "use saturday", "use saturday"),
                "pre_reply_route": "long_term",
                "post_reply_route": "short_term",
            },
        ]

        def _persisting_refresh(*, athlete_id, latest_interaction_context):
            response = responses.pop(0)
            athlete_memory_bench_runner.dynamodb_models.replace_memory_notes(
                athlete_id,
                response["memory_notes"],
            )
            athlete_memory_bench_runner.dynamodb_models.replace_continuity_summary(
                athlete_id,
                response["continuity_summary"],
            )
            return response

        with athlete_memory_bench_runner.local_fake_storage(), mock.patch.object(
            athlete_memory_bench_runner,
            "apply_benchmark_memory_refresh",
            side_effect=_persisting_refresh,
        ):
            result = athlete_memory_bench_runner.run_single_scenario(
                _scenario(),
                run_index=2,
                total_runs=3,
            )
        self.assertEqual(result["status"], athlete_memory_bench_runner.OK)
        self.assertEqual(result["run_index"], 2)
        self.assertEqual(result["total_runs"], 3)
        self.assertEqual(len(result["step_results"]), 5)
        self.assertEqual(result["final_evaluation"]["findings"], [])
        self.assertTrue(all(step["started_at"] for step in result["step_results"]))
        self.assertTrue(all(step["completed_at"] for step in result["step_results"]))
        self.assertTrue(all(step["api_duration_seconds"] >= 0 for step in result["step_results"]))
        self.assertCountEqual(
            [note["memory_note_id"] for note in result["retrieval_context"]["memory_notes"]],
            [1, 3],
        )

    def test_run_single_scenario_logs_before_and_after_refresh(self):
        response = {
            "memory_notes": [_note(1, "early sessions before 7am"), _note(2, "no saturday training")],
            "continuity_summary": _continuity("build week", "keep sunday long run", "check saturday constraint"),
        }

        def _persisting_refresh(*, athlete_id, latest_interaction_context):
            athlete_memory_bench_runner.dynamodb_models.replace_memory_notes(
                athlete_id,
                response["memory_notes"],
            )
            athlete_memory_bench_runner.dynamodb_models.replace_continuity_summary(
                athlete_id,
                response["continuity_summary"],
            )
            return response

        scenario = _scenario()
        scenario["messages"] = [scenario["messages"][0]]
        scenario["final_assertions"] = {
            "final_durable_truths": [_fact("early schedule", "before 7am")],
            "final_retrieval_support": [_fact("early schedule", "before 7am")],
            "final_retired_truths": [],
        }
        with athlete_memory_bench_runner.local_fake_storage(), mock.patch.object(
            athlete_memory_bench_runner,
            "apply_benchmark_memory_refresh",
            side_effect=_persisting_refresh,
        ), self.assertLogs("athlete_memory_bench_runner", level="INFO") as logs:
            result = athlete_memory_bench_runner.run_single_scenario(
                scenario,
                run_index=1,
                total_runs=3,
            )
        self.assertEqual(result["status"], athlete_memory_bench_runner.OK)
        joined_logs = "\n".join(logs.output)
        self.assertIn("Starting memory refresh scenario=AM-T1 step=1", joined_logs)
        self.assertIn("Completed memory refresh scenario=AM-T1 step=1", joined_logs)

    def test_aggregate_results_consolidates_multiple_runs_per_scenario(self):
        scenario = _scenario()
        runs = [
            {
                "scenario_id": "AM-T1",
                "run_index": 1,
                "athlete_name": "Test Athlete",
                "sport": "running",
                "status": athlete_memory_bench_runner.OK,
                "duration_seconds": 10.0,
                "step_results": [
                    {
                        "step": 1,
                        "label": athlete_memory_bench_runner.COACH_READY,
                        "score": 0.9,
                        "api_duration_seconds": 1.1,
                    }
                ],
                "final_evaluation": {"score": 1.0, "findings": [], "retired_present": []},
            },
            {
                "scenario_id": "AM-T1",
                "run_index": 2,
                "athlete_name": "Test Athlete",
                "sport": "running",
                "status": athlete_memory_bench_runner.ASSERTION_FAILED,
                "duration_seconds": 12.0,
                "step_results": [
                    {
                        "step": 1,
                        "label": athlete_memory_bench_runner.UNSAFE_FOR_COACHING,
                        "score": 0.3,
                        "api_duration_seconds": 2.2,
                    }
                ],
                "final_evaluation": {"score": 0.5, "findings": ["miss"], "retired_present": []},
            },
            {
                "scenario_id": "AM-T1",
                "run_index": 3,
                "athlete_name": "Test Athlete",
                "sport": "running",
                "status": athlete_memory_bench_runner.OK,
                "duration_seconds": 11.0,
                "step_results": [
                    {
                        "step": 1,
                        "label": athlete_memory_bench_runner.COACH_READY,
                        "score": 0.6,
                        "api_duration_seconds": 1.5,
                    }
                ],
                "final_evaluation": {"score": 0.75, "findings": [], "retired_present": []},
            },
        ]
        summary = athlete_memory_bench_runner.aggregate_results(
            scenarios=[scenario],
            runs=runs,
            bench_path=Path("/tmp/bench.md"),
            output_dir=Path("/tmp/out"),
            runs_per_scenario=3,
        )
        item = summary["per_scenario"][0]
        self.assertEqual(summary["total_runs"], 3)
        self.assertEqual(item["runs_attempted"], 3)
        self.assertEqual(item["status_counts"][athlete_memory_bench_runner.OK], 2)
        self.assertEqual(item["pass_rate"], 0.667)
        self.assertEqual(item["average_step_score"], 0.6)
        self.assertEqual(item["final_score_average"], 0.75)
        self.assertEqual(item["slowest_step"]["run_index"], 2)

    def test_write_summary_contains_sections(self):
        summary = {
            "generated_at": "2026-01-01T00:00:00+00:00",
            "benchmark_path": "/tmp/bench.md",
            "output_dir": "/tmp/out",
            "storage_mode": "local_fake",
            "total_scenarios": 1,
            "runs_per_scenario": 3,
            "total_runs": 3,
            "per_scenario": [
                {
                    "scenario_id": "AM-T1",
                    "sport": "running",
                    "pass_rate": 0.667,
                    "average_duration_seconds": 12.3,
                    "average_step_score": 0.92,
                    "unsafe_step_count": 0,
                    "final_score_average": 1.0,
                    "status_counts": {"ok": 2, "assertion_failed": 1},
                    "slowest_step": {
                        "step": 1,
                        "run_index": 2,
                        "api_duration_seconds": 2.5,
                    },
                    "run_results": [
                        {"run_index": 1, "status": "ok", "final_score": 1.0, "duration_seconds": 12.0},
                        {"run_index": 2, "status": "assertion_failed", "final_score": 0.0, "duration_seconds": 13.0},
                        {"run_index": 3, "status": "ok", "final_score": 1.0, "duration_seconds": 11.9},
                    ],
                }
            ],
            "runs": [
                {
                    "scenario_id": "AM-T1",
                    "run_index": 2,
                    "step_results": [
                        {
                            "step": 1,
                            "status": "ok",
                            "label": "coach_ready",
                            "score": 1.0,
                            "started_at": "2026-01-01T00:00:00+00:00",
                            "completed_at": "2026-01-01T00:00:02+00:00",
                            "api_duration_seconds": 2.5,
                            "dimensions": {
                                "durable_memory_quality": {"missing": []},
                                "active_context_quality": {"missing": []},
                            },
                            "stale_assumption_risks": [],
                            "over_retention_flags": [],
                        }
                    ],
                    "final_evaluation": {
                        "findings": ["final retrieval note"],
                        "retired_present": [],
                    },
                }
            ],
        }
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "summary.md"
            athlete_memory_bench_runner.write_summary(summary, path)
            text = path.read_text(encoding="utf-8")
        self.assertIn("## Coach Readiness", text)
        self.assertIn("## Step Timings", text)
        self.assertIn("## Durable Memory Misses", text)
        self.assertIn("## Active Context Handling", text)
        self.assertIn("## Stale Assumption Risks", text)
        self.assertIn("## Noise / Over-Retention", text)
        self.assertIn("## Final Retrieval Findings", text)
        self.assertIn("Runs per scenario: 3", text)
        self.assertIn("AM-T1 run 2", text)
        self.assertIn("api_duration_seconds=2.5", text)


if __name__ == "__main__":
    unittest.main()
