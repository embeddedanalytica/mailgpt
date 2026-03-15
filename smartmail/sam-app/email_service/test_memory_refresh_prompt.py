"""Unit tests for the split memory refresh prompt contracts."""

import json
import unittest

from athlete_memory_contract import ContinuitySummary, MemoryNote
from skills.memory import (
    MemoryRefreshEligibilityError,
    MemoryRefreshPromptError,
    build_long_term_memory_user_payload,
    build_memory_router_user_payload,
    build_short_term_memory_user_payload,
)
from skills.memory.long_term.prompt import SYSTEM_PROMPT as LONG_TERM_PROMPT
from skills.memory.long_term.schema import JSON_SCHEMA as LONG_TERM_SCHEMA
from skills.memory.router.prompt import SYSTEM_PROMPT as ROUTER_PROMPT
from skills.memory.router.schema import JSON_SCHEMA as ROUTER_SCHEMA
from skills.memory.short_term.prompt import SYSTEM_PROMPT as SHORT_TERM_PROMPT
from skills.memory.short_term.schema import JSON_SCHEMA as SHORT_TERM_SCHEMA


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
        "updated_at": 1773100800,
        "last_confirmed_at": 1773100800,
    }


class TestMemoryRouterPrompt(unittest.TestCase):
    def test_router_prompt_includes_route_contract(self):
        prompt = ROUTER_PROMPT
        self.assertIn("response schema", prompt.lower())
        self.assertIn("objective:", prompt.lower())
        self.assertIn("long_term", prompt)
        self.assertIn("short_term", prompt)
        self.assertIn("both", prompt)
        self.assertIn("neither", prompt)
        self.assertIn("use only the provided prior state", prompt.lower())
        self.assertIn("do not assume hidden history", prompt.lower())
        self.assertIn("durable truths should survive routine churn", prompt.lower())
        self.assertIn("temporary disruption", prompt.lower())

    def test_router_schema_defines_strict_output_shape(self):
        self.assertFalse(ROUTER_SCHEMA["additionalProperties"])
        self.assertEqual(ROUTER_SCHEMA["required"], ["route"])
        self.assertEqual(
            set(ROUTER_SCHEMA["properties"]["route"]["enum"]),
            {"long_term", "short_term", "both", "neither"},
        )

    def test_router_payload_includes_prior_state_and_latest_context(self):
        payload = build_memory_router_user_payload(
            prior_memory_notes=[_note(2)],
            prior_continuity_summary={
                "summary": "Athlete is rebuilding after travel.",
                "last_recommendation": "Keep the week light.",
                "open_loops": ["Check energy next week"],
                "updated_at": 1773100800,
            },
            latest_interaction_context={"interaction_type": "durable_change"},
        )
        decoded = json.loads(payload)
        self.assertEqual(decoded["prior_memory_notes"][0]["fact_key"], "masters_session_slot")
        self.assertEqual(decoded["prior_memory_notes"][0]["last_confirmed_at_readable"], "2026-03-10")
        self.assertEqual(decoded["prior_continuity_summary"]["updated_at_readable"], "2026-03-10")
        self.assertEqual(decoded["latest_interaction_context"]["interaction_type"], "durable_change")

    def test_router_payload_filters_inactive_notes(self):
        payload = build_memory_router_user_payload(
            prior_memory_notes=[
                _note(1, fact_key="saturday_availability", summary="Saturday open"),
                _note(2, fact_key="saturday_availability", summary="Saturday unavailable", status="inactive"),
            ],
            prior_continuity_summary=None,
            latest_interaction_context={"interaction_type": "durable_change"},
        )
        decoded = json.loads(payload)
        self.assertEqual(len(decoded["prior_memory_notes"]), 1)

    def test_router_payload_requires_valid_contracts(self):
        with self.assertRaises(MemoryRefreshEligibilityError):
            build_memory_router_user_payload(
                prior_memory_notes="not-a-list",
                prior_continuity_summary=None,
                latest_interaction_context={},
            )


