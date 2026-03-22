"""Validation helpers for the coaching-reasoning workflow."""

from __future__ import annotations

from typing import Any, Dict

from skills.coaching_reasoning.errors import CoachingReasoningError

_REQUIRED_FIELDS = {
    "opening",
    "main_message",
    "content_plan",
    "avoid",
    "tone",
    "recommend_material",
    "rationale",
}

_ALL_FIELDS = _REQUIRED_FIELDS


def validate_coaching_directive(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize an LLM-produced coaching directive.

    Returns a clean dict with only the expected fields.
    Raises CoachingReasoningError on invalid input.
    """
    if not isinstance(payload, dict):
        raise CoachingReasoningError(f"Expected dict, got {type(payload).__name__}")

    missing = _REQUIRED_FIELDS - set(payload.keys())
    if missing:
        raise CoachingReasoningError(f"Missing required fields: {sorted(missing)}")

    extra = set(payload.keys()) - _ALL_FIELDS
    if extra:
        raise CoachingReasoningError(f"Unexpected fields: {sorted(extra)}")

    # Type checks
    for str_field in ("opening", "main_message", "tone", "rationale"):
        if not isinstance(payload[str_field], str) or not payload[str_field].strip():
            raise CoachingReasoningError(f"'{str_field}' must be a non-empty string")

    if not isinstance(payload["content_plan"], list) or len(payload["content_plan"]) < 1:
        raise CoachingReasoningError("'content_plan' must be a non-empty list")
    for i, item in enumerate(payload["content_plan"]):
        if not isinstance(item, str) or not item.strip():
            raise CoachingReasoningError(f"'content_plan[{i}]' must be a non-empty string")

    if not isinstance(payload["avoid"], list):
        raise CoachingReasoningError("'avoid' must be a list")
    for i, item in enumerate(payload["avoid"]):
        if not isinstance(item, str) or not item.strip():
            raise CoachingReasoningError(f"'avoid[{i}]' must be a non-empty string")

    if payload["recommend_material"] is not None and not isinstance(payload["recommend_material"], str):
        raise CoachingReasoningError("'recommend_material' must be a string or null")

    # Normalize: strip whitespace
    return {
        "opening": payload["opening"].strip(),
        "main_message": payload["main_message"].strip(),
        "content_plan": [item.strip() for item in payload["content_plan"]],
        "avoid": [item.strip() for item in payload["avoid"]],
        "tone": payload["tone"].strip(),
        "recommend_material": payload["recommend_material"].strip() if payload["recommend_material"] else None,
        "rationale": payload["rationale"].strip(),
    }
