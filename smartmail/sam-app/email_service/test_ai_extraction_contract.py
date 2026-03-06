"""Unit tests for AI extraction contract."""

import unittest

from ai_extraction_contract import (
    AIExtractionContractError,
    AIExtractionPayload,
    list_missing_or_low_confidence_critical_fields,
    should_request_clarification,
    validate_ai_extraction_payload,
    validate_confidence_coverage,
)


def _valid_payload():
    return {
        "risk_candidate": "red_a",
        "event_date": "2026-06-20",
        "hard_return_context": False,
        "return_context": True,
        "has_upcoming_event": None,
        "performance_intent_this_week": True,
        "returning_from_break": False,
        "recent_illness": "none",
        "break_days": None,
        "explicit_main_sport_switch_request": False,
        "performance_chase_active": True,
        "experience_level": "intermediate",
        "time_bucket": "4_6h",
        "main_sport_current": "run",
        "days_available": 4,
        "week_chaotic": False,
        "missed_sessions_count": 1,
        "pain_score": 5,
        "pain_sharp": False,
        "pain_sudden_onset": False,
        "swelling_present": False,
        "numbness_or_tingling": False,
        "pain_affects_form": False,
        "night_pain": False,
        "pain_worsening": False,
        "energy_score": 6,
        "stress_score": 5,
        "sleep_score": 6,
        "heavy_fatigue": False,
        "structure_preference": "mixed",
        "schedule_variability": "medium",
        "equipment_access": {"gym": True, "pool": False, "bike": True, "trainer": False},
        "suppress_performance_language": True,
        "track_hint": "return_or_risk_managed",
        "hard_limits": {
            "max_hard_sessions_per_week": 1,
            "allow_back_to_back_hard_days": False,
            "volume_adjustment_pct": -20,
            "intensity_allowed": False,
            "max_sessions_per_week": 5,
        },
        "field_confidence": {
            "risk_candidate": 0.95,
            "event_date": 0.93,
            "days_available": 0.91,
            "pain_score": 0.89,
        },
        "free_text_summary": "Knee pain moderate but stable.",
    }


class TestAIExtractionValidation(unittest.TestCase):
    def test_valid_payload_passes(self):
        validate_ai_extraction_payload(_valid_payload())

    def test_unknown_field_fails(self):
        payload = _valid_payload()
        payload["random_field"] = "x"
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_invalid_enum_fails(self):
        payload = _valid_payload()
        payload["risk_candidate"] = "amber"
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_invalid_recent_illness_fails(self):
        payload = _valid_payload()
        payload["recent_illness"] = "bad"
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_invalid_break_days_fails(self):
        payload = _valid_payload()
        payload["break_days"] = -1
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_invalid_explicit_switch_request_type_fails(self):
        payload = _valid_payload()
        payload["explicit_main_sport_switch_request"] = "yes"
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_invalid_hard_limits_type_fails(self):
        payload = _valid_payload()
        payload["hard_limits"]["max_hard_sessions_per_week"] = "2"
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_invalid_confidence_fails(self):
        payload = _valid_payload()
        payload["field_confidence"]["pain_score"] = 1.2
        with self.assertRaises(AIExtractionContractError):
            validate_ai_extraction_payload(payload)

    def test_dataclass_round_trip(self):
        payload = _valid_payload()
        model = AIExtractionPayload.from_dict(payload)
        self.assertEqual(model.to_dict(), payload)


class TestClarificationHelpers(unittest.TestCase):
    def test_missing_critical_fields_trigger_clarification(self):
        payload = _valid_payload()
        payload.pop("event_date")
        missing = list_missing_or_low_confidence_critical_fields(payload)
        self.assertIn("event_date", missing)
        self.assertTrue(should_request_clarification(payload))

    def test_low_confidence_triggers_clarification(self):
        payload = _valid_payload()
        payload["field_confidence"]["risk_candidate"] = 0.4
        missing = list_missing_or_low_confidence_critical_fields(payload, min_confidence=0.7)
        self.assertIn("risk_candidate", missing)
        self.assertTrue(should_request_clarification(payload, min_confidence=0.7))

    def test_high_confidence_complete_payload_no_clarification(self):
        payload = _valid_payload()
        self.assertFalse(should_request_clarification(payload))

    def test_validate_confidence_coverage_reports_missing(self):
        payload = _valid_payload()
        payload["field_confidence"].pop("days_available")
        missing, present = validate_confidence_coverage(
            payload,
            fields=("risk_candidate", "days_available", "pain_score"),
        )
        self.assertEqual(missing, {"days_available"})
        self.assertEqual(present, {"risk_candidate", "pain_score"})


if __name__ == "__main__":
    unittest.main()
