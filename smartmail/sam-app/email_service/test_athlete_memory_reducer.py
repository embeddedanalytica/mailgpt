"""Unit tests for deterministic long-term durable-memory application."""

import unittest

from athlete_memory_reducer import (
    AthleteMemoryReducerError,
    derive_canonical_fact_key,
    reduce_long_term_memory,
    validate_long_term_candidate_payload,
)


def _note(
    note_id: int,
    *,
    fact_type: str,
    fact_key: str,
    summary: str,
    importance: str = "medium",
    status: str = "active",
    created_at: int = 1772928000,
    updated_at: int = 1773014400,
    last_confirmed_at: int = 1773014400,
) -> dict:
    return {
        "memory_note_id": note_id,
        "fact_type": fact_type,
        "fact_key": fact_key,
        "summary": summary,
        "importance": importance,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


class TestFactKeyDerivation(unittest.TestCase):
    def test_derive_canonical_fact_key_still_supports_manual_upserts(self):
        self.assertEqual(
            derive_canonical_fact_key(
                fact_type="constraint",
                proposed_key="weekday cutoff",
                summary="Weekday sessions need to finish before 7am.",
            ),
            "weekday_before_7am_cutoff",
        )


class TestLongTermPayloadValidation(unittest.TestCase):
    def test_upsert_requires_explicit_structured_fields(self):
        validated = validate_long_term_candidate_payload(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "memory_note_id": 0,
                        "fact_type": "constraint",
                        "fact_key": "weekday_cutoff",
                        "summary": "Weekday sessions need to finish before 7am.",
                        "importance": "high",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ],
                "consolidation_ops": [],
            }
        )
        self.assertIsNone(validated["candidates"][0]["memory_note_id"])
        self.assertEqual(validated["candidates"][0]["fact_key"], "weekday_cutoff")

    def test_retire_requires_memory_note_id_and_reason(self):
        with self.assertRaises(AthleteMemoryReducerError):
            validate_long_term_candidate_payload(
                {
                    "candidates": [
                        {
                            "action": "retire",
                            "memory_note_id": 1,
                            "evidence_source": "athlete_email",
                            "evidence_strength": "explicit",
                        }
                    ],
                    "consolidation_ops": [],
                }
            )

    def test_merge_into_uses_note_ids_not_fact_keys(self):
        validated = validate_long_term_candidate_payload(
            {
                "candidates": [],
                "consolidation_ops": [
                    {
                        "action": "merge_into",
                        "source_memory_note_id": 2,
                        "target_memory_note_id": 1,
                        "summary": "Unified summary",
                    }
                ],
            }
        )
        self.assertEqual(validated["consolidation_ops"][0]["source_memory_note_id"], 2)


