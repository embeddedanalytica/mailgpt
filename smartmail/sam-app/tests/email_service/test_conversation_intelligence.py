"""Unit tests for conversation intelligence extraction wrapper."""

import unittest
from unittest import mock

import conversation_intelligence


class TestConversationIntelligence(unittest.TestCase):
    def test_analyze_returns_validated_payload(self):
        with mock.patch.object(
            conversation_intelligence,
            "run_conversation_intelligence_workflow",
            return_value={
                "intent": "coaching",
                "complexity_score": 3,
                "model_name": conversation_intelligence.OPENAI_CLASSIFICATION_MODEL,
                "resolution_source": "single_prompt",
                "intent_resolution_reason": "llm_direct_classification",
            },
        ):
            result = conversation_intelligence.analyze_conversation_intelligence(
                "Travel week, only two days available."
            )

        self.assertEqual(result["intent"], "coaching")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["model_name"], conversation_intelligence.OPENAI_CLASSIFICATION_MODEL)
        self.assertEqual(result["resolution_source"], "single_prompt")
        self.assertEqual(result["intent_resolution_reason"], "llm_direct_classification")
        self.assertNotIn("signals", result)

    def test_analyze_fallbacks_on_contract_failures(self):
        with mock.patch.object(
            conversation_intelligence,
            "run_conversation_intelligence_workflow",
            side_effect=conversation_intelligence.ConversationIntelligenceProposalError("bad"),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence("Hi")

        self.assertEqual(result["intent"], "coaching")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["intent_resolution_reason"], "single_prompt_validation_failed")

    def test_analyze_fallbacks_on_runtime_error(self):
        with mock.patch.object(
            conversation_intelligence,
            "run_conversation_intelligence_workflow",
            side_effect=RuntimeError("boom"),
        ):
            result = conversation_intelligence.analyze_conversation_intelligence(
                "Finished my 10k in 46:30."
            )

        self.assertEqual(result["intent"], "coaching")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertEqual(result["intent_resolution_reason"], "llm_intelligence_failed")


if __name__ == "__main__":
    unittest.main()
