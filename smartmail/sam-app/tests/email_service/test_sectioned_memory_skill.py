"""Tests for sectioned memory skill (validator + reversal helper)."""

from __future__ import annotations

import unittest

from sectioned_memory_contract import empty_sectioned_memory
from skills.memory.sectioned.errors import SectionedMemoryRefreshError
from skills.memory.sectioned.runner import _candidates_address_reversal_sectioned
from skills.memory.sectioned.validator import validate_sectioned_candidate_response


def _base_candidate(**kwargs: object) -> dict:
    c = {
        "action": "upsert",
        "target_id": None,
        "section": "goal",
        "subtype": "primary",
        "fact_key": "marathon",
        "summary": "Train",
        "supersedes_fact_keys": None,
        "evidence_source": "athlete_email",
        "evidence_strength": "explicit",
    }
    c.update(kwargs)
    return c


def _continuity() -> dict:
    return {
        "summary": "Ctx",
        "last_recommendation": "Rec",
        "open_loops": [],
    }


class TestSectionedValidator(unittest.TestCase):
    def test_valid_new_upsert(self) -> None:
        out = validate_sectioned_candidate_response(
            {
                "candidates": [_base_candidate()],
                "continuity": _continuity(),
            }
        )
        self.assertEqual(len(out["candidates"]), 1)
        self.assertEqual(out["candidates"][0]["section"], "goal")

    def test_invalid_section(self) -> None:
        with self.assertRaises(SectionedMemoryRefreshError):
            validate_sectioned_candidate_response(
                {
                    "candidates": [_base_candidate(section="nope")],
                    "continuity": _continuity(),
                }
            )

    def test_invalid_subtype(self) -> None:
        with self.assertRaises(SectionedMemoryRefreshError):
            validate_sectioned_candidate_response(
                {
                    "candidates": [_base_candidate(subtype="hard_blocker")],
                    "continuity": _continuity(),
                }
            )

    def test_update_ignores_echoed_section_and_fact_key(self) -> None:
        out = validate_sectioned_candidate_response(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "target_id": "x",
                        "section": "goal",
                        "subtype": "secondary",
                        "fact_key": "goal:ignored",
                        "summary": "Hi",
                        "supersedes_fact_keys": None,
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ],
                "continuity": _continuity(),
            }
        )
        self.assertEqual(out["candidates"][0]["target_id"], "x")
        self.assertEqual(out["candidates"][0]["summary"], "Hi")
        self.assertEqual(out["candidates"][0]["subtype"], "secondary")
        self.assertNotIn("section", out["candidates"][0])
        self.assertNotIn("fact_key", out["candidates"][0])

    def test_retire_requires_explicit(self) -> None:
        with self.assertRaises(SectionedMemoryRefreshError):
            validate_sectioned_candidate_response(
                {
                    "candidates": [
                        {
                            "action": "retire",
                            "target_id": "a",
                            "section": "goal",
                            "subtype": None,
                            "fact_key": None,
                            "summary": None,
                            "supersedes_fact_keys": None,
                            "evidence_source": "athlete_email",
                            "evidence_strength": "strong_inference",
                        }
                    ],
                    "continuity": _continuity(),
                }
            )

    def test_rule_engine_only_confirm(self) -> None:
        with self.assertRaises(SectionedMemoryRefreshError):
            validate_sectioned_candidate_response(
                {
                    "candidates": [
                        _base_candidate(evidence_source="rule_engine_state"),
                    ],
                    "continuity": _continuity(),
                }
            )

        ok = validate_sectioned_candidate_response(
            {
                "candidates": [
                    {
                        "action": "confirm",
                        "target_id": "mid",
                        "section": None,
                        "subtype": None,
                        "fact_key": None,
                        "summary": None,
                        "supersedes_fact_keys": None,
                        "evidence_source": "rule_engine_state",
                        "evidence_strength": "explicit",
                    }
                ],
                "continuity": _continuity(),
            }
        )
        self.assertEqual(ok["candidates"][0]["action"], "confirm")


class TestReversalSectioned(unittest.TestCase):
    def test_new_schedule_without_existing_conflict_needs_retry_signal(self) -> None:
        mem = empty_sectioned_memory()
        mem["schedule_anchors"]["active"].append(
            {
                "memory_id": "old",
                "section": "schedule_anchor",
                "subtype": "other",
                "fact_key": "schedule_anchor:old",
                "summary": "Old swim",
                "status": "active",
                "supersedes": [],
                "created_at": 1,
                "updated_at": 1,
                "last_confirmed_at": 1,
            }
        )
        candidates = [
            {
                "action": "upsert",
                "section": "schedule_anchor",
                "subtype": "hard_blocker",
                "fact_key": "new",
                "summary": "New",
            }
        ]
        self.assertFalse(_candidates_address_reversal_sectioned(candidates, mem))

    def test_retire_addresses_reversal(self) -> None:
        mem = empty_sectioned_memory()
        mem["schedule_anchors"]["active"].append(
            {
                "memory_id": "old",
                "section": "schedule_anchor",
                "subtype": "other",
                "fact_key": "schedule_anchor:old",
                "summary": "Old",
                "status": "active",
                "supersedes": [],
                "created_at": 1,
                "updated_at": 1,
                "last_confirmed_at": 1,
            }
        )
        candidates = [
            {"action": "retire", "target_id": "old", "section": "schedule_anchor"},
        ]
        self.assertTrue(_candidates_address_reversal_sectioned(candidates, mem))


if __name__ == "__main__":
    unittest.main()
