"""Direct tests for the planner component boundary."""

from __future__ import annotations

import unittest
from unittest import mock

import skills.runtime as skill_runtime
from config import PLANNING_LLM_MODEL
from rule_engine import HARD_SESSION_TAGS, NON_HARD_SESSION_TAGS, build_decision_envelope
from skills.planner import (
    JSON_SCHEMA,
    JSON_SCHEMA_NAME,
    PlannerContractError,
    PlannerProposalError,
    PlanningLLM,
    build_planner_brief,
    repair_or_fallback_plan,
    run_planner_workflow,
    validate_planner_brief,
    validate_planner_output,
    validate_planner_response,
)
from skills.planner.eval import evaluate_cases


class _Response:
    def __init__(self, content: str):
        self.output_text = content


class _CapturingOpenAIClientStub:
    def __init__(self, content: str):
        self.responses = self
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.content)


class _OpenAIClientStub:
    def __init__(self, contents):
        self.responses = self
        self._contents = contents

    def create(self, **_kwargs):
        if self._contents:
            return _Response(self._contents.pop(0))
        return _Response("{}")


def _stub_openai_with_contents(contents):
    shared_contents = list(contents)
    return type(
        "OpenAIStubModule",
        (),
        {"OpenAI": lambda: _OpenAIClientStub(shared_contents)},
    )


def _planner_brief() -> dict:
    envelope = build_decision_envelope(
        {"main_sport_current": "run"},
        {"days_available": 4, "structure_preference": "flexibility"},
        "build",
        "yellow",
        "return_or_risk_managed",
        False,
        {},
        fallback_skeleton=["easy_aerobic", "strength"],
        adjustments=["reduce_intensity"],
        plan_update_status="updated",
        today_action="prioritize_big_2_anchors",
        routing_context={"winning_signal": "chaos"},
    )
    return build_planner_brief(
        {"structure_preference": "flexibility"},
        {"days_available": 4, "structure_preference": "flexibility"},
        envelope,
        {},
    )


class TestPlannerContracts(unittest.TestCase):
    def test_build_planner_brief_contract(self):
        brief = _planner_brief()
        self.assertEqual(brief["risk_flag"], "yellow")
        self.assertEqual(brief["structure_preference"], "flexibility")
        self.assertIn("hard_limits", brief)
        self.assertIn("weekly_targets", brief)
        self.assertEqual(brief["fallback_skeleton"], ["easy_aerobic", "strength"])

    def test_validate_planner_brief_rejects_extra_keys(self):
        brief = _planner_brief()
        brief["unexpected"] = True
        with self.assertRaises(PlannerContractError):
            validate_planner_brief(brief)

    def test_validate_planner_response_normalizes_and_rejects_extra_keys(self):
        response = validate_planner_response(
            {
                "plan_proposal": {"weekly_skeleton": ["Easy_Aerobic", "strength"]},
                "rationale": "safe plan",
                "non_binding_state_suggestions": ["  advisory note  "],
            },
            model_name="planner-test",
        )
        self.assertEqual(response["plan_proposal"]["weekly_skeleton"], ["easy_aerobic", "strength"])
        self.assertEqual(response["non_binding_state_suggestions"], ["advisory note"])
        self.assertEqual(response["model_name"], "planner-test")

        with self.assertRaises(PlannerContractError):
            validate_planner_response(
                {
                    "plan_proposal": {"weekly_skeleton": ["easy_aerobic"]},
                    "rationale": "ok",
                    "non_binding_state_suggestions": [],
                    "extra": "nope",
                }
            )

    def test_validate_planner_output_and_repair(self):
        planner_brief = _planner_brief()
        invalid = {"weekly_skeleton": ["tempo", "intervals", "unknown_tag"]}
        validation = validate_planner_output(planner_brief, invalid)
        self.assertFalse(validation["is_valid"])
        repaired = repair_or_fallback_plan(validation, planner_brief)
        self.assertIn(repaired["source"], {"repaired_planner_plan", "deterministic_fallback"})
        self.assertEqual(repaired["status"], "repaired_or_fallback")
        self.assertTrue(all(token in HARD_SESSION_TAGS | NON_HARD_SESSION_TAGS for token in repaired["weekly_skeleton"]))
        self.assertLessEqual(
            sum(1 for token in repaired["weekly_skeleton"] if token in HARD_SESSION_TAGS),
            1,
        )
        self.assertTrue(repaired["failure_reason"])

    def test_validate_planner_output_guardrails(self):
        planner_brief = _planner_brief()
        invalid = {"weekly_skeleton": ["tempo", "intervals"]}
        validation = validate_planner_output(planner_brief, invalid)
        self.assertIn("hard_session_budget_exceeded", validation["errors"])
        self.assertIn("back_to_back_hard_days", validation["errors"])

        red_brief = dict(planner_brief)
        red_brief["risk_flag"] = "red_b"
        validation = validate_planner_output(red_brief, {"weekly_skeleton": ["tempo", "easy_aerobic"]})
        self.assertIn("red_tier_intensity_forbidden", validation["errors"])


