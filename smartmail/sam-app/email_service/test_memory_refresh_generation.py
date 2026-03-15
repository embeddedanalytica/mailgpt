"""Unit tests for split memory refresh generation."""

import unittest
from unittest import mock

import skills.runtime as skill_runtime
from config import OPENAI_CLASSIFICATION_MODEL, PROFILE_EXTRACTION_MODEL
from skills.memory import (
    MemoryRefreshError,
    run_long_term_memory_refresh,
    run_memory_refresh,
    run_memory_router,
    run_short_term_memory_refresh,
)
from skills.memory.long_term.schema import JSON_SCHEMA as LONG_TERM_SCHEMA
from skills.memory.long_term.schema import JSON_SCHEMA_NAME as LONG_TERM_SCHEMA_NAME
from skills.memory.router.schema import JSON_SCHEMA as ROUTER_SCHEMA
from skills.memory.router.schema import JSON_SCHEMA_NAME as ROUTER_SCHEMA_NAME
from skills.memory.short_term.schema import JSON_SCHEMA as SHORT_TERM_SCHEMA
from skills.memory.short_term.schema import JSON_SCHEMA_NAME as SHORT_TERM_SCHEMA_NAME


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


class _CapturingOpenAIClientStub:
    def __init__(self, content: str):
        self.responses = self
        self.content = content
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        return _Response(self.content)


def _note(
    note_id: int,
    *,
    fact_type: str = "schedule",
    fact_key: str = "masters_session_slot",
    summary: str = "Masters swim every Tuesday night",
    importance: str = "high",
    status: str = "active",
) -> dict:
    return {
        "memory_note_id": note_id,
        "fact_type": fact_type,
        "fact_key": fact_key,
        "summary": summary,
        "importance": importance,
        "status": status,
        "created_at": 1772928000,
        "updated_at": 1773014400,
        "last_confirmed_at": 1773014400,
    }


class TestMemoryRouterGeneration(unittest.TestCase):
    def test_router_uses_responses_api_with_strict_json_schema(self):
        client = _CapturingOpenAIClientStub('{"route":"both"}')
        openai_stub = type("OpenAIStubModule", (), {"OpenAI": lambda: client})

        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", openai_stub
        ):
            run_memory_router(
                prior_memory_notes=[],
                prior_continuity_summary=None,
                latest_interaction_context={"inbound_email": "hi"},
            )

        call = client.calls[0]
        self.assertEqual(call["model"], OPENAI_CLASSIFICATION_MODEL)
        self.assertEqual(call["text"]["format"]["name"], ROUTER_SCHEMA_NAME)
        self.assertTrue(call["text"]["format"]["strict"])
        self.assertEqual(call["text"]["format"]["schema"], ROUTER_SCHEMA)

    def test_router_falls_back_to_neither_on_invalid_route(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", _stub_openai_with_contents(['{"route":"always"}'])
        ):
            result = run_memory_router(
                prior_memory_notes=[],
                prior_continuity_summary=None,
                latest_interaction_context={"inbound_email": "hi"},
            )
        self.assertEqual(result["route"], "neither")
        self.assertEqual(result["resolution_source"], "fallback")
        self.assertIn("raw_response_text", result)
        self.assertIn("raw_llm_data", result)

    def test_router_returns_raw_debug_fields_on_success(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", _stub_openai_with_contents(['{"route":"both"}'])
        ):
            result = run_memory_router(
                prior_memory_notes=[],
                prior_continuity_summary=None,
                latest_interaction_context={"inbound_email": "hi"},
            )

        self.assertEqual(result["route"], "both")
        self.assertEqual(result["raw_llm_data"], {"route": "both"})
        self.assertEqual(result["raw_response_text"], '{"route":"both"}')


