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
from skills.response_generation.prompt import SYSTEM_PROMPT
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
        "athlete_context": {
            "goal_summary": "10k race in 8 weeks",
            "experience_level": "intermediate",
            "structure_preference": "flexibility",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "yellow",
            "today_action": "do planned but conservative",
            "clarification_needed": False,
        },
        "validated_plan": {
            "weekly_skeleton": ["easy_aerobic", "strength", "tempo"],
            "plan_summary": "Current plan: rebuild consistency while protecting recovery.",
        },
        "delivery_context": {
            "inbound_subject": "Weekly check-in",
            "selected_model_name": "gpt-5-mini",
            "response_channel": "email",
        },
        "memory_context": {
            "memory_available": True,
            "backbone_summaries": {"hard_constraints": "Weekday sessions need to finish before 7am"},
            "context_notes": [_context_note()],
            "continuity_summary": {
                "summary": "Athlete is rebuilding consistency.",
                "last_recommendation": "Keep one controlled quality session this week.",
                "open_loops": ["How did the quality session feel?"],
                "updated_at": 1773273600,
            },
            "continuity_focus": "Athlete is rebuilding consistency.",
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
    if reply_mode == "clarification":
        payload["decision_context"] = {"clarification_needed": True}
        payload["validated_plan"] = {}
    elif reply_mode == "safety_risk_managed":
        payload["decision_context"] = {
            "risk_flag": "red_a",
            "today_action": "pause_training_and_get_clinical_guidance",
            "clarification_needed": False,
        }
        payload["validated_plan"] = {}
    elif reply_mode == "lightweight_non_planning":
        payload["decision_context"] = {}
        payload["validated_plan"] = {}
    elif reply_mode == "off_topic_redirect":
        payload["decision_context"] = {}
        payload["validated_plan"] = {}
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
    def test_prompt_instructs_authority_split_and_final_email_body(self):
        self.assertIn("response_brief JSON object", SYSTEM_PROMPT)
        self.assertIn("Never contradict risk posture", SYSTEM_PROMPT)
        self.assertIn("final_email_body must contain the complete email body", SYSTEM_PROMPT)
        self.assertIn("continuity_focus is context from the previous exchange", SYSTEM_PROMPT)
        self.assertIn("backbone_summaries are durable memory facts", SYSTEM_PROMPT)
        self.assertIn("Do not repeat every memory fact mechanically", SYSTEM_PROMPT)
        self.assertIn("clarification: ask only for the specific items listed in decision_context.clarification_questions", SYSTEM_PROMPT)
        self.assertIn("safety_risk_managed: prioritize caution", SYSTEM_PROMPT)
        self.assertIn("lightweight_non_planning: answer the athlete's question", SYSTEM_PROMPT)
        self.assertIn("off_topic_redirect: briefly redirect", SYSTEM_PROMPT)
        self.assertIn("Lead with the most important point", SYSTEM_PROMPT)
        self.assertIn("When the athlete is struggling", SYSTEM_PROMPT)
        self.assertIn("realistic coaching tone", SYSTEM_PROMPT)
        self.assertIn("Read the athlete's emotional state from inbound_body", SYSTEM_PROMPT)
        self.assertIn("Match the athlete's energy", SYSTEM_PROMPT)
        self.assertIn("do not become overly verbose", SYSTEM_PROMPT)
        self.assertIn("Do not contradict the brief", SYSTEM_PROMPT)
        self.assertIn("Avoid boilerplate closers", SYSTEM_PROMPT)
        self.assertIn("Never open with 'Hi there'", SYSTEM_PROMPT)

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


if __name__ == "__main__":
    unittest.main()
