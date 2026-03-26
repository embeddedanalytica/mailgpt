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

_ALLOWED_REQUESTED_ACTIONS = {
    "plan_update",
    "answer_question",
    "checkin_ack",
    "clarify_only",
}

_ALLOWED_BREVITY = {"brief", "normal"}

# Fallback mapping: when the LLM omits requested_action, infer from intent.
_DEFAULT_ACTION_FOR_INTENT: Dict[str, str] = {
    "coaching": "plan_update",
    "question": "answer_question",
    "off_topic": "clarify_only",
    "safety_concern": "clarify_only",
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

    # requested_action: validate if present, default from intent if missing
    raw_action = str(payload.get("requested_action", "")).strip().lower()
    if raw_action in _ALLOWED_REQUESTED_ACTIONS:
        requested_action = raw_action
    else:
        requested_action = _DEFAULT_ACTION_FOR_INTENT.get(intent, "plan_update")

    # brevity_preference: validate if present, default to "normal"
    raw_brevity = str(payload.get("brevity_preference", "")).strip().lower()
    brevity_preference = raw_brevity if raw_brevity in _ALLOWED_BREVITY else "normal"

    return {
        "intent": intent,
        "complexity_score": complexity_raw,
        "requested_action": requested_action,
        "brevity_preference": brevity_preference,
        "model_name": OPENAI_CLASSIFICATION_MODEL,
        "resolution_source": "single_prompt",
        "intent_resolution_reason": "llm_direct_classification",
    }
