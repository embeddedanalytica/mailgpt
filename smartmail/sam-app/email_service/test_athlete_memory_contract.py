"""Unit tests for the athlete memory contract (AM2 durable facts)."""

from decimal import Decimal
import unittest

from athlete_memory_contract import (
    VALID_FACT_TYPES,
    VALID_IMPORTANCE_LEVELS,
    HIGH_IMPORTANCE_TYPES,
    MAX_ACTIVE_FACTS,
    MAX_OPEN_LOOPS,
    AthleteMemoryContractError,
    ContinuitySummary,
    DurableFact,
    normalize_fact_key,
    validate_continuity_summary,
    validate_memory_notes,
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


def _valid_fact_dict(
    *,
    memory_note_id: str = "fact-001",
    fact_type: str = "goal",
    fact_key: str = "goal:half-marathon",
    summary: str = "Run a half marathon in May",
    importance: str = "high",
    created_at: int = 1773014400,
    updated_at: int = 1773014400,
    last_confirmed_at: int = 1773014400,
) -> dict:
    return {
        "memory_note_id": memory_note_id,
        "fact_type": fact_type,
        "fact_key": fact_key,
        "summary": summary,
        "importance": importance,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


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


class TestNormalizeFactKey(unittest.TestCase):
    def test_basic_normalization(self):
        self.assertEqual(normalize_fact_key("goal", "Half Marathon"), "goal:half-marathon")

    def test_collapses_whitespace_to_hyphens(self):
        self.assertEqual(
            normalize_fact_key("schedule", "  Monday  morning  runs  "),
            "schedule:monday-morning-runs",
        )

    def test_removes_special_characters(self):
        self.assertEqual(
            normalize_fact_key("constraint", "can't run before 6am!"),
            "constraint:cant-run-before-6am",
        )

    def test_truncates_to_64_chars(self):
        long_key = "a" * 100
        result = normalize_fact_key("other", long_key)
        slug = result.split(":", 1)[1]
        self.assertLessEqual(len(slug), 64)

    def test_rejects_invalid_fact_type(self):
        with self.assertRaises(AthleteMemoryContractError):
            normalize_fact_key("invalid_type", "some key")

    def test_rejects_empty_result(self):
        with self.assertRaises(AthleteMemoryContractError):
            normalize_fact_key("goal", "!!!???")


class TestDurableFact(unittest.TestCase):
    def test_round_trip(self):
        payload = _valid_fact_dict()
        fact = DurableFact.from_dict(payload)
        self.assertEqual(fact.to_dict(), payload)

    def test_rejects_non_dict(self):
        with self.assertRaises(AthleteMemoryContractError):
            DurableFact.from_dict("not a dict")

    def test_rejects_invalid_fact_type(self):
        payload = _valid_fact_dict(fact_type="invalid")
        with self.assertRaises(AthleteMemoryContractError):
            DurableFact.from_dict(payload)

    def test_rejects_invalid_importance(self):
        payload = _valid_fact_dict(importance="critical")
        with self.assertRaises(AthleteMemoryContractError):
            DurableFact.from_dict(payload)

    def test_rejects_empty_summary(self):
        payload = _valid_fact_dict(summary="  ")
        with self.assertRaises(AthleteMemoryContractError):
            DurableFact.from_dict(payload)

    def test_rejects_empty_memory_note_id(self):
        payload = _valid_fact_dict(memory_note_id="  ")
        with self.assertRaises(AthleteMemoryContractError):
            DurableFact.from_dict(payload)

    def test_accepts_decimal_timestamps(self):
        payload = _valid_fact_dict()
        payload["created_at"] = Decimal("1773014400")
        payload["updated_at"] = Decimal("1773014400")
        payload["last_confirmed_at"] = Decimal("1773014400")
        fact = DurableFact.from_dict(payload)
        self.assertEqual(fact.created_at, 1773014400)


class TestValidateMemoryNotes(unittest.TestCase):
    def test_valid_list_passes(self):
        notes = [
            _valid_fact_dict(memory_note_id="f1", fact_key="goal:marathon"),
            _valid_fact_dict(memory_note_id="f2", fact_type="schedule", fact_key="schedule:weekly", summary="4 days/week"),
        ]
        result = validate_memory_notes(notes)
        self.assertEqual(len(result), 2)

    def test_empty_list_passes(self):
        result = validate_memory_notes([])
        self.assertEqual(result, [])

    def test_rejects_non_list(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_notes("not a list")

    def test_rejects_duplicate_memory_note_id(self):
        notes = [
            _valid_fact_dict(memory_note_id="dup", fact_key="goal:a"),
            _valid_fact_dict(memory_note_id="dup", fact_key="goal:b"),
        ]
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_notes(notes)

    def test_rejects_duplicate_fact_key(self):
        notes = [
            _valid_fact_dict(memory_note_id="f1", fact_key="goal:marathon"),
            _valid_fact_dict(memory_note_id="f2", fact_key="goal:marathon"),
        ]
        with self.assertRaises(AthleteMemoryContractError):
            validate_memory_notes(notes)

    def test_constants(self):
        self.assertEqual(VALID_FACT_TYPES, {"goal", "constraint", "schedule", "preference", "other"})
        self.assertEqual(VALID_IMPORTANCE_LEVELS, {"high", "medium"})
        self.assertEqual(HIGH_IMPORTANCE_TYPES, {"goal", "constraint"})
        self.assertEqual(MAX_ACTIVE_FACTS, 7)


if __name__ == "__main__":
    unittest.main()
