"""Human-readable RE4 scenario tests for planner-shape validation under fixed guardrails."""

from __future__ import annotations

import os
import unittest
from typing import Any, Dict, List, Tuple
from unittest import mock

from _test_support import install_boto_stubs, valid_engine_output_payload

install_boto_stubs()

import rule_engine_orchestrator
from planner_bench_fixture import build_scenario_brief
from rule_engine import HARD_SESSION_TAGS
from skills.planner import (
    PlannerProposalError,
    PlanningLLM,
    repair_or_fallback_plan,
    validate_planner_output,
)


def run_scenario_with_mocked_proposals(
    planner_brief: Dict[str, Any],
    proposals: List[List[str]],
) -> List[Dict[str, Any]]:
    """Validate mock plan proposals and deterministically repair/fallback when needed."""
    results: List[Dict[str, Any]] = []
    for proposal in proposals:
        candidate = {"weekly_skeleton": list(proposal)}
        validation = validate_planner_output(planner_brief, candidate)
        if validation["is_valid"]:
            results.append(
                {
                    "status": "accepted",
                    "weekly_skeleton": list(validation["normalized_plan_proposal"]["weekly_skeleton"]),
                }
            )
            continue
        repaired = repair_or_fallback_plan(validation, planner_brief)
        results.append(
            {
                "status": "repaired_or_fallback",
                "source": repaired["source"],
                "weekly_skeleton": list(repaired["weekly_skeleton"]),
            }
        )
    return results


def run_scenario_live_planner(planner_brief: Dict[str, Any]) -> Dict[str, Any]:
    """
    Run live planner for a scenario brief.

    This is optional and should only be used when RUN_LIVE_PLANNER_SCENARIOS=true.
    """
    planner_response = PlanningLLM.propose_plan(planner_brief)
    plan_proposal = dict(planner_response.get("plan_proposal", {}))
    validation = validate_planner_output(planner_brief, plan_proposal)
    return {
        "plan_proposal": plan_proposal,
        "validation": validation,
        "planner_response": planner_response,
    }


def assert_quality_guardrails_goal_fit(
    testcase: unittest.TestCase,
    planner_brief: Dict[str, Any],
    weekly_skeleton: List[str],
    *,
    required_goal_tokens: List[str],
) -> None:
    """Quality rubric: Safety + Structure + Goal fit."""
    validation = validate_planner_output(planner_brief, {"weekly_skeleton": list(weekly_skeleton)})
    testcase.assertTrue(validation["is_valid"], msg=f"expected valid plan, got {validation['errors']}")

    normalized = list(validation["normalized_plan_proposal"]["weekly_skeleton"])
    testcase.assertGreaterEqual(len(normalized), 1)
    testcase.assertLessEqual(len(normalized), int(planner_brief["max_sessions_per_week"]))

    # Safety: no red-tier intensity and no forbidden hard adjacency.
    risk_flag = str(planner_brief.get("risk_flag", "")).strip().lower()
    hard_count = sum(1 for token in normalized if token in HARD_SESSION_TAGS)
    if risk_flag in {"red_a", "red_b"}:
        testcase.assertEqual(hard_count, 0)
    max_hard = int(planner_brief.get("hard_limits", {}).get("max_hard_sessions_per_week", 0) or 0)
    testcase.assertLessEqual(hard_count, max_hard)

    # Goal fit: at least one scenario-specific goal token is present.
    testcase.assertTrue(
        any(token in normalized for token in required_goal_tokens),
        msg=f"plan does not align with goal tokens: {required_goal_tokens}",
    )


