"""Unit tests for the AM2 athlete memory contract."""

from decimal import Decimal
import unittest

from athlete_memory_contract import (
    ALLOWED_FACT_TYPES,
    ALLOWED_MEMORY_NOTE_IMPORTANCE,
    ALLOWED_MEMORY_NOTE_STATUS,
    FACT_KEY_REFERENCE_EXAMPLES,
    MAX_MEMORY_NOTES,
    MAX_OPEN_LOOPS,
    AthleteMemoryContractError,
    ContinuitySummary,
    MemoryNote,
    filter_active_memory_notes,
    normalize_fact_key,
    validate_continuity_summary,
    validate_memory_note,
    validate_memory_note_list,
)


def _valid_note() -> MemoryNote:
    return MemoryNote(
        memory_note_id=2,
        fact_type="constraint",
        fact_key="weekday_before_7am_cutoff",
        summary="Can usually train only before 7am on weekdays",
        importance="medium",
        status="active",
        created_at=1772928000,
        updated_at=1773014400,
        last_confirmed_at=1773014400,
    )


def _valid_continuity_summary() -> ContinuitySummary:
    return ContinuitySummary(
        summary="Athlete is rebuilding after a week of missed training due to travel.",
        last_recommendation="Keep the week light and re-establish consistency.",
        open_loops=[
            "Check whether travel schedule is over",
            "Confirm energy levels by next check-in",
        ],
        updated_at=1773014400,
    )


