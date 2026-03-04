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
    def __init__(self, content: str):
        self._content = content
        self.chat = self
        self.completions = self

    def create(self, **_kwargs):
        return _Response(self._content)


class TestConversationIntelligence(unittest.TestCase):
    def test_analyze_returns_validated_payload(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            type("OpenAIStubModule", (), {"OpenAI": lambda: _OpenAIClientStub(
                '{"intent":"check_in","complexity_score":2}'
            )}),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence("I did 5 miles.")
        self.assertEqual(result["intent"], "check_in")
        self.assertEqual(result["complexity_score"], 2)
        self.assertEqual(result["model_name"], conversation_intelligence.OPENAI_CLASSIFICATION_MODEL)

    def test_analyze_raises_on_invalid_intent(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            type("OpenAIStubModule", (), {"OpenAI": lambda: _OpenAIClientStub(
                '{"intent":"invalid","complexity_score":2}'
            )}),
        ):
            with self.assertRaises(conversation_intelligence.ConversationIntelligenceError):
                conversation_intelligence.analyze_conversation_intelligence("Hi")

    def test_analyze_raises_on_non_integer_complexity(self):
        with mock.patch.object(
            conversation_intelligence,
            "openai",
            type("OpenAIStubModule", (), {"OpenAI": lambda: _OpenAIClientStub(
                '{"intent":"question","complexity_score":"2"}'
            )}),
        ):
            with self.assertRaises(conversation_intelligence.ConversationIntelligenceError):
                conversation_intelligence.analyze_conversation_intelligence("Can I race this weekend?")


if __name__ == "__main__":
    unittest.main()
