"""Validator for session-checkin extraction workflow."""

from __future__ import annotations

from typing import Any, Dict

from ai_extraction_contract import (
    validate_ai_extraction_payload,
)

_SESSION_CHECKIN_NULLABLE_FIELDS = {
    "risk_candidate",
    "event_date",
    "break_days",
    "main_sport_current",
}


class SessionCheckinExtractionContractError(ValueError):
    """Raised when session-checkin extraction response shape is invalid."""


def validate_session_checkin_extraction_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise SessionCheckinExtractionContractError("invalid_response_shape")

    dropped_none_keys = sorted(
        key
        for key, value in payload.items()
        if value is None and key not in _SESSION_CHECKIN_NULLABLE_FIELDS
    )
    if dropped_none_keys:
        payload = {key: value for key, value in payload.items() if key not in dropped_none_keys}

    validate_ai_extraction_payload(payload)
    return dict(payload)
