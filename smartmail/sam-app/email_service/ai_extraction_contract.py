"""
Canonical AI extraction contract for rule-engine inputs.

Purpose:
- Keep free-text extraction schema explicit and versionable.
- Validate AI outputs before they enter deterministic rule logic.
- Centralize confidence/clarification helpers for safety gating.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple


ALLOWED_RISK_CANDIDATES = {"green", "yellow", "red_a", "red_b"}
ALLOWED_EXPERIENCE_LEVELS = {"new", "intermediate", "advanced"}
ALLOWED_TIME_BUCKETS = {"2_3h", "4_6h", "7_10h", "10h_plus"}
ALLOWED_MAIN_SPORTS = {"run", "bike", "swim", "other"}
ALLOWED_STRUCTURE_PREFERENCES = {"structure", "flexibility", "mixed"}
ALLOWED_SCHEDULE_VARIABILITY = {"low", "medium", "high"}
ALLOWED_RECENT_ILLNESS = {"none", "mild", "significant"}
CRITICAL_WEEKLY_FIELDS = ("event_date", "pain_score")

_ALLOWED_TOP_LEVEL_FIELDS = {
    "risk_candidate",
    "event_date",
    "returning_from_break",
    "recent_illness",
    "break_days",
    "explicit_main_sport_switch_request",
    "experience_level",
    "time_bucket",
    "main_sport_current",
    "days_available",
    "week_chaotic",
    "missed_sessions_count",
    "pain_score",
    "pain_sharp",
    "pain_sudden_onset",
    "swelling_present",
    "numbness_or_tingling",
    "pain_affects_form",
    "night_pain",
    "pain_worsening",
    "energy_score",
    "stress_score",
    "sleep_score",
    "heavy_fatigue",
    "structure_preference",
    "schedule_variability",
    "equipment_access",
    "field_confidence",
    "free_text_summary",
}
_ALLOWED_EQUIPMENT_KEYS = {"gym", "pool", "bike", "trainer"}


class AIExtractionContractError(ValueError):
    """Raised when AI extraction payload violates schema/constraints."""


def _require_dict(field: str, value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise AIExtractionContractError(f"{field} must be a dict")
    return value


def _require_bool(field: str, value: Any) -> None:
    if not isinstance(value, bool):
        raise AIExtractionContractError(f"{field} must be a bool")


def _require_optional_bool(field: str, value: Any) -> None:
    if value is None:
        return
    _require_bool(field, value)


def _require_string_in(field: str, value: Any, allowed: Set[str]) -> None:
    if not isinstance(value, str):
        raise AIExtractionContractError(f"{field} must be a string")
    normalized = value.strip().lower()
    if normalized not in allowed:
        raise AIExtractionContractError(f"{field} must be one of {sorted(allowed)}")


def _require_int_ge(field: str, value: Any, minimum: int) -> None:
    if not isinstance(value, int) or value < minimum:
        raise AIExtractionContractError(f"{field} must be an int >= {minimum}")


def _require_optional_int_ge(field: str, value: Any, minimum: int) -> None:
    if value is None:
        return
    _require_int_ge(field, value, minimum)


def _require_number_in_range(field: str, value: Any, low: float, high: float) -> None:
    if not isinstance(value, (int, float)):
        raise AIExtractionContractError(f"{field} must be a number")
    numeric = float(value)
    if numeric < low or numeric > high:
        raise AIExtractionContractError(f"{field} must be in range [{low}, {high}]")


def _require_optional_ymd_date(field: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise AIExtractionContractError(f"{field} must be a YYYY-MM-DD string or null")
    text = value.strip()
    if len(text) != 10 or text[4] != "-" or text[7] != "-":
        raise AIExtractionContractError(f"{field} must be in YYYY-MM-DD format")
    yyyy, mm, dd = text.split("-")
    if not (yyyy.isdigit() and mm.isdigit() and dd.isdigit()):
        raise AIExtractionContractError(f"{field} must be in YYYY-MM-DD format")


def _validate_equipment_access(value: Any) -> None:
    equipment = _require_dict("equipment_access", value)
    extra = set(equipment.keys()) - _ALLOWED_EQUIPMENT_KEYS
    if extra:
        raise AIExtractionContractError(
            f"equipment_access has unknown fields: {', '.join(sorted(extra))}"
        )
    for key, val in equipment.items():
        _require_bool(f"equipment_access.{key}", val)


def _validate_field_confidence(value: Any) -> Dict[str, float]:
    confidence = _require_dict("field_confidence", value)
    normalized: Dict[str, float] = {}
    for key, val in confidence.items():
        if not isinstance(key, str) or not key.strip():
            raise AIExtractionContractError("field_confidence keys must be non-empty strings")
        _require_number_in_range(f"field_confidence.{key}", val, 0.0, 1.0)
        normalized[key.strip()] = float(val)
    return normalized


def validate_ai_extraction_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise AIExtractionContractError("payload must be a dict")

    extra = set(payload.keys()) - _ALLOWED_TOP_LEVEL_FIELDS
    if extra:
        raise AIExtractionContractError(
            f"payload has unknown fields: {', '.join(sorted(extra))}"
        )

    if "risk_candidate" in payload and payload["risk_candidate"] is not None:
        _require_string_in("risk_candidate", payload["risk_candidate"], ALLOWED_RISK_CANDIDATES)
    if "event_date" in payload:
        _require_optional_ymd_date("event_date", payload["event_date"])
    if "returning_from_break" in payload:
        _require_bool("returning_from_break", payload["returning_from_break"])
    if "recent_illness" in payload:
        _require_string_in("recent_illness", payload["recent_illness"], ALLOWED_RECENT_ILLNESS)
    if "break_days" in payload:
        _require_optional_int_ge("break_days", payload["break_days"], 0)
    if "explicit_main_sport_switch_request" in payload:
        _require_bool(
            "explicit_main_sport_switch_request",
            payload["explicit_main_sport_switch_request"],
        )
    if "experience_level" in payload:
        _require_string_in("experience_level", payload["experience_level"], ALLOWED_EXPERIENCE_LEVELS)
    if "time_bucket" in payload:
        _require_string_in("time_bucket", payload["time_bucket"], ALLOWED_TIME_BUCKETS)
    if "main_sport_current" in payload and payload["main_sport_current"] is not None:
        _require_string_in("main_sport_current", payload["main_sport_current"], ALLOWED_MAIN_SPORTS)
    if "days_available" in payload:
        _require_int_ge("days_available", payload["days_available"], 0)
    if "week_chaotic" in payload:
        _require_bool("week_chaotic", payload["week_chaotic"])
    if "missed_sessions_count" in payload:
        _require_int_ge("missed_sessions_count", payload["missed_sessions_count"], 0)
    if "pain_score" in payload:
        _require_number_in_range("pain_score", payload["pain_score"], 0.0, 10.0)
    if "pain_sharp" in payload:
        _require_bool("pain_sharp", payload["pain_sharp"])
    if "pain_sudden_onset" in payload:
        _require_bool("pain_sudden_onset", payload["pain_sudden_onset"])
    if "swelling_present" in payload:
        _require_bool("swelling_present", payload["swelling_present"])
    if "numbness_or_tingling" in payload:
        _require_bool("numbness_or_tingling", payload["numbness_or_tingling"])
    if "pain_affects_form" in payload:
        _require_bool("pain_affects_form", payload["pain_affects_form"])
    if "night_pain" in payload:
        _require_bool("night_pain", payload["night_pain"])
    if "pain_worsening" in payload:
        _require_bool("pain_worsening", payload["pain_worsening"])
    if "energy_score" in payload:
        _require_number_in_range("energy_score", payload["energy_score"], 0.0, 10.0)
    if "stress_score" in payload:
        _require_number_in_range("stress_score", payload["stress_score"], 0.0, 10.0)
    if "sleep_score" in payload:
        _require_number_in_range("sleep_score", payload["sleep_score"], 0.0, 10.0)
    if "heavy_fatigue" in payload:
        _require_bool("heavy_fatigue", payload["heavy_fatigue"])
    if "structure_preference" in payload:
        _require_string_in("structure_preference", payload["structure_preference"], ALLOWED_STRUCTURE_PREFERENCES)
    if "schedule_variability" in payload:
        _require_string_in("schedule_variability", payload["schedule_variability"], ALLOWED_SCHEDULE_VARIABILITY)
    if "equipment_access" in payload:
        _validate_equipment_access(payload["equipment_access"])
    if "field_confidence" in payload:
        _validate_field_confidence(payload["field_confidence"])
    if "free_text_summary" in payload:
        if not isinstance(payload["free_text_summary"], str):
            raise AIExtractionContractError("free_text_summary must be a string")


def list_missing_or_low_confidence_critical_fields(
    payload: Dict[str, Any],
    *,
    min_confidence: float = 0.7,
    critical_fields: Iterable[str] = CRITICAL_WEEKLY_FIELDS,
) -> List[str]:
    validate_ai_extraction_payload(payload)
    _require_number_in_range("min_confidence", min_confidence, 0.0, 1.0)

    confidence_map = payload.get("field_confidence", {})
    normalized_confidence = (
        _validate_field_confidence(confidence_map) if isinstance(confidence_map, dict) else {}
    )

    missing_or_low: List[str] = []
    for field in critical_fields:
        field_name = str(field).strip()
        if not field_name:
            continue
        value = payload.get(field_name, None)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing_or_low.append(field_name)
            continue
        confidence = normalized_confidence.get(field_name)
        if confidence is not None and confidence < min_confidence:
            missing_or_low.append(field_name)
    return missing_or_low


def should_request_clarification(
    payload: Dict[str, Any],
    *,
    min_confidence: float = 0.7,
    critical_fields: Iterable[str] = CRITICAL_WEEKLY_FIELDS,
) -> bool:
    return bool(
        list_missing_or_low_confidence_critical_fields(
            payload,
            min_confidence=min_confidence,
            critical_fields=critical_fields,
        )
    )


@dataclass(frozen=True)
class AIExtractionPayload:
    """Thin dataclass wrapper around validated extraction payload dict."""

    data: Dict[str, Any]

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "AIExtractionPayload":
        validate_ai_extraction_payload(payload)
        return cls(data=dict(payload))

    def to_dict(self) -> Dict[str, Any]:
        return dict(self.data)

    def missing_or_low_confidence_critical_fields(
        self,
        *,
        min_confidence: float = 0.7,
        critical_fields: Iterable[str] = CRITICAL_WEEKLY_FIELDS,
    ) -> List[str]:
        return list_missing_or_low_confidence_critical_fields(
            self.data,
            min_confidence=min_confidence,
            critical_fields=critical_fields,
        )

    def should_request_clarification(
        self,
        *,
        min_confidence: float = 0.7,
        critical_fields: Iterable[str] = CRITICAL_WEEKLY_FIELDS,
    ) -> bool:
        return should_request_clarification(
            self.data,
            min_confidence=min_confidence,
            critical_fields=critical_fields,
        )


def validate_confidence_coverage(
    payload: Dict[str, Any],
    *,
    fields: Iterable[str],
) -> Tuple[Set[str], Set[str]]:
    """
    Returns (missing_confidence_fields, present_confidence_fields).
    """
    validate_ai_extraction_payload(payload)
    confidence = payload.get("field_confidence", {})
    normalized = _validate_field_confidence(confidence) if isinstance(confidence, dict) else {}

    requested = {str(field).strip() for field in fields if str(field).strip()}
    present = {field for field in requested if field in normalized}
    missing = requested - present
    return missing, present
