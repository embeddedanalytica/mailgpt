"""Runner for conversation-intelligence classification workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import OPENAI_CLASSIFICATION_MODEL
from skills.planner.conversation_intelligence_prompt import SYSTEM_PROMPT
from skills.planner.conversation_intelligence_schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.planner.conversation_intelligence_validator import (
    ConversationIntelligenceContractError,
    validate_conversation_intelligence_output,
)

logger = logging.getLogger(__name__)


class ConversationIntelligenceProposalError(RuntimeError):
    """Raised when conversation-intelligence generation fails."""


def run_conversation_intelligence_workflow(
    email_body: str,
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    raw_content = ""
    try:
        selected_model = str(model_name or OPENAI_CLASSIFICATION_MODEL).strip() or OPENAI_CLASSIFICATION_MODEL
        payload, raw_content = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=selected_model,
            system_prompt=SYSTEM_PROMPT,
            user_content=json.dumps({"email_body": str(email_body or "")}, separators=(",", ":"), ensure_ascii=True),
            schema_name=JSON_SCHEMA_NAME,
            schema=JSON_SCHEMA,
            disabled_message="conversation-intelligence LLM calls are disabled",
            warning_log_name="conversation_intelligence",
            retries=1,
            require_live_llm=False,
        )
        return validate_conversation_intelligence_output(payload)
    except (ConversationIntelligenceContractError, skill_runtime.SkillExecutionError) as exc:
        logger.error(
            "Conversation-intelligence workflow failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(getattr(exc, "raw_response", "") or raw_content),
        )
        raise ConversationIntelligenceProposalError("conversation_intelligence_failed") from exc
    except Exception as exc:
        logger.error(
            "Conversation-intelligence workflow failed: %s (raw_response_preview=%s)",
            exc,
            skill_runtime.preview_text(raw_content),
        )
        raise ConversationIntelligenceProposalError("conversation_intelligence_failed") from exc