class TestLongTermPrompt(unittest.TestCase):
    def test_long_term_prompt_stays_candidate_only(self):
        prompt = LONG_TERM_PROMPT.lower()
        self.assertIn("objective:", prompt)
        self.assertIn("candidate durable-memory operations", prompt)
        self.assertIn("do not rewrite the full durable-memory state", prompt)
        self.assertIn("fact_key is only an identity hint", prompt)
        self.assertIn("retire requires explicit athlete-originated evidence", prompt)
        self.assertIn("use memory_note_id to reference an existing prior durable note", prompt)
        self.assertIn("set memory_note_id to 0 for a brand-new fact", prompt)
        self.assertNotIn("next_memory_note_id", prompt)

    def test_long_term_prompt_includes_worthiness_and_consolidation_rules(self):
        prompt = LONG_TERM_PROMPT.lower()
        self.assertIn("prefer retire on the old note", prompt)
        self.assertIn("use memory_note_id", prompt)
        self.assertIn("merge_into", prompt)
        self.assertIn("freeform rewriting", prompt)
        self.assertIn("temporary disruption", prompt)
        self.assertIn("durable truths should survive routine churn", prompt)
        self.assertIn("target the prior note by memory_note_id", prompt)

    def test_long_term_schema_defines_candidates_and_optional_merges(self):
        self.assertFalse(LONG_TERM_SCHEMA["additionalProperties"])
        self.assertEqual(LONG_TERM_SCHEMA["required"], ["candidates", "consolidation_ops"])
        self.assertIn("consolidation_ops", LONG_TERM_SCHEMA["properties"])
        self.assertEqual(
            LONG_TERM_SCHEMA["properties"]["candidates"]["items"]["properties"]["memory_note_id"]["minimum"],
            0,
        )

    def test_long_term_payload_uses_active_notes_only(self):
        payload = build_long_term_memory_user_payload(
            prior_memory_notes=[
                _note(2),
                _note(4, fact_key="saturday_availability", summary="Saturday unavailable", status="inactive"),
            ],
            latest_interaction_context={"inbound_email": "Saturday is open now."},
        )
        decoded = json.loads(payload)
        self.assertEqual(len(decoded["prior_memory_notes"]), 1)
        self.assertEqual(decoded["prior_memory_notes"][0]["updated_at_readable"], "2026-03-10")

    def test_long_term_payload_requires_valid_notes(self):
        with self.assertRaises(MemoryRefreshPromptError):
            build_long_term_memory_user_payload(
                prior_memory_notes="not-a-list",
                latest_interaction_context={},
            )


class TestShortTermPrompt(unittest.TestCase):
    def test_short_term_prompt_stays_continuity_only(self):
        prompt = SHORT_TERM_PROMPT
        self.assertIn("Objective:", prompt)
        self.assertIn("continuity_summary", prompt)
        self.assertIn("next 1 to 2 exchanges", prompt)
        self.assertIn("routine status messages", prompt.lower())
        self.assertIn("not a transcript and not long-term memory", prompt.lower())
        self.assertNotIn("next_memory_note_id", prompt)

    def test_short_term_schema_defines_continuity_only(self):
        self.assertFalse(SHORT_TERM_SCHEMA["additionalProperties"])
        self.assertEqual(SHORT_TERM_SCHEMA["required"], ["continuity_summary"])
        self.assertFalse(
            SHORT_TERM_SCHEMA["properties"]["continuity_summary"]["additionalProperties"]
        )

    def test_short_term_payload_includes_latest_context(self):
        payload = build_short_term_memory_user_payload(
            prior_continuity_summary={
                "summary": "Athlete is rebuilding after travel.",
                "last_recommendation": "Keep the week light.",
                "open_loops": ["Check energy next week"],
                "updated_at": 1773100800,
            },
            latest_interaction_context={"coach_reply": "Add one moderate session."},
        )
        decoded = json.loads(payload)
        self.assertEqual(decoded["prior_continuity_summary"]["updated_at_readable"], "2026-03-10")
        self.assertEqual(decoded["latest_interaction_context"]["coach_reply"], "Add one moderate session.")

    def test_short_term_payload_requires_valid_continuity(self):
        with self.assertRaises(MemoryRefreshPromptError):
            build_short_term_memory_user_payload(
                prior_continuity_summary="not-a-dict",
                latest_interaction_context={},
            )


class TestMemoryRefreshRepresentativeOutputs(unittest.TestCase):
    def test_representative_goal_note_output_validates(self):
        note = MemoryNote.from_dict(
            _note(
                1,
                fact_type="goal",
                fact_key="marathon_goal",
                summary="Training for a fall marathon",
            )
        )
        self.assertEqual(note.fact_type, "goal")

    def test_representative_preference_note_output_and_continuity_validate(self):
        note = MemoryNote.from_dict(
            _note(
                4,
                fact_type="preference",
                fact_key="reply_format",
                summary="Prefers concise bullets and explicit priorities",
                importance="low",
            )
        )
        continuity = ContinuitySummary.from_dict(
            {
                "summary": "Athlete is re-establishing routine after a disrupted travel block.",
                "last_recommendation": "Keep one moderate session and prioritize consistency.",
                "open_loops": [
                    "Confirm travel is finished",
                    "Check calf response after the moderate session",
                ],
                "updated_at": 1773187200,
            }
        )
        self.assertEqual(note.fact_type, "preference")
        self.assertEqual(len(continuity.open_loops), 2)


if __name__ == "__main__":
    unittest.main()