class TestMemoryNoteValidation(unittest.TestCase):
    def test_valid_memory_note_passes(self):
        note = _valid_note()
        validate_memory_note(note)

    def test_round_trip_from_dict_passes(self):
        payload = _valid_note().to_dict()
        rebuilt = MemoryNote.from_dict(payload)
        self.assertEqual(rebuilt.to_dict(), payload)

    def test_memory_note_id_must_be_positive_int(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(**{**_valid_note().to_dict(), "memory_note_id": 0})
            )

    def test_fact_type_must_be_allowed_value(self):
        self.assertEqual(ALLOWED_FACT_TYPES, {"goal", "constraint", "schedule", "preference", "other"})
        for fact_type in ALLOWED_FACT_TYPES:
            note = MemoryNote(**{**_valid_note().to_dict(), "fact_type": fact_type})
            validate_memory_note(note)
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(**{**_valid_note().to_dict(), "fact_type": "injury"})
            )

    def test_fact_key_is_normalized_and_strips_type_prefix(self):
        note = MemoryNote(
            **{**_valid_note().to_dict(), "fact_key": "Constraint:Weekday Before 7am Cutoff"}
        )
        validate_memory_note(note)
        self.assertEqual(note.fact_key, "weekday_before_7am_cutoff")
        self.assertEqual(
            normalize_fact_key("schedule:Saturday Availability"),
            "saturday_availability",
        )

    def test_summary_must_be_non_empty(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(**{**_valid_note().to_dict(), "summary": "   "})
            )

    def test_importance_must_be_allowed_value(self):
        self.assertEqual(ALLOWED_MEMORY_NOTE_IMPORTANCE, {"high", "medium", "low"})
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(**{**_valid_note().to_dict(), "importance": "critical"})
            )

    def test_status_must_be_allowed_value(self):
        self.assertEqual(ALLOWED_MEMORY_NOTE_STATUS, {"active", "inactive"})
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(**{**_valid_note().to_dict(), "status": "archived"})
            )

    def test_timestamps_must_be_positive_and_ordered(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(**{**_valid_note().to_dict(), "created_at": "03/08/2026"})
            )
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note(
                MemoryNote(
                    **{
                        **_valid_note().to_dict(),
                        "created_at": 1773014400,
                        "updated_at": 1772928000,
                    }
                )
            )

    def test_decimal_timestamps_from_dynamodb_are_accepted(self):
        payload = {
            **_valid_note().to_dict(),
            "created_at": Decimal("1772928000"),
            "updated_at": Decimal("1773014400"),
            "last_confirmed_at": Decimal("1773014400"),
        }
        rebuilt = MemoryNote.from_dict(payload)
        self.assertEqual(rebuilt.created_at, 1772928000)
        self.assertEqual(rebuilt.updated_at, 1773014400)
        self.assertEqual(rebuilt.last_confirmed_at, 1773014400)

    def test_decimal_memory_note_id_from_dynamodb_is_accepted(self):
        payload = {
            **_valid_note().to_dict(),
            "memory_note_id": Decimal("2"),
        }
        rebuilt = MemoryNote.from_dict(payload)
        self.assertEqual(rebuilt.memory_note_id, 2)

    def test_fractional_decimal_memory_note_id_is_rejected(self):
        payload = {
            **_valid_note().to_dict(),
            "memory_note_id": Decimal("2.5"),
        }
        with self.assertRaises(AthleteMemoryContractError):
            MemoryNote.from_dict(payload)

    def test_from_dict_rejects_missing_required_fields(self):
        payload = _valid_note().to_dict()
        del payload["status"]
        with self.assertRaises(AthleteMemoryContractError):
            MemoryNote.from_dict(payload)

    def test_from_dict_ignores_unknown_fields(self):
        payload = _valid_note().to_dict()
        payload["unexpected"] = "value"
        rebuilt = MemoryNote.from_dict(payload)
        self.assertEqual(rebuilt.to_dict(), _valid_note().to_dict())

    def test_memory_note_list_rejects_duplicate_ids(self):
        notes = [_valid_note().to_dict(), {**_valid_note().to_dict(), "summary": "other"}]
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note_list(notes)

    def test_memory_note_list_rejects_duplicate_ids_after_decimal_normalization(self):
        notes = [
            {**_valid_note().to_dict(), "memory_note_id": Decimal("2")},
            {**_valid_note().to_dict(), "memory_note_id": 2, "summary": "other"},
        ]
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note_list(notes)

    def test_memory_note_list_rejects_duplicate_active_fact_keys(self):
        notes = [
            _valid_note().to_dict(),
            {
                **_valid_note().to_dict(),
                "memory_note_id": 3,
                "summary": "Updated wording",
            },
        ]
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note_list(notes)

    def test_memory_note_list_allows_inactive_duplicate_fact_key(self):
        notes = [
            _valid_note().to_dict(),
            {
                **_valid_note().to_dict(),
                "memory_note_id": 3,
                "status": "inactive",
                "summary": "Old wording",
            },
        ]
        normalized = validate_memory_note_list(notes)
        self.assertEqual(len(normalized), 2)
        self.assertEqual(len(filter_active_memory_notes(normalized)), 1)

    def test_memory_note_list_rejects_more_than_max_active_notes(self):
        notes = [
            {
                "memory_note_id": idx,
                "fact_type": "schedule",
                "fact_key": f"slot_{idx}",
                "summary": f"note {idx}",
                "importance": "medium",
                "status": "active",
                "created_at": 1772928000,
                "updated_at": 1772928000,
                "last_confirmed_at": 1772928000,
            }
            for idx in range(1, MAX_MEMORY_NOTES + 2)
        ]
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note_list(notes)

    def test_memory_note_list_hard_cutover_rejects_am1_shape(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_note_list(
                [
                    {
                        "memory_note_id": 1,
                        "category": "schedule",
                        "summary": "old shape",
                        "importance": "medium",
                        "last_confirmed_at": 1772928000,
                    }
                ]
            )

    def test_reference_examples_have_expected_shape(self):
        self.assertEqual(len(FACT_KEY_REFERENCE_EXAMPLES), 5)
        for example in FACT_KEY_REFERENCE_EXAMPLES:
            self.assertIn("canonical_fact_key", example)
            self.assertIn("fact_type", example)


class TestContinuitySummaryValidation(unittest.TestCase):
    def test_valid_continuity_summary_passes(self):
        summary = _valid_continuity_summary()
        validate_continuity_summary(summary)

    def test_round_trip_from_dict_passes(self):
        payload = _valid_continuity_summary().to_dict()
        rebuilt = ContinuitySummary.from_dict(payload)
        self.assertEqual(rebuilt.to_dict(), payload)

    def test_summary_must_be_non_empty(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_continuity_summary(
                ContinuitySummary(**{**_valid_continuity_summary().to_dict(), "summary": " "})
            )

    def test_last_recommendation_must_be_non_empty(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_continuity_summary(
                ContinuitySummary(
                    **{
                        **_valid_continuity_summary().to_dict(),
                        "last_recommendation": " ",
                    }
                )
            )

    def test_open_loops_must_be_list_of_non_empty_strings(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_continuity_summary(
                ContinuitySummary(
                    **{**_valid_continuity_summary().to_dict(), "open_loops": "not-a-list"}
                )
            )
        with self.assertRaises(AthleteMemoryContractError):
            validate_continuity_summary(
                ContinuitySummary(
                    **{
                        **_valid_continuity_summary().to_dict(),
                        "open_loops": ["valid", " "],
                    }
                )
            )

    def test_updated_at_must_be_positive_unix_timestamp(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_continuity_summary(
                ContinuitySummary(
                    **{**_valid_continuity_summary().to_dict(), "updated_at": "yesterday"}
                )
            )

    def test_continuity_summary_accepts_decimal_updated_at(self):
        payload = {
            **_valid_continuity_summary().to_dict(),
            "updated_at": Decimal("1773014400"),
        }
        rebuilt = ContinuitySummary.from_dict(payload)
        self.assertEqual(rebuilt.updated_at, 1773014400)

    def test_from_dict_rejects_missing_required_fields(self):
        payload = _valid_continuity_summary().to_dict()
        del payload["open_loops"]
        with self.assertRaises(AthleteMemoryContractError):
            ContinuitySummary.from_dict(payload)

    def test_from_dict_ignores_unknown_fields(self):
        payload = _valid_continuity_summary().to_dict()
        payload["unexpected"] = "value"
        rebuilt = ContinuitySummary.from_dict(payload)
        self.assertEqual(rebuilt.to_dict(), _valid_continuity_summary().to_dict())

    def test_continuity_summary_rejects_too_many_open_loops(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_continuity_summary(
                ContinuitySummary(
                    **{
                        **_valid_continuity_summary().to_dict(),
                        "open_loops": [str(idx) for idx in range(1, MAX_OPEN_LOOPS + 2)],
                    }
                )
            )


if __name__ == "__main__":
    unittest.main()
