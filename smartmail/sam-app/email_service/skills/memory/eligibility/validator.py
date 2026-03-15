"""Validation for memory refresh eligibility outputs."""

from typing import Any, Dict

from config import OPENAI_CLASSIFICATION_MODEL
from skills.memory.eligibility.errors import MemoryRefreshEligibilityError
from skills.memory.eligibility.schema import ALLOWED_REASONS


def validate_eligibility_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise MemoryRefreshEligibilityError("invalid_response_shape")

    should_refresh = payload.get("should_refresh")
    if not isinstance(should_refresh, bool):
        raise MemoryRefreshEligibilityError("invalid_should_refresh")

    reason = str(payload.get("reason", "")).strip().lower()
    if reason not in ALLOWED_REASONS:
        raise MemoryRefreshEligibilityError("invalid_reason")

    if should_refresh and reason not in {
        "durable_context_changed",
        "coaching_recommendation",
        "coaching_state_changed",
    }:
        raise MemoryRefreshEligibilityError("invalid_trigger_reason")

    if not should_refresh and reason in {
        "durable_context_changed",
        "coaching_recommendation",
        "coaching_state_changed",
    }:
        raise MemoryRefreshEligibilityError("invalid_skip_reason")

    return {
        "should_refresh": should_refresh,
        "reason": reason,
        "model_name": OPENAI_CLASSIFICATION_MODEL,
        "resolution_source": "single_prompt",
        "reason_resolution": "llm_direct_classification",
    }