SCENARIOS: List[Dict[str, Any]] = [
    {
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
        "valid_shapes": [
            ["easy_aerobic", "strength", "easy_aerobic"],
            ["strength", "easy_aerobic", "recovery"],
        ],
        "invalid_shape": ["tempo", "intervals", "easy_aerobic"],
    },
    {
        "name": "new_athlete_chaotic_feasible",
        "profile": {
            "goal_category": "general_consistency",
            "main_sport_current": "run",
            "time_bucket": "4_6h",
            "structure_preference": "flexibility",
        },
        "checkin": {
            "days_available": 3,
            "week_chaotic": True,
            "structure_preference": "flexibility",
            "has_upcoming_event": False,
        },
        "phase": "base",
        "risk_flag": "green",
        "track": "general_moderate_time",
        "effective_performance_intent": False,
        "fallback_skeleton": ["easy_aerobic", "strength", "easy_aerobic"],
        "required_goal_tokens": ["easy_aerobic", "strength"],
        "valid_shapes": [
            ["easy_aerobic", "strength", "easy_aerobic"],
            ["strength", "easy_aerobic", "mobility"],
        ],
        "invalid_shape": ["unknown_tag", "tempo", "strength"],
    },
    {
        "name": "experienced_marathon_8w_green",
        "profile": {
            "goal_category": "event_8_16w",
            "main_sport_current": "run",
            "time_bucket": "7_10h",
            "structure_preference": "structure",
        },
        "checkin": {"days_available": 5, "has_upcoming_event": True, "event_date": "2026-05-07"},
        "phase": "build",
        "risk_flag": "green",
        "track": "main_build",
        "effective_performance_intent": True,
        "fallback_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic", "intervals"],
        "required_goal_tokens": ["tempo", "intervals", "easy_aerobic"],
        "valid_shapes": [
            ["easy_aerobic", "tempo", "strength", "easy_aerobic", "intervals"],
            ["tempo", "easy_aerobic", "strength", "intervals", "recovery"],
            ["easy_aerobic", "intervals", "strength", "tempo", "recovery"],
        ],
        "invalid_shape": ["tempo", "intervals", "vo2", "strength", "easy_aerobic"],
    },
    {
        "name": "experienced_high_availability_build",
        "profile": {
            "goal_category": "performance_16w_plus",
            "main_sport_current": "run",
            "time_bucket": "10h_plus",
            "structure_preference": "mixed",
        },
        "checkin": {"days_available": 6, "has_upcoming_event": True, "event_date": "2026-06-15"},
        "phase": "build",
        "risk_flag": "green",
        "track": "main_build",
        "effective_performance_intent": True,
        "fallback_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic", "intervals", "easy_aerobic"],
        "required_goal_tokens": ["tempo", "intervals", "easy_aerobic"],
        "valid_shapes": [
            ["easy_aerobic", "tempo", "strength", "easy_aerobic", "intervals", "easy_aerobic"],
            ["tempo", "easy_aerobic", "strength", "intervals", "easy_aerobic", "recovery"],
            ["easy_aerobic", "intervals", "strength", "easy_aerobic", "tempo", "recovery"],
        ],
        "invalid_shape": ["tempo", "intervals", "vo2", "race_sim", "easy_aerobic", "strength"],
    },
    {
        "name": "experienced_yellow_controlled_push",
        "profile": {
            "goal_category": "event_8_16w",
            "main_sport_current": "run",
            "time_bucket": "7_10h",
            "structure_preference": "structure",
        },
        "checkin": {"days_available": 5, "has_upcoming_event": True, "event_date": "2026-05-01"},
        "phase": "build",
        "risk_flag": "yellow",
        "track": "main_build",
        "effective_performance_intent": True,
        "fallback_skeleton": ["easy_aerobic", "tempo", "strength", "easy_aerobic", "recovery"],
        "required_goal_tokens": ["tempo", "easy_aerobic"],
        "valid_shapes": [
            ["easy_aerobic", "tempo", "strength", "easy_aerobic", "recovery"],
            ["tempo", "easy_aerobic", "strength", "recovery", "easy_aerobic"],
        ],
        "invalid_shape": ["tempo", "intervals", "easy_aerobic", "strength", "recovery"],
    },
    {
        "name": "risk_managed_red_tier",
        "profile": {
            "goal_category": "general_consistency",
            "main_sport_current": "run",
            "time_bucket": "4_6h",
            "structure_preference": "structure",
        },
        "checkin": {"days_available": 4, "has_upcoming_event": False},
        "phase": "return_to_training",
        "risk_flag": "red_b",
        "track": "return_or_risk_managed",
        "effective_performance_intent": False,
        "fallback_skeleton": ["easy_aerobic", "strength", "recovery", "easy_aerobic"],
        "required_goal_tokens": ["easy_aerobic", "recovery", "strength"],
        "valid_shapes": [
            ["easy_aerobic", "strength", "recovery", "easy_aerobic"],
            ["recovery", "easy_aerobic", "strength", "recovery"],
        ],
        "invalid_shape": ["tempo", "intervals", "easy_aerobic", "strength"],
    },
]


