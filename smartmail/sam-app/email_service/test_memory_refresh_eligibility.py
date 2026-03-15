"""Unit tests for memory refresh eligibility classification."""

import unittest
from unittest import mock

import skills.runtime as skill_runtime
from config import OPENAI_CLASSIFICATION_MODEL
from skills.memory import MemoryRefreshEligibilityError, run_memory_refresh_eligibility
from skills.memory.eligibility.eval import evaluate_cases
from skills.memory.eligibility.prompt import SYSTEM_PROMPT
from skills.memory.eligibility.schema import JSON_SCHEMA, JSON_SCHEMA_NAME


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


def _stub_openai_with_contents(contents):
    shared_contents = list(contents)
    return type(
        "OpenAIStubModule",
        (),
        {"OpenAI": lambda: _OpenAIClientStub(shared_contents)},
    )


class _CapturingOpenAIClientStub:
    def __init__(self, content: str):
        self.responses = self
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.content)


class TestMemoryRefreshEligibility(unittest.TestCase):
    def test_eligibility_uses_responses_api_with_strict_json_schema(self):
        client = _CapturingOpenAIClientStub(
            '{"should_refresh":false,"reason":"no_meaningful_change"}'
        )
        openai_stub = type("OpenAIStubModule", (), {"OpenAI": lambda: client})

        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime,
            "openai",
            openai_stub,
        ):
            run_memory_refresh_eligibility({"interaction_type": "x"})

        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["model"], OPENAI_CLASSIFICATION_MODEL)
        self.assertEqual(call["text"]["format"]["type"], "json_schema")
        self.assertEqual(call["text"]["format"]["name"], JSON_SCHEMA_NAME)
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual(call["text"]["format"]["schema"], JSON_SCHEMA)

    def test_system_prompt_includes_output_contract_and_reason_enums(self):
        prompt = SYSTEM_PROMPT
        self.assertIn("objective:", prompt.lower())
        self.assertIn("fresh session", prompt.lower())
        self.assertIn("response schema", prompt.lower())
        self.assertIn("durable_context_changed", prompt)
        self.assertIn("coaching_recommendation", prompt)
        self.assertIn("coaching_state_changed", prompt)
        self.assertIn("greeting_or_acknowledgement", prompt)
        self.assertIn("clarification_only", prompt)
        self.assertIn("no_meaningful_change", prompt)

    def test_system_prompt_includes_priority_and_output_constraints(self):
        prompt = SYSTEM_PROMPT
        self.assertIn("Decision priority", prompt)
        self.assertIn("1. durable_context_changed", prompt)
        self.assertIn("6. no_meaningful_change", prompt)
        self.assertIn("interaction_type is only a hint", prompt)
        self.assertIn("do not trigger solely because a coach recommendation exists", prompt.lower())
        self.assertIn("prefer should_refresh=true when the interaction may retire a stale durable assumption", prompt.lower())
        self.assertIn("messages that say the week was normal, on script, or unchanged", prompt.lower())
        self.assertNotIn('"should_refresh"', prompt)

    def test_json_schema_defines_strict_output_shape(self):
        self.assertFalse(JSON_SCHEMA["additionalProperties"])
        self.assertEqual(JSON_SCHEMA["required"], ["should_refresh", "reason"])
        self.assertEqual(
            set(JSON_SCHEMA["properties"]["reason"]["enum"]),
            {
                "durable_context_changed",
                "coaching_recommendation",
                "coaching_state_changed",
                "greeting_or_acknowledgement",
                "clarification_only",
                "no_meaningful_change",
            },
        )

    def test_analyze_returns_valid_trigger_payload(self):
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"should_refresh":true,"reason":"coaching_recommendation"}']
            ),
        ):
            result = run_memory_refresh_eligibility(
                {
                    "inbound_email": "Can I add one faster session?",
                    "coach_reply": "Yes, add one controlled moderate session.",
                    "interaction_type": "coaching_recommendation",
                }
            )
        self.assertTrue(result["should_refresh"])
        self.assertEqual(result["reason"], "coaching_recommendation")
        self.assertEqual(result["model_name"], OPENAI_CLASSIFICATION_MODEL)
        self.assertEqual(result["resolution_source"], "single_prompt")
        self.assertEqual(result["reason_resolution"], "llm_direct_classification")

    def test_analyze_returns_valid_skip_payload(self):
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"should_refresh":false,"reason":"greeting_or_acknowledgement"}']
            ),
        ):
            result = run_memory_refresh_eligibility(
                {
                    "inbound_email": "Thanks, that makes sense.",
                    "coach_reply": "You're welcome.",
                    "interaction_type": "acknowledgement",
                }
            )
        self.assertFalse(result["should_refresh"])
        self.assertEqual(result["reason"], "greeting_or_acknowledgement")

    def test_analyze_fallbacks_on_invalid_reason(self):
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"should_refresh":true,"reason":"always_refresh"}']
            ),
        ):
            result = run_memory_refresh_eligibility(
                {"interaction_type": "anything"}
            )
        self.assertFalse(result["should_refresh"])
        self.assertEqual(result["reason"], "no_meaningful_change")
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["reason_resolution"], "single_prompt_validation_failed")

    def test_analyze_fallbacks_on_inconsistent_bool_reason_pair(self):
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"should_refresh":false,"reason":"coaching_recommendation"}']
            ),
        ):
            result = run_memory_refresh_eligibility(
                {"interaction_type": "anything"}
            )
        self.assertFalse(result["should_refresh"])
        self.assertEqual(result["reason"], "no_meaningful_change")
        self.assertEqual(result["resolution_source"], "fallback")

    def test_analyze_fallbacks_when_schema_valid_but_bool_reason_pair_is_invalid(self):
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"should_refresh":true,"reason":"greeting_or_acknowledgement"}']
            ),
        ):
            result = run_memory_refresh_eligibility({"interaction_type": "anything"})
        self.assertFalse(result["should_refresh"])
        self.assertEqual(result["reason"], "no_meaningful_change")
        self.assertEqual(result["reason_resolution"], "single_prompt_validation_failed")

    def test_analyze_fallbacks_on_invalid_json(self):
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ["not-json", "still-not-json"]
            ),
        ):
            result = run_memory_refresh_eligibility(
                {"interaction_type": "durable_context_candidate"}
            )
        self.assertFalse(result["should_refresh"])
        self.assertEqual(result["reason_resolution"], "single_prompt_validation_failed")

    def test_analyze_fallbacks_on_runtime_error(self):
        openai_stub = type(
            "OpenAIStubModule",
            (),
            {"OpenAI": lambda: (_ for _ in ()).throw(RuntimeError("boom"))},
        )
        with mock.patch.object(
            skill_runtime,
            "live_llm_enabled",
            return_value=True,
        ), mock.patch.object(skill_runtime, "openai", openai_stub):
            result = run_memory_refresh_eligibility(
                {"interaction_type": "durable_context_candidate"}
            )
        self.assertFalse(result["should_refresh"])
        self.assertEqual(result["reason"], "no_meaningful_change")
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["reason_resolution"], "llm_memory_refresh_eligibility_failed")

    def test_non_dict_input_raises(self):
        with self.assertRaises(MemoryRefreshEligibilityError):
            run_memory_refresh_eligibility("not-a-dict")

    def test_eval_cases_reports_match_and_mismatch(self):
        results = evaluate_cases(
            [
                {
                    "case_id": "match",
                    "interaction_context": {"interaction_type": "x"},
                    "expected": {"should_refresh": False, "reason": "no_meaningful_change"},
                },
                {
                    "case_id": "mismatch",
                    "interaction_context": {"interaction_type": "y"},
                    "expected": {"should_refresh": True, "reason": "coaching_recommendation"},
                },
            ],
            evaluator=lambda _ctx: {
                "should_refresh": False,
                "reason": "no_meaningful_change",
                "model_name": "test-model",
                "resolution_source": "single_prompt",
                "reason_resolution": "llm_direct_classification",
            },
        )
        self.assertEqual(results[0]["case_id"], "match")
        self.assertTrue(results[0]["matched"])
        self.assertFalse(results[1]["matched"])
        self.assertIn("should_refresh", results[1]["mismatches"])


if __name__ == "__main__":
    unittest.main()