class TestArtifactUpdaterGeneration(unittest.TestCase):
    def test_long_term_updater_reduces_candidates_into_notes(self):
        client = _CapturingOpenAIClientStub(
            '{"candidates":[{"action":"upsert","memory_note_id":0,"fact_type":"constraint","fact_key":"weekday_cutoff","summary":"Weekday sessions need to finish before 7am","importance":"high","reason":"","evidence_source":"athlete_email","evidence_strength":"explicit"}],"consolidation_ops":[]}'
        )
        openai_stub = type("OpenAIStubModule", (), {"OpenAI": lambda: client})

        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime, "openai", openai_stub
        ):
            result = run_long_term_memory_refresh(
                prior_memory_notes=[],
                latest_interaction_context={"inbound_email": "I can only train before 7am"},
            )

        call = client.calls[0]
        self.assertEqual(call["model"], PROFILE_EXTRACTION_MODEL)
        self.assertEqual(call["text"]["format"]["name"], LONG_TERM_SCHEMA_NAME)
        self.assertEqual(call["text"]["format"]["schema"], LONG_TERM_SCHEMA)
        self.assertEqual(result["memory_notes"][0]["fact_key"], "weekday_cutoff")
        self.assertEqual(result["memory_notes"][0]["memory_note_id"], 1)

    def test_short_term_updater_trims_extra_open_loops(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                [
                    '{"continuity_summary":{"summary":"Athlete is rebuilding after travel.","last_recommendation":"Keep one moderate session this week.","open_loops":["one","two","three","four"],"updated_at":1773273600}}'
                ]
            ),
        ), self.assertLogs("skills.memory.short_term.validator", level="INFO") as logs:
            refreshed = run_short_term_memory_refresh(
                prior_continuity_summary=None,
                latest_interaction_context={
                    "inbound_email": "Travel is over. Calf felt fine this week.",
                    "coach_reply": "You can add one moderate session.",
                },
            )

        self.assertEqual(refreshed["continuity_summary"]["open_loops"], ["one", "two", "three"])
        self.assertIn("trimming to 3 most relevant items", "\n".join(logs.output))

    def test_long_term_updater_rejects_conflicting_actions_on_same_note(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                [
                    '{"candidates":[{"action":"confirm","memory_note_id":1,"fact_type":"","fact_key":"","summary":"","importance":"","reason":"","evidence_source":"athlete_email","evidence_strength":"explicit"},{"action":"retire","memory_note_id":1,"fact_type":"","fact_key":"","summary":"","importance":"","reason":"Athlete explicitly said it ended.","evidence_source":"athlete_email","evidence_strength":"explicit"}],"consolidation_ops":[]}'
                ]
            ),
        ):
            result = run_long_term_memory_refresh(
                prior_memory_notes=[
                    _note(
                        1,
                        summary="Masters swim every Tuesday night",
                        fact_key="masters_session_slot",
                    )
                ],
                latest_interaction_context={"inbound_email": "hi"},
            )
        self.assertEqual(result["memory_notes"][0]["status"], "active")

    def test_short_term_updater_rejects_invalid_payload(self):
        with mock.patch.object(skill_runtime, "live_llm_enabled", return_value=True), mock.patch.object(
            skill_runtime,
            "openai",
            _stub_openai_with_contents(
                ['{"continuity_summary":{"summary":"ok","last_recommendation":"ok","open_loops":["one"],"updated_at":0}}']
            ),
        ):
            with self.assertRaises(MemoryRefreshError) as exc_info:
                run_short_term_memory_refresh(
                    prior_continuity_summary=None,
                    latest_interaction_context={"coach_reply": "ok"},
                )
        self.assertIn("positive unix timestamp", exc_info.exception.cause_message)


