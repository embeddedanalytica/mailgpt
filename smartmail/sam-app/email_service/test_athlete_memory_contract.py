"""Unit tests for the athlete memory contract (AM3 backbone/context)."""

from decimal import Decimal
import unittest

from athlete_memory_contract import (
    BACKBONE_SLOT_KEYS,
    BackboneSlot,
    BackboneSlots,
    ContextNote,
    MAX_CONTEXT_NOTES,
    MAX_OPEN_LOOPS,
    AthleteMemoryContractError,
    ContinuitySummary,
    validate_backbone_slots,
    validate_context_note_list,
    validate_continuity_summary,
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


class TestBackboneSlotValidation(unittest.TestCase):
    def test_populated_slot_round_trips(self):
        slot = BackboneSlot(summary="Run a half marathon on 2026-05-17", updated_at=1773014400)
        rebuilt = BackboneSlot.from_dict(slot.to_dict(), slot_name="primary_goal")
        self.assertEqual(rebuilt.to_dict(), slot.to_dict())

    def test_null_slot_round_trips(self):
        slot = BackboneSlot(summary=None, updated_at=None)
        rebuilt = BackboneSlot.from_dict(slot.to_dict(), slot_name="primary_goal")
        self.assertIsNone(rebuilt.summary)
        self.assertIsNone(rebuilt.updated_at)

    def test_none_payload_produces_null_slot(self):
        slot = BackboneSlot.from_dict(None, slot_name="primary_goal")
        self.assertIsNone(slot.summary)

    def test_rejects_summary_without_updated_at(self):
        with self.assertRaises(AthleteMemoryContractError):
            BackboneSlot.from_dict(
                {"summary": "half marathon", "updated_at": None},
                slot_name="primary_goal",
            )

    def test_rejects_updated_at_without_summary(self):
        with self.assertRaises(AthleteMemoryContractError):
            BackboneSlot.from_dict(
                {"summary": None, "updated_at": 1773014400},
                slot_name="primary_goal",
            )

    def test_rejects_empty_summary(self):
        with self.assertRaises(AthleteMemoryContractError):
            BackboneSlot.from_dict(
                {"summary": "   ", "updated_at": 1773014400},
                slot_name="primary_goal",
            )

    def test_accepts_decimal_updated_at(self):
        slot = BackboneSlot.from_dict(
            {"summary": "goal", "updated_at": Decimal("1773014400")},
            slot_name="primary_goal",
        )
        self.assertEqual(slot.updated_at, 1773014400)

    def test_rejects_non_dict_payload(self):
        with self.assertRaises(AthleteMemoryContractError):
            BackboneSlot.from_dict("not a dict", slot_name="primary_goal")


class TestBackboneSlotsValidation(unittest.TestCase):
    def _populated_backbone(self) -> dict:
        return {
            "primary_goal": {"summary": "Half marathon in May", "updated_at": 1773014400},
            "weekly_structure": {"summary": "4 days/week, Mon/Wed/Fri/Sun", "updated_at": 1773014400},
            "hard_constraints": {"summary": "Mild Achilles tightness, busy mornings Tue", "updated_at": 1773014400},
            "training_preferences": {"summary": "Prefers structured plans", "updated_at": 1773014400},
        }

    def test_populated_backbone_round_trips(self):
        payload = self._populated_backbone()
        backbone = BackboneSlots.from_dict(payload)
        self.assertEqual(backbone.to_dict(), payload)

    def test_empty_backbone_has_all_null_slots(self):
        backbone = BackboneSlots.empty()
        for key in BACKBONE_SLOT_KEYS:
            slot = backbone.to_dict()[key]
            self.assertIsNone(slot["summary"])
            self.assertIsNone(slot["updated_at"])

    def test_partial_backbone_allows_null_slots(self):
        payload = self._populated_backbone()
        payload["training_preferences"] = {"summary": None, "updated_at": None}
        backbone = BackboneSlots.from_dict(payload)
        self.assertIsNone(backbone.training_preferences.summary)

    def test_missing_slot_key_treated_as_null(self):
        payload = self._populated_backbone()
        del payload["training_preferences"]
        backbone = BackboneSlots.from_dict(payload)
        self.assertIsNone(backbone.training_preferences.summary)

    def test_rejects_non_dict(self):
        with self.assertRaises(AthleteMemoryContractError):
            BackboneSlots.from_dict("not a dict")

    def test_backbone_slot_keys_constant(self):
        self.assertEqual(
            BACKBONE_SLOT_KEYS,
            ["primary_goal", "weekly_structure", "hard_constraints", "training_preferences"],
        )


class TestContextNoteValidation(unittest.TestCase):
    def _valid_context_note(self) -> dict:
        return {
            "label": "power meter",
            "summary": "Has a power meter on the road bike",
            "updated_at": 1773014400,
        }

    def test_valid_context_note_round_trips(self):
        payload = self._valid_context_note()
        note = ContextNote.from_dict(payload, index=0)
        self.assertEqual(note.to_dict(), payload)

    def test_rejects_empty_label(self):
        payload = {**self._valid_context_note(), "label": "  "}
        with self.assertRaises(AthleteMemoryContractError):
            ContextNote.from_dict(payload, index=0)

    def test_rejects_empty_summary(self):
        payload = {**self._valid_context_note(), "summary": ""}
        with self.assertRaises(AthleteMemoryContractError):
            ContextNote.from_dict(payload, index=0)

    def test_rejects_non_dict(self):
        with self.assertRaises(AthleteMemoryContractError):
            ContextNote.from_dict("not a dict", index=0)

    def test_accepts_decimal_updated_at(self):
        payload = {**self._valid_context_note(), "updated_at": Decimal("1773014400")}
        note = ContextNote.from_dict(payload, index=0)
        self.assertEqual(note.updated_at, 1773014400)


class TestContextNoteListValidation(unittest.TestCase):
    def _note(self, label: str, summary: str = "details") -> dict:
        return {"label": label, "summary": summary, "updated_at": 1773014400}

    def test_valid_list_passes(self):
        notes = [self._note("power meter"), self._note("Sunday group run")]
        result = validate_context_note_list(notes)
        self.assertEqual(len(result), 2)

    def test_empty_list_passes(self):
        result = validate_context_note_list([])
        self.assertEqual(result, [])

    def test_max_context_notes_is_4(self):
        self.assertEqual(MAX_CONTEXT_NOTES, 4)
        notes = [self._note(f"fact_{i}") for i in range(4)]
        result = validate_context_note_list(notes)
        self.assertEqual(len(result), 4)

    def test_rejects_more_than_max(self):
        notes = [self._note(f"fact_{i}") for i in range(MAX_CONTEXT_NOTES + 1)]
        with self.assertRaises(AthleteMemoryContractError):
            validate_context_note_list(notes)

    def test_rejects_duplicate_labels(self):
        notes = [self._note("power meter"), self._note("Power Meter")]
        with self.assertRaises(AthleteMemoryContractError):
            validate_context_note_list(notes)

    def test_rejects_non_list(self):
        with self.assertRaises(AthleteMemoryContractError):
            validate_context_note_list("not a list")


if __name__ == "__main__":
    unittest.main()
