"""
LLM-driven conversation intelligence for inbound coaching messages.
"""
import json
import logging
import os
from typing import Dict, Any

try:
    import openai  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised via tests with stubs
    openai = None  # type: ignore

from config import OPENAI_CLASSIFICATION_MODEL
from email_copy import AICopy

logger = logging.getLogger(__name__)
if openai is not None:
    openai.api_key = os.getenv("OPENAI_API_KEY")

_ALLOWED_INTENTS = {
    "check_in",
    "question",
    "plan_change_request",
    "milestone_update",
    "off_topic",
}


class ConversationIntelligenceError(Exception):
    """Raised when intent/complexity extraction fails."""


def _validate_intelligence_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    intent = str(payload.get("intent", "")).strip().lower()
    if intent not in _ALLOWED_INTENTS:
        raise ConversationIntelligenceError("invalid_intent")

    complexity_raw = payload.get("complexity_score")
    if not isinstance(complexity_raw, int):
        raise ConversationIntelligenceError("invalid_complexity_type")
    if complexity_raw < 1 or complexity_raw > 5:
        raise ConversationIntelligenceError("invalid_complexity_range")

    return {
        "intent": intent,
        "complexity_score": complexity_raw,
        "model_name": OPENAI_CLASSIFICATION_MODEL,
    }


def analyze_conversation_intelligence(email_body: str) -> Dict[str, Any]:
    """
    Returns:
    - intent: enum value
    - complexity_score: int in [1, 5]
    - model_name: model used for classification
    """
    try:
        if openai is None:
            raise RuntimeError("openai package is not installed")
        client = openai.OpenAI()
        response = client.chat.completions.create(
            model=OPENAI_CLASSIFICATION_MODEL,
            messages=[
                {"role": "system", "content": AICopy.CONVERSATION_INTELLIGENCE_SYSTEM_PROMPT},
                {"role": "user", "content": email_body},
            ],
            response_format={"type": "json_object"},
            temperature=0,
        )
        raw_content = response.choices[0].message.content or ""
        payload = json.loads(raw_content)
        if not isinstance(payload, dict):
            raise ConversationIntelligenceError("invalid_response_shape")
        validated = _validate_intelligence_payload(payload)
        logger.info(
            "conversation_intelligence intent=%s complexity_score=%s model=%s",
            validated["intent"],
            validated["complexity_score"],
            validated["model_name"],
        )
        return validated
    except ConversationIntelligenceError:
        raise
    except Exception as e:
        logger.error("Error extracting conversation intelligence: %s", e)
        raise ConversationIntelligenceError("llm_intelligence_failed") from e