class TestMemoryRefreshOrchestration(unittest.TestCase):
    def test_neither_returns_prior_state_unchanged(self):
        with mock.patch("skills.memory.refresh.runner.run_memory_router", return_value={"route": "neither"}), mock.patch(
            "skills.memory.refresh.runner.run_long_term_memory_refresh"
        ) as run_long_term, mock.patch(
            "skills.memory.refresh.runner.run_short_term_memory_refresh"
        ) as run_short_term:
            refreshed = run_memory_refresh(
                prior_memory_notes=[],
                prior_continuity_summary={
                    "summary": "Keep things steady.",
                    "last_recommendation": "Hold the line.",
                    "open_loops": [],
                    "updated_at": 1773273600,
                },
                latest_interaction_context={"inbound_email": "routine update"},
            )

        self.assertEqual(refreshed["memory_notes"], [])
        self.assertEqual(refreshed["continuity_summary"]["summary"], "Keep things steady.")
        run_long_term.assert_not_called()
        run_short_term.assert_not_called()

    def test_long_term_updates_only_notes(self):
        with mock.patch("skills.memory.refresh.runner.run_memory_router", return_value={"route": "long_term"}), mock.patch(
            "skills.memory.refresh.runner.run_long_term_memory_refresh",
            return_value={
                "memory_notes": [
                    _note(
                        1,
                        fact_type="constraint",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Before 7am only",
                    )
                ]
            },
        ) as run_long_term, mock.patch(
            "skills.memory.refresh.runner.run_short_term_memory_refresh"
        ) as run_short_term:
            refreshed = run_memory_refresh(
                prior_memory_notes=[],
                prior_continuity_summary={
                    "summary": "Existing continuity.",
                    "last_recommendation": "Existing recommendation.",
                    "open_loops": ["Existing loop"],
                    "updated_at": 1773100800,
                },
                latest_interaction_context={"inbound_email": "Before 7am only now."},
            )

        self.assertEqual(refreshed["memory_notes"][0]["summary"], "Before 7am only")
        self.assertEqual(refreshed["continuity_summary"]["summary"], "Existing continuity.")
        run_long_term.assert_called_once()
        run_short_term.assert_not_called()

    def test_long_term_without_prior_continuity_does_not_fail(self):
        with mock.patch("skills.memory.refresh.runner.run_memory_router", return_value={"route": "long_term"}), mock.patch(
            "skills.memory.refresh.runner.run_long_term_memory_refresh",
            return_value={
                "memory_notes": [
                    _note(
                        1,
                        fact_type="constraint",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Before 7am only",
                    )
                ]
            },
        ) as run_long_term, mock.patch(
            "skills.memory.refresh.runner.run_short_term_memory_refresh"
        ) as run_short_term:
            refreshed = run_memory_refresh(
                prior_memory_notes=[],
                prior_continuity_summary=None,
                latest_interaction_context={"inbound_email": "Before 7am only now."},
            )

        self.assertEqual(refreshed["memory_notes"][0]["summary"], "Before 7am only")
        self.assertIsNone(refreshed["continuity_summary"])
        run_long_term.assert_called_once()
        run_short_term.assert_not_called()

    def test_short_term_updates_only_continuity(self):
        with mock.patch("skills.memory.refresh.runner.run_memory_router", return_value={"route": "short_term"}), mock.patch(
            "skills.memory.refresh.runner.run_long_term_memory_refresh"
        ) as run_long_term, mock.patch(
            "skills.memory.refresh.runner.run_short_term_memory_refresh",
            return_value={
                "continuity_summary": {
                    "summary": "Travel week only.",
                    "last_recommendation": "Use the hotel treadmill.",
                    "open_loops": ["Check in when home"],
                    "updated_at": 1773273600,
                }
            },
        ) as run_short_term:
            refreshed = run_memory_refresh(
                prior_memory_notes=[
                    _note(
                        2,
                        fact_type="constraint",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Before 7am only",
                    )
                ],
                prior_continuity_summary={
                    "summary": "Existing continuity.",
                    "last_recommendation": "Existing recommendation.",
                    "open_loops": ["Existing loop"],
                    "updated_at": 1773100800,
                },
                latest_interaction_context={"coach_reply": "Use the hotel treadmill."},
            )

        self.assertEqual(refreshed["memory_notes"][0]["memory_note_id"], 2)
        self.assertEqual(refreshed["continuity_summary"]["summary"], "Travel week only.")
        run_long_term.assert_not_called()
        run_short_term.assert_called_once()

    def test_both_updates_and_merges(self):
        with mock.patch("skills.memory.refresh.runner.run_memory_router", return_value={"route": "both"}), mock.patch(
            "skills.memory.refresh.runner.run_long_term_memory_refresh",
            return_value={
                "memory_notes": [
                    _note(
                        3,
                        fact_type="schedule",
                        fact_key="saturday_availability",
                        summary="Saturday is open now",
                    )
                ]
            },
        ), mock.patch(
            "skills.memory.refresh.runner.run_short_term_memory_refresh",
            return_value={
                "continuity_summary": {
                    "summary": "Use Saturday this week.",
                    "last_recommendation": "Move the long run to Saturday.",
                    "open_loops": ["Confirm long run timing"],
                    "updated_at": 1773273600,
                }
            },
        ):
            refreshed = run_memory_refresh(
                prior_memory_notes=[],
                prior_continuity_summary={
                    "summary": "Old continuity.",
                    "last_recommendation": "Old recommendation.",
                    "open_loops": [],
                    "updated_at": 1773100800,
                },
                latest_interaction_context={"inbound_email": "Saturday is open now."},
            )

        self.assertEqual(refreshed["memory_notes"][0]["summary"], "Saturday is open now")
        self.assertEqual(refreshed["continuity_summary"]["last_recommendation"], "Move the long run to Saturday.")

    def test_orchestration_uses_provided_routing_decision(self):
        with mock.patch("skills.memory.refresh.runner.run_memory_router") as run_router, mock.patch(
            "skills.memory.refresh.runner.run_short_term_memory_refresh",
            return_value={
                "continuity_summary": {
                    "summary": "Travel week only.",
                    "last_recommendation": "Use the hotel treadmill.",
                    "open_loops": [],
                    "updated_at": 1773273600,
                }
            },
        ):
            refreshed = run_memory_refresh(
                prior_memory_notes=[],
                prior_continuity_summary={
                    "summary": "Existing continuity.",
                    "last_recommendation": "Existing recommendation.",
                    "open_loops": [],
                    "updated_at": 1773100800,
                },
                latest_interaction_context={"coach_reply": "Use the hotel treadmill."},
                routing_decision={"route": "short_term"},
            )

        self.assertEqual(refreshed["continuity_summary"]["summary"], "Travel week only.")
        run_router.assert_not_called()


if __name__ == "__main__":
    unittest.main()
