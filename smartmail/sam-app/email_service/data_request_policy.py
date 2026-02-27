"""
Minimal v1 data request policy.

YAGNI-first implementation:
- Liberal by default.
- No DB-backed policy resolution yet.
- Only basic shape validation and hard safety caps.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


# Liberal defaults
DEFAULT_WINDOW_DAYS = 30
DEFAULT_MAX_ITEMS = 1000
DEFAULT_TIMEOUT_SECONDS = 30

# Hard safety caps (finite runaway protection)
HARD_CAP_WINDOW_DAYS = 90
HARD_CAP_MAX_ITEMS = 5000
HARD_CAP_TIMEOUT_SECONDS = 120


@dataclass(frozen=True)
class PolicyDecision:
    allowed: bool
    normalized_request: Optional[Dict[str, Any]]
    reasons: List[str]


def _validate_provider(provider: Any, reasons: List[str]) -> Optional[str]:
    if not isinstance(provider, str) or not provider.strip():
        reasons.append("provider is required and must be a non-empty string")
        return None
    return provider.strip().lower()


def _validate_data_types(data_types: Any, reasons: List[str]) -> Optional[List[str]]:
    if not isinstance(data_types, list) or not data_types:
        reasons.append("data_types is required and must be a non-empty list")
        return None

    normalized: List[str] = []
    for item in data_types:
        if not isinstance(item, str) or not item.strip():
            reasons.append("data_types must contain only non-empty strings")
            return None
        token = item.strip().lower()
        if token not in normalized:
            normalized.append(token)
    return normalized


def _validate_positive_int(field_name: str, value: Any, reasons: List[str]) -> Optional[int]:
    if not isinstance(value, int) or value < 1:
        reasons.append(f"{field_name} must be an integer >= 1")
        return None
    return value


def resolve_request(request: Dict[str, Any]) -> PolicyDecision:
    """
    Resolve a connector data request with a liberal allow policy.

    Required fields:
    - provider: non-empty string
    - data_types: non-empty list of strings

    Optional fields:
    - window_days (default 30, clamped to hard cap 90)
    - max_items (default 1000, clamped to hard cap 5000)
    - timeout_seconds (default 30, clamped to hard cap 120)
    """
    reasons: List[str] = []
    if not isinstance(request, dict):
        return PolicyDecision(
            allowed=False, normalized_request=None, reasons=["request must be a dict"]
        )

    provider = _validate_provider(request.get("provider"), reasons)
    data_types = _validate_data_types(request.get("data_types"), reasons)

    window_days_raw = request.get("window_days", DEFAULT_WINDOW_DAYS)
    max_items_raw = request.get("max_items", DEFAULT_MAX_ITEMS)
    timeout_raw = request.get("timeout_seconds", DEFAULT_TIMEOUT_SECONDS)

    window_days = _validate_positive_int("window_days", window_days_raw, reasons)
    max_items = _validate_positive_int("max_items", max_items_raw, reasons)
    timeout_seconds = _validate_positive_int("timeout_seconds", timeout_raw, reasons)

    if reasons:
        return PolicyDecision(allowed=False, normalized_request=None, reasons=reasons)

    assert provider is not None
    assert data_types is not None
    assert window_days is not None
    assert max_items is not None
    assert timeout_seconds is not None

    normalized_request = {
        "provider": provider,
        "data_types": data_types,
        "window_days": min(window_days, HARD_CAP_WINDOW_DAYS),
        "max_items": min(max_items, HARD_CAP_MAX_ITEMS),
        "timeout_seconds": min(timeout_seconds, HARD_CAP_TIMEOUT_SECONDS),
    }
    return PolicyDecision(allowed=True, normalized_request=normalized_request, reasons=[])
