"""LLM-driven conversation intelligence for inbound coaching messages."""

from __future__ import annotations

import logging
from typing import Dict

from config import OPENAI_CLASSIFICATION_MODEL
from skills.planner import (
    ConversationIntelligenceProposalError,
    run_conversation_intelligence_workflow,
)

logger = logging.getLogger(__name__)


class ConversationIntelligenceError(Exception):
    """Raised when intent/complexity extraction fails."""


def analyze_conversation_intelligence(email_body: str) -> Dict[str, object]:
    """
    Returns:
    - intent: enum value
    - complexity_score: int in [1, 5]
    - model_name: model used for classification
    """
    try:
        validated = run_conversation_intelligence_workflow(email_body)
        logger.info(
            "conversation_intelligence intent=%s complexity_score=%s requested_action=%s brevity=%s model=%s",
            validated["intent"],
            validated["complexity_score"],
            validated.get("requested_action"),
            validated.get("brevity_preference"),
            validated["model_name"],
        )
        return validated
    except ConversationIntelligenceProposalError:
        return {
            "intent": "coaching",
            "complexity_score": 3,
            "requested_action": "plan_update",
            "brevity_preference": "normal",
            "model_name": OPENAI_CLASSIFICATION_MODEL,
            "resolution_source": "fallback",
            "intent_resolution_reason": "single_prompt_validation_failed",
        }
    except Exception as e:
        logger.error("Error extracting conversation intelligence: %s", e)
        return {
            "intent": "coaching",
            "complexity_score": 3,
            "requested_action": "plan_update",
            "brevity_preference": "normal",
            "model_name": OPENAI_CLASSIFICATION_MODEL,
            "resolution_source": "fallback",
            "intent_resolution_reason": "llm_intelligence_failed",
        }