class TestPlannerRunner(unittest.TestCase):
    def test_runner_uses_responses_api_with_strict_json_schema(self):
        client = _CapturingOpenAIClientStub(
            '{"plan_proposal":{"weekly_skeleton":["easy_aerobic","strength"]},"rationale":"safe","non_binding_state_suggestions":["note"]}'
        )
        openai_stub = type("OpenAIStubModule", (), {"OpenAI": lambda: client})

        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime,
            "openai",
            openai_stub,
        ):
            PlanningLLM.propose_plan(_planner_brief())

        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["model"], PLANNING_LLM_MODEL)
        self.assertEqual(call["text"]["format"]["type"], "json_schema")
        self.assertEqual(call["text"]["format"]["name"], JSON_SCHEMA_NAME)
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual(call["text"]["format"]["schema"], JSON_SCHEMA)

    def test_run_planner_workflow_accepts_valid_plan(self):
        with mock.patch.object(
            PlanningLLM,
            "propose_plan",
            return_value={
                "plan_proposal": {"weekly_skeleton": ["easy_aerobic", "strength"]},
                "rationale": "safe",
                "non_binding_state_suggestions": ["note"],
                "model_name": "planner-x",
            },
        ):
            result = run_planner_workflow(_planner_brief())
        self.assertEqual(result["status"], "accepted")
        self.assertEqual(result["source"], "validated_planner_plan")
        self.assertEqual(result["weekly_skeleton"], ["easy_aerobic", "strength"])
        self.assertEqual(result["failure_reason"], "")

    def test_run_planner_workflow_repairs_invalid_plan(self):
        with mock.patch.object(
            PlanningLLM,
            "propose_plan",
            return_value={
                "plan_proposal": {"weekly_skeleton": ["tempo", "intervals", "unknown_tag"]},
                "rationale": "unsafe",
                "non_binding_state_suggestions": ["note"],
                "model_name": "planner-x",
            },
        ):
            result = run_planner_workflow(_planner_brief())
        self.assertEqual(result["status"], "repaired_or_fallback")
        self.assertIn(result["source"], {"repaired_planner_plan", "deterministic_fallback"})
        self.assertTrue(result["validation_errors"])
        self.assertEqual(result["planner_state_suggestions"], ["note"])

    def test_run_planner_workflow_falls_back_when_unavailable(self):
        with mock.patch.object(
            PlanningLLM,
            "propose_plan",
            side_effect=PlannerProposalError("planning llm proposal failed"),
        ):
            result = run_planner_workflow(_planner_brief())
        self.assertEqual(result["status"], "repaired_or_fallback")
        self.assertEqual(result["source"], "deterministic_fallback")
        self.assertEqual(result["failure_reason"], "planner_unavailable")

    def test_propose_plan_fails_closed_on_contract_invalid_payload(self):
        with mock.patch(
            "skills.runtime.live_llm_enabled",
            return_value=True,
        ), mock.patch(
            "skills.runtime.openai",
            _stub_openai_with_contents(
                [
                    '{"plan_proposal":{"weekly_skeleton":["easy_aerobic"]},"rationale":"ok","non_binding_state_suggestions":[],"extra":"unexpected"}'
                ]
            ),
        ):
            with self.assertRaises(PlannerProposalError):
                PlanningLLM.propose_plan(_planner_brief())


class TestPlannerEval(unittest.TestCase):
    def test_evaluate_cases_reports_matches(self):
        results = evaluate_cases(
            [
                {
                    "case_id": "accepted_case",
                    "planner_brief": _planner_brief(),
                    "expected": {
                        "status": "accepted",
                        "source": "validated_planner_plan",
                        "weekly_skeleton": ["easy_aerobic", "strength"],
                    },
                }
            ],
            evaluator=lambda planner_brief: {
                "status": "accepted",
                "source": "validated_planner_plan",
                "weekly_skeleton": list(planner_brief["fallback_skeleton"]),
                "output_mode": planner_brief["structure_preference"],
                "planner_rationale": "safe",
                "planner_state_suggestions": [],
                "validation_errors": [],
                "failure_reason": "",
                "model_name": "",
            },
        )
        self.assertEqual(len(results), 1)
        self.assertTrue(results[0]["matched"])


def _base_decision_envelope() -> dict:
    return build_decision_envelope(
        {"main_sport_current": "run"},
        {"days_available": 4, "structure_preference": "structure"},
        "build",
        "green",
        "return_or_risk_managed",
        False,
        {},
        fallback_skeleton=["easy_aerobic", "strength"],
        adjustments=[],
        plan_update_status="updated",
        today_action="prioritize_big_2_anchors",
        routing_context={"winning_signal": "stable"},
    )


class TestPlannerBriefContinuityContext(unittest.TestCase):

    def test_planner_brief_accepts_continuity_context(self):
        ctx = {
            "goal_horizon_type": "event",
            "current_phase": "build",
            "current_block_focus": "event_specific_build",
            "weeks_in_current_block": 4,
        }
        brief = build_planner_brief(
            {"structure_preference": "structure"},
            {"days_available": 4},
            _base_decision_envelope(),
            {},
            continuity_context=ctx,
        )
        self.assertEqual(brief["continuity_context"]["current_block_focus"], "event_specific_build")

    def test_planner_brief_without_continuity_context(self):
        brief = build_planner_brief(
            {"structure_preference": "structure"},
            {"days_available": 4},
            _base_decision_envelope(),
            {},
        )
        self.assertNotIn("continuity_context", brief)

    def test_validate_planner_brief_accepts_continuity_context(self):
        brief = _planner_brief()
        brief["continuity_context"] = {"current_block_focus": "maintain_fitness"}
        validated = validate_planner_brief(brief)
        self.assertIn("continuity_context", validated)

    def test_validate_planner_brief_still_rejects_unknown_keys(self):
        brief = _planner_brief()
        brief["totally_unknown"] = True
        with self.assertRaises(PlannerContractError):
            validate_planner_brief(brief)
