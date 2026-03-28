"""Validation helpers for the coaching-reasoning workflow."""

from __future__ import annotations

from typing import Any, Dict, Optional

from continuity_recommendation_contract import (
    ContinuityRecommendation,
    ContinuityRecommendationError,
)
from skills.coaching_reasoning.errors import CoachingReasoningError

_REQUIRED_FIELDS = {
    "reply_action",
    "opening",
    "main_message",
    "content_plan",
    "avoid",
    "tone",
    "recommend_material",
    "rationale",
}

_OPTIONAL_FIELDS = {"continuity_recommendation"}

_ALL_FIELDS = _REQUIRED_FIELDS | _OPTIONAL_FIELDS
_ALLOWED_REPLY_ACTIONS = {"send", "suppress"}


def _validate_continuity_recommendation(
    raw: Any,
) -> Optional[Dict[str, Any]]:
    """Validate a continuity_recommendation sub-object.

    Returns the validated dict, or raises CoachingReasoningError.
    """
    if raw is None:
        return None
    if not isinstance(raw, dict):
        raise CoachingReasoningError(
            f"'continuity_recommendation' must be a dict, got {type(raw).__name__}"
        )
    try:
        return ContinuityRecommendation.from_dict(raw).to_dict()
    except ContinuityRecommendationError as exc:
        raise CoachingReasoningError(
            f"Invalid continuity_recommendation: {exc}"
        ) from exc


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
    if (
        not isinstance(payload["reply_action"], str)
        or payload["reply_action"].strip() not in _ALLOWED_REPLY_ACTIONS
    ):
        raise CoachingReasoningError("'reply_action' must be 'send' or 'suppress'")

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

    # Validate optional continuity_recommendation
    continuity_rec = _validate_continuity_recommendation(
        payload.get("continuity_recommendation")
    )

    # Normalize: strip whitespace
    result = {
        "reply_action": payload["reply_action"].strip(),
        "opening": payload["opening"].strip(),
        "main_message": payload["main_message"].strip(),
        "content_plan": [item.strip() for item in payload["content_plan"]],
        "avoid": [item.strip() for item in payload["avoid"]],
        "tone": payload["tone"].strip(),
        "recommend_material": payload["recommend_material"].strip() if payload["recommend_material"] else None,
        "rationale": payload["rationale"].strip(),
    }
    if continuity_rec is not None:
        result["continuity_recommendation"] = continuity_rec
    return result
