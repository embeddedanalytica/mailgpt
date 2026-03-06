"""Unit tests for LLM conversation intelligence extraction."""
import unittest
from unittest import mock

import conversation_intelligence


class _Response:
    def __init__(self, content: str):
        class _Message:
            pass

        class _Choice:
            pass

        message = _Message()
        message.content = content
        choice = _Choice()
        choice.message = message
        self.choices = [choice]


class _OpenAIClientStub:
    def __init__(self, contents):
        self._contents = contents
        self.chat = self
        self.completions = self

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


class TestConversationIntelligence(unittest.TestCase):
    def test_analyze_returns_validated_payload(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            _stub_openai_with_contents(
                ['{"intent":"availability_update","complexity_score":3}']
            ),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence(
                "Travel week, only two days available."
            )
        self.assertEqual(result["intent"], "availability_update")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["model_name"], conversation_intelligence.OPENAI_CLASSIFICATION_MODEL)
        self.assertEqual(result["resolution_source"], "single_prompt")
        self.assertEqual(result["intent_resolution_reason"], "llm_direct_classification")
        self.assertNotIn("signals", result)

    def test_analyze_fallbacks_on_invalid_intent(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            _stub_openai_with_contents(
                ['{"intent":"invalid","complexity_score":2}']
            ),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence("Hi")
        self.assertEqual(result["intent"], "question")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["intent_resolution_reason"], "single_prompt_validation_failed")

    def test_analyze_fallbacks_on_non_integer_complexity(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            _stub_openai_with_contents(
                ['{"intent":"question","complexity_score":"2"}']
            ),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence(
                "Can I race this weekend?"
            )
        self.assertEqual(result["intent"], "question")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["resolution_source"], "fallback")

    def test_analyze_fallbacks_on_invalid_json(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            _stub_openai_with_contents(
                [
                    "not-json",
                    "still-not-json",
                ]
            ),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence(
                "My knee hurts badly, should I train?"
            )
        self.assertEqual(result["intent"], "question")
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["intent_resolution_reason"], "single_prompt_validation_failed")

    def test_analyze_fallbacks_on_runtime_error(self):
        openai_stub = type(
            "OpenAIStubModule",
            (),
            {"OpenAI": lambda: (_ for _ in ()).throw(RuntimeError("boom"))},
        )
        with mock.patch.object(conversation_intelligence, "openai", openai_stub):
            result = conversation_intelligence.analyze_conversation_intelligence(
                "Finished my 10k in 46:30."
            )
        self.assertEqual(result["intent"], "question")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["intent_resolution_reason"], "llm_intelligence_failed")


if __name__ == "__main__":
    unittest.main()
