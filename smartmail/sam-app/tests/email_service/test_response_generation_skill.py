"""Unit tests for the response-generation skill workflow."""

import unittest
from unittest import mock

import skills.runtime as skill_runtime
from config import LANGUAGE_RENDER_MODEL
from skills.response_generation import evaluate_cases, run_response_generation_workflow
from skills.response_generation.errors import (
    ResponseGenerationContractError,
    ResponseGenerationProposalError,
)
from skills.response_generation.prompt import (
    _directive_mentions_training_position,
    _content_plan_has_decision,
    _is_narrow_directive,
)
from skills.response_generation.schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.response_generation.validator import (
    validate_response_generation_brief,
    validate_response_generation_output,
)


class _Response:
    def __init__(self, content: str):
        self.output_text = content


class _OpenAIClientStub:
    def __init__(self, contents):
        self._contents = contents
        self.responses = self

    def create(self, **_kwargs):
        if self._contents:
            return _Response(self._contents.pop(0))
        return _Response("{}")


class _CapturingOpenAIClientStub:
    def __init__(self, content: str):
        self.responses = self
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.content)


def _stub_openai_with_contents(contents):
    shared_contents = list(contents)
    return type("OpenAIStubModule", (), {"OpenAI": lambda: _OpenAIClientStub(shared_contents)})


def _context_note(label: str = "Schedule", summary: str = "Weekday sessions need to finish before 7am") -> dict:
    return {"label": label, "summary": summary, "updated_at": 1773273600}


def _valid_brief() -> dict:
    return {
        "reply_mode": "normal_coaching",
        "coaching_directive": {
            "opening": "Test opening",
            "main_message": "Keep one controlled quality session this week.",
            "content_plan": ["present the plan"],
            "avoid": [],
            "tone": "calm and direct",
            "recommend_material": None,
        },
        "plan_data": {
            "weekly_skeleton": ["easy_aerobic", "strength", "tempo"],
            "plan_summary": "Current plan: rebuild consistency while protecting recovery.",
        },
        "delivery_context": {
            "inbound_subject": "Weekly check-in",
            "selected_model_name": "gpt-5-mini",
        },
    }


def _valid_output() -> dict:
    return {
        "final_email_body": (
            "You can still move the week forward, but keep this one controlled.\n\n"
            "I want one purposeful session only if your legs feel steady, with easy aerobic work around it."
        ),
    }


def _brief_for_mode(reply_mode: str) -> dict:
    payload = _valid_brief()
    payload["reply_mode"] = reply_mode
    if reply_mode in ("clarification", "safety_risk_managed", "lightweight_non_planning", "off_topic_redirect"):
        payload["plan_data"] = {}
    return payload


class TestResponseGenerationSkill(unittest.TestCase):
    def test_runner_uses_responses_api_with_strict_json_schema(self):
        client = _CapturingOpenAIClientStub(
            '{"final_email_body":"You can still move the week forward, but keep this one controlled.\\n\\nI want one purposeful session only if your legs feel steady, with easy aerobic work around it."}'
        )
        openai_stub = type("OpenAIStubModule", (), {"OpenAI": lambda: client})

        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", openai_stub
        ):
            run_response_generation_workflow(_valid_brief())

        call = client.calls[0]
        self.assertEqual(call["model"], LANGUAGE_RENDER_MODEL)
        self.assertEqual(call["text"]["format"]["name"], JSON_SCHEMA_NAME)
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual(call["text"]["format"]["schema"], JSON_SCHEMA)

    def test_invalid_brief_fails_before_llm_call(self):
        payload = _valid_brief()
        del payload["reply_mode"]

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_generation_brief(payload)

        with self.assertRaises(ResponseGenerationContractError):
            run_response_generation_workflow(payload)

    def test_malformed_output_fails_validation(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", _stub_openai_with_contents(['{"subject_hint":"missing required fields"}'])
        ):
            with self.assertRaises(ResponseGenerationProposalError):
                run_response_generation_workflow(_valid_brief())

    def test_returns_normalized_final_email_response(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"final_email_body":"You can still move the week forward, but keep this one controlled.\\n\\nI want one purposeful session only if your legs feel steady, with easy aerobic work around it."}']
            ),
        ):
            result = run_response_generation_workflow(_valid_brief(), model_name="gpt-5-nano")

        self.assertIn("keep this one controlled", result["final_email_body"])
        self.assertEqual(result["model_name"], "gpt-5-nano")

    def test_runtime_invalid_json_raises_workflow_error(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", _stub_openai_with_contents(["not-json", "still-not-json"])
        ):
            with self.assertRaises(ResponseGenerationProposalError):
                run_response_generation_workflow(_valid_brief())


