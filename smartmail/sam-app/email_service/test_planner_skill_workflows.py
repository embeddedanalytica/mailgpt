"""Unit tests for planner-owned non-plan skill workflows."""

import unittest
from unittest import mock

import skills.runtime as skill_runtime
from skills.planner import (
    ConversationIntelligenceProposalError,
    ProfileExtractionProposalError,
    SessionCheckinExtractionProposalError,
    run_conversation_intelligence_workflow,
    run_profile_extraction_workflow,
    run_session_checkin_extraction_workflow,
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


def _stub_openai_with_contents(contents):
    shared_contents = list(contents)
    return type("OpenAIStubModule", (), {"OpenAI": lambda: _OpenAIClientStub(shared_contents)})


class TestConversationIntelligenceWorkflow(unittest.TestCase):
    def test_returns_validated_payload(self):
        with mock.patch.object(skill_runtime, "openai", _stub_openai_with_contents([
            '{"intent":"availability_update","complexity_score":3}'
        ])):
            result = run_conversation_intelligence_workflow("Travel week")

        self.assertEqual(result["intent"], "availability_update")
        self.assertEqual(result["complexity_score"], 3)
        self.assertEqual(result["resolution_source"], "single_prompt")

    def test_invalid_json_raises(self):
        with mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(["not-json", "still-not-json"]),
        ):
            with self.assertRaises(ConversationIntelligenceProposalError):
                run_conversation_intelligence_workflow("Travel week")


class TestProfileExtractionWorkflow(unittest.TestCase):
    def test_returns_dict_payload(self):
        with mock.patch.object(skill_runtime, "openai", _stub_openai_with_contents([
            '{"primary_goal":"10k PR"}'
        ])):
            result = run_profile_extraction_workflow("Goal: 10k PR")

        self.assertEqual(result["primary_goal"], "10k PR")

    def test_invalid_json_raises(self):
        with mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(["bad", "still-bad"]),
        ):
            with self.assertRaises(ProfileExtractionProposalError):
                run_profile_extraction_workflow("Goal: 10k PR")

    def test_rejects_time_placeholder_only_payload(self):
        with mock.patch.object(skill_runtime, "openai", _stub_openai_with_contents([
            '{"primary_goal":null,"time_availability":{"sessions_per_week":0,"hours_per_week":0},"experience_level":"unknown","experience_level_note":null,"constraints":[]}',
            '{"primary_goal":null,"time_availability":{"sessions_per_week":0,"hours_per_week":0},"experience_level":"unknown","experience_level_note":null,"constraints":[]}',
        ])):
            with self.assertRaises(ProfileExtractionProposalError):
                run_profile_extraction_workflow("No clear profile details yet.")


class TestSessionCheckinExtractionWorkflow(unittest.TestCase):
    def test_validates_and_sanitizes_payload(self):
        with mock.patch.object(skill_runtime, "openai", _stub_openai_with_contents([
            '{"pain_score":2,"event_date":"2026-06-20","week_chaotic":null}'
        ])):
            result = run_session_checkin_extraction_workflow("Pain 2/10 and race on June 20")

        self.assertEqual(result["pain_score"], 2)
        self.assertEqual(result["event_date"], "2026-06-20")
        self.assertNotIn("week_chaotic", result)

    def test_invalid_json_raises(self):
        with mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(["{", "{"]),
        ):
            with self.assertRaises(SessionCheckinExtractionProposalError):
                run_session_checkin_extraction_workflow("Pain 2/10")


if __name__ == "__main__":
    unittest.main()