class TestReducer(unittest.TestCase):
    def test_upsert_new_note_creates_record(self):
        reduced = reduce_long_term_memory(
            stored_memory_notes=[],
            candidate_payload={
                "candidates": [
                    {
                        "action": "upsert",
                        "memory_note_id": 0,
                        "fact_type": "constraint",
                        "fact_key": "weekday_cutoff",
                        "summary": "Weekday sessions need to finish before 7am.",
                        "importance": "high",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ],
                "consolidation_ops": [],
            },
            now_epoch=1773273600,
        )
        self.assertEqual(len(reduced), 1)
        self.assertEqual(reduced[0]["memory_note_id"], 1)
        self.assertEqual(reduced[0]["fact_key"], "weekday_cutoff")

    def test_upsert_existing_note_updates_by_memory_note_id(self):
        reduced = reduce_long_term_memory(
            stored_memory_notes=[
                _note(
                    3,
                    fact_type="constraint",
                    fact_key="weekday_cutoff",
                    summary="Before 7am.",
                    importance="high",
                )
            ],
            candidate_payload={
                "candidates": [
                    {
                        "action": "upsert",
                        "memory_note_id": 3,
                        "fact_type": "constraint",
                        "fact_key": "weekday_cutoff",
                        "summary": "Weekday sessions need to finish before 6:30am.",
                        "importance": "high",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ],
                "consolidation_ops": [],
            },
            now_epoch=1773273600,
        )
        self.assertEqual(len(reduced), 1)
        self.assertEqual(reduced[0]["memory_note_id"], 3)
        self.assertEqual(reduced[0]["summary"], "Weekday sessions need to finish before 6:30am.")

    def test_confirm_updates_existing_note_by_memory_note_id(self):
        reduced = reduce_long_term_memory(
            stored_memory_notes=[
                _note(
                    1,
                    fact_type="goal",
                    fact_key="fall_marathon",
                    summary="Training for a fall marathon",
                    importance="high",
                )
            ],
            candidate_payload={
                "candidates": [
                    {
                        "action": "confirm",
                        "memory_note_id": 1,
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ],
                "consolidation_ops": [],
            },
            now_epoch=1773273600,
        )
        self.assertEqual(reduced[0]["last_confirmed_at"], 1773273600)

    def test_retire_inactivates_existing_note_by_memory_note_id(self):
        reduced = reduce_long_term_memory(
            stored_memory_notes=[
                _note(
                    2,
                    fact_type="constraint",
                    fact_key="saturday_availability",
                    summary="Saturdays are unavailable.",
                    importance="high",
                )
            ],
            candidate_payload={
                "candidates": [
                    {
                        "action": "retire",
                        "memory_note_id": 2,
                        "reason": "Athlete explicitly said Saturdays are open again.",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ],
                "consolidation_ops": [],
            },
            now_epoch=1773273600,
        )
        self.assertEqual(reduced[0]["status"], "inactive")

    def test_conflicting_actions_for_same_note_are_dropped(self):
        reduced = reduce_long_term_memory(
            stored_memory_notes=[
                _note(
                    1,
                    fact_type="schedule",
                    fact_key="masters_session_slot",
                    summary="Masters swim every Tuesday night",
                    importance="high",
                )
            ],
            candidate_payload={
                "candidates": [
                    {
                        "action": "confirm",
                        "memory_note_id": 1,
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    },
                    {
                        "action": "retire",
                        "memory_note_id": 1,
                        "reason": "Conflicting test payload.",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    },
                ],
                "consolidation_ops": [],
            },
            now_epoch=1773273600,
        )
        self.assertEqual(reduced[0]["status"], "active")
        self.assertEqual(reduced[0]["summary"], "Masters swim every Tuesday night")

    def test_merge_into_updates_target_and_inactivates_source(self):
        reduced = reduce_long_term_memory(
            stored_memory_notes=[
                _note(
                    1,
                    fact_type="schedule",
                    fact_key="masters_session_slot",
                    summary="Masters swim every Tuesday night",
                    importance="high",
                ),
                _note(
                    2,
                    fact_type="schedule",
                    fact_key="bike_windows",
                    summary="Bike fits on Thursday and Sunday",
                ),
            ],
            candidate_payload={
                "candidates": [],
                "consolidation_ops": [
                    {
                        "action": "merge_into",
                        "source_memory_note_id": 2,
                        "target_memory_note_id": 1,
                        "summary": "Week is anchored by masters swim and the main bike windows.",
                    }
                ],
            },
            now_epoch=1773273600,
        )
        target = next(note for note in reduced if note["memory_note_id"] == 1)
        source = next(note for note in reduced if note["memory_note_id"] == 2)
        self.assertEqual(target["summary"], "Week is anchored by masters swim and the main bike windows.")
        self.assertEqual(source["status"], "inactive")

    def test_invalid_payload_raises(self):
        with self.assertRaises(AthleteMemoryReducerError):
            reduce_long_term_memory(
                stored_memory_notes=[],
                candidate_payload={"memory_notes": []},
            )


if __name__ == "__main__":
    unittest.main()