class TestResponseGenerationPromptAndSchema(unittest.TestCase):
    def test_schema_matches_final_email_output(self):
        validated = validate_response_generation_output(_valid_output())
        self.assertEqual(set(validated.keys()), set(JSON_SCHEMA["required"]))

    def test_validator_accepts_all_supported_reply_modes(self):
        for reply_mode in (
            "normal_coaching",
            "clarification",
            "safety_risk_managed",
            "lightweight_non_planning",
            "off_topic_redirect",
        ):
            payload = _valid_brief()
            payload["reply_mode"] = reply_mode
            validated = validate_response_generation_brief(payload)
            self.assertEqual(validated["reply_mode"], reply_mode)

    def test_representative_mode_output_patterns_match_expected_guidance(self):
        representative_outputs = {
            "normal_coaching": {
                "final_email_body": (
                    "Keep this week controlled.\n\n"
                    "I want one purposeful session only if your legs feel steady, with easy work around it."
                )
            },
            "clarification": {
                "final_email_body": (
                    "Before I change anything, reply with your event date, available training days, and current pain score."
                )
            },
            "safety_risk_managed": {
                "final_email_body": (
                    "Pause training for now and get medical guidance before the next hard session.\n\n"
                    "Reply once you know what your clinician advised."
                )
            },
            "lightweight_non_planning": {
                "final_email_body": (
                    "Easy runs should stay conversational. If you need to slow down to keep that feeling, that's the right move."
                )
            },
            "off_topic_redirect": {
                "final_email_body": (
                    "I can help with training, recovery, and plan adjustments. Send me your latest workout update or coaching question."
                )
            },
        }

        cases = [
            {
                "case_id": "normal",
                "response_brief": _brief_for_mode("normal_coaching"),
                "expected": {
                    "required_phrases": ["purposeful session"],
                    "forbidden_phrases": ["event date", "medical guidance"],
                    "max_lines": 4,
                },
            },
            {
                "case_id": "clarification",
                "response_brief": _brief_for_mode("clarification"),
                "expected": {
                    "required_phrases": ["event date", "pain score"],
                    "forbidden_phrases": ["This week", "purposeful session"],
                    "max_lines": 2,
                },
            },
            {
                "case_id": "safety",
                "response_brief": _brief_for_mode("safety_risk_managed"),
                "expected": {
                    "required_phrases": ["Pause training", "medical guidance"],
                    "forbidden_phrases": ["weekly plan rewrite", "purposeful session"],
                    "max_lines": 4,
                },
            },
            {
                "case_id": "lightweight",
                "response_brief": _brief_for_mode("lightweight_non_planning"),
                "expected": {
                    "required_phrases": ["conversational"],
                    "forbidden_phrases": ["This week", "weekly skeleton"],
                    "max_lines": 3,
                },
            },
            {
                "case_id": "redirect",
                "response_brief": _brief_for_mode("off_topic_redirect"),
                "expected": {
                    "required_phrases": ["training", "coaching question"],
                    "forbidden_phrases": ["weekly plan", "pain score"],
                    "max_lines": 3,
                },
            },
        ]

        def _fixture_evaluator(brief):
            return representative_outputs[brief["reply_mode"]]

        results = evaluate_cases(cases, evaluator=_fixture_evaluator)
        self.assertTrue(all(result["matched"] for result in results), results)


class TestNarrowDirectiveDetection(unittest.TestCase):
    """Verify _is_narrow_directive correctly identifies minimal directives."""

    def test_short_message_few_items_is_narrow(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Got it."
        brief["coaching_directive"]["content_plan"] = ["acknowledge"]
        self.assertTrue(_is_narrow_directive(brief))

    def test_long_message_is_not_narrow(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "x" * 150
        brief["coaching_directive"]["content_plan"] = ["acknowledge"]
        self.assertFalse(_is_narrow_directive(brief))

    def test_many_content_items_is_not_narrow(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Brief"
        brief["coaching_directive"]["content_plan"] = ["a", "b", "c"]
        self.assertFalse(_is_narrow_directive(brief))

    def test_decision_in_content_plan_is_not_narrow(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Brief."
        brief["coaching_directive"]["content_plan"] = ["approve Thursday pickups"]
        self.assertFalse(_is_narrow_directive(brief))

    def test_progression_in_content_plan_is_not_narrow(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Brief."
        brief["coaching_directive"]["content_plan"] = ["progress to 2x strength"]
        self.assertFalse(_is_narrow_directive(brief))

    def test_transition_in_content_plan_is_not_narrow(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Ready."
        brief["coaching_directive"]["content_plan"] = ["move to build phase"]
        self.assertFalse(_is_narrow_directive(brief))


class TestContentPlanDecisionDetection(unittest.TestCase):
    """Verify _content_plan_has_decision catches decision language."""

    def test_simple_ack_is_not_decision(self):
        self.assertFalse(_content_plan_has_decision(["acknowledge check-in"]))

    def test_approve_is_decision(self):
        self.assertTrue(_content_plan_has_decision(["approve Thursday pickups"]))

    def test_add_session_is_decision(self):
        self.assertTrue(_content_plan_has_decision(["add Friday easy run"]))

    def test_progress_is_decision(self):
        self.assertTrue(_content_plan_has_decision(["progress to 2x strength per week"]))

    def test_increase_is_decision(self):
        self.assertTrue(_content_plan_has_decision(["increase long run to 90 min"]))

    def test_cleared_for_is_decision(self):
        self.assertTrue(_content_plan_has_decision(["cleared for tempo work"]))

    def test_start_is_decision(self):
        self.assertTrue(_content_plan_has_decision(["start Thursday pickups"]))

    def test_empty_is_not_decision(self):
        self.assertFalse(_content_plan_has_decision([]))


class TestContinuityAnchoringDetection(unittest.TestCase):
    def test_week_reference_requires_continuity_anchor(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Week 4 stays controlled."
        brief["coaching_directive"]["content_plan"] = ["confirm the week 4 focus"]
        self.assertTrue(_directive_mentions_training_position(brief))

    def test_block_reference_requires_continuity_anchor(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Stay in this block."
        brief["coaching_directive"]["content_plan"] = ["hold the current block focus"]
        self.assertTrue(_directive_mentions_training_position(brief))

    def test_plain_ack_does_not_require_continuity_anchor(self):
        brief = _valid_brief()
        brief["coaching_directive"]["main_message"] = "Got it."
        brief["coaching_directive"]["content_plan"] = ["acknowledge"]
        self.assertFalse(_directive_mentions_training_position(brief))


if __name__ == "__main__":
    unittest.main()
