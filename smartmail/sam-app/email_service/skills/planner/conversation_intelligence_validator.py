"""Validator for conversation-intelligence classification workflow."""

from __future__ import annotations

from typing import Any, Dict

from config import OPENAI_CLASSIFICATION_MODEL

_ALLOWED_INTENTS = {
    "coaching",
    "question",
    "off_topic",
    "safety_concern",
}


class ConversationIntelligenceContractError(ValueError):
    """Raised when conversation-intelligence response shape is invalid."""


def validate_conversation_intelligence_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ConversationIntelligenceContractError("invalid_response_shape")

    intent = str(payload.get("intent", "")).strip().lower()
    if intent not in _ALLOWED_INTENTS:
        raise ConversationIntelligenceContractError("invalid_intent")

    complexity_raw = payload.get("complexity_score")
    if not isinstance(complexity_raw, int):
        raise ConversationIntelligenceContractError("invalid_complexity_type")
    if complexity_raw < 1 or complexity_raw > 5:
        raise ConversationIntelligenceContractError("invalid_complexity_range")

    return {
        "intent": intent,
        "complexity_score": complexity_raw,
        "model_name": OPENAI_CLASSIFICATION_MODEL,
        "resolution_source": "single_prompt",
        "intent_resolution_reason": "llm_direct_classification",
    }