class TestPlannerScenarioMatrix(unittest.TestCase):
    def test_mocked_scenarios_allow_multiple_valid_shapes_within_same_guardrails(self):
        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                planner_brief = build_scenario_brief(scenario)
                proposals = list(scenario["valid_shapes"]) + [list(scenario["invalid_shape"])]
                results = run_scenario_with_mocked_proposals(planner_brief, proposals)

                accepted = [item for item in results if item["status"] == "accepted"]
                self.assertGreaterEqual(len(accepted), 2)
                self.assertGreaterEqual(len({tuple(item["weekly_skeleton"]) for item in accepted}), 2)

                for item in accepted:
                    assert_quality_guardrails_goal_fit(
                        self,
                        planner_brief,
                        item["weekly_skeleton"],
                        required_goal_tokens=list(scenario["required_goal_tokens"]),
                    )

                repaired = results[-1]
                self.assertEqual(repaired["status"], "repaired_or_fallback")
                assert_quality_guardrails_goal_fit(
                    self,
                    planner_brief,
                    repaired["weekly_skeleton"],
                    required_goal_tokens=list(scenario["required_goal_tokens"]),
                )

    def test_live_planner_optional_matrix(self):
        if os.getenv("RUN_LIVE_PLANNER_SCENARIOS", "false").strip().lower() != "true":
            self.skipTest("RUN_LIVE_PLANNER_SCENARIOS is not true")

        for scenario in SCENARIOS:
            with self.subTest(scenario=scenario["name"]):
                planner_brief = build_scenario_brief(scenario)
                try:
                    live = run_scenario_live_planner(planner_brief)
                except PlannerProposalError as exc:
                    self.fail(f"live planner failed for scenario {scenario['name']}: {exc}")

                validation = live["validation"]
                if validation["is_valid"]:
                    candidate = validation["normalized_plan_proposal"]["weekly_skeleton"]
                else:
                    repaired = repair_or_fallback_plan(validation, planner_brief)
                    candidate = repaired["weekly_skeleton"]

                assert_quality_guardrails_goal_fit(
                    self,
                    planner_brief,
                    candidate,
                    required_goal_tokens=list(scenario["required_goal_tokens"]),
                )


class TestPlannerScenarioIntegration(unittest.TestCase):
    def test_run_rule_engine_for_week_accepts_distinct_valid_shapes_same_guardrails(self):
        scenario = next(item for item in SCENARIOS if item["name"] == "experienced_marathon_8w_green")
        rendered_payload = valid_engine_output_payload()["next_email_payload"]
        accepted_shapes: List[Tuple[str, ...]] = []

        for plan_shape in scenario["valid_shapes"][:2]:
            with self.subTest(plan_shape=plan_shape):
                with mock.patch.object(rule_engine_orchestrator, "load_rule_state", return_value={}), mock.patch.object(
                    rule_engine_orchestrator,
                    "update_rule_state",
                    return_value={},
                ), mock.patch.object(
                    rule_engine_orchestrator,
                    "run_planner_workflow",
                    return_value={
                        "status": "accepted",
                        "source": "validated_planner_plan",
                        "weekly_skeleton": list(plan_shape),
                        "output_mode": "structure",
                        "planner_rationale": "scenario plan",
                        "planner_state_suggestions": ["advisory_only"],
                        "validation_errors": [],
                        "failure_reason": "",
                        "model_name": "",
                    },
                ), mock.patch.object(
                    rule_engine_orchestrator.LanguageReplyRenderer,
                    "render_reply",
                    return_value=rendered_payload,
                ):
                    output = rule_engine_orchestrator.run_rule_engine_for_week(
                        athlete_id="ath_1",
                        profile=dict(scenario["profile"]),
                        checkin=dict(scenario["checkin"]),
                        today_date=rule_engine_orchestrator.date(2026, 3, 4),
                    )

                planner_brief = build_scenario_brief(scenario)
                assert_quality_guardrails_goal_fit(
                    self,
                    planner_brief,
                    list(output.weekly_skeleton),
                    required_goal_tokens=list(scenario["required_goal_tokens"]),
                )
                accepted_shapes.append(tuple(output.weekly_skeleton))

        self.assertGreaterEqual(len(set(accepted_shapes)), 2)


if __name__ == "__main__":
    unittest.main()
