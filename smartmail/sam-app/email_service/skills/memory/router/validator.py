"""Validation for memory refresh router outputs."""

from typing import Any, Dict

from config import OPENAI_CLASSIFICATION_MODEL
from skills.memory.eligibility.errors import MemoryRefreshEligibilityError
from skills.memory.router.schema import ALLOWED_ROUTES


def validate_router_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise MemoryRefreshEligibilityError("invalid_response_shape")

    route = str(payload.get("route", "")).strip().lower()
    if route not in ALLOWED_ROUTES:
        raise MemoryRefreshEligibilityError("invalid_route")

    return {
        "route": route,
        "model_name": OPENAI_CLASSIFICATION_MODEL,
        "resolution_source": "single_prompt",
        "reason_resolution": "llm_direct_routing",
    }
