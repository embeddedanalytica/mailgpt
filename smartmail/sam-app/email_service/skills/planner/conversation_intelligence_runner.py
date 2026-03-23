"""Runner for conversation-intelligence classification workflow."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

import skills.runtime as skill_runtime
from config import OPENAI_CLASSIFICATION_MODEL
from skills.planner.conversation_intelligence_prompt import SYSTEM_PROMPT
from skills.planner.conversation_intelligence_schema import JSON_SCHEMA, JSON_SCHEMA_NAME
from skills.planner.conversation_intelligence_validator import validate_conversation_intelligence_output

logger = logging.getLogger(__name__)


class ConversationIntelligenceProposalError(RuntimeError):
    """Raised when conversation-intelligence generation fails."""


def run_conversation_intelligence_workflow(
    email_body: str,
    *,
    model_name: Optional[str] = None,
) -> Dict[str, Any]:
    selected_model = str(model_name or OPENAI_CLASSIFICATION_MODEL).strip() or OPENAI_CLASSIFICATION_MODEL
    return skill_runtime.run_validated_json_schema_workflow(
        logger=logger,
        model_name=selected_model,
        system_prompt=SYSTEM_PROMPT,
        user_content=json.dumps({"email_body": str(email_body or "")}, separators=(",", ":"), ensure_ascii=True),
        schema_name=JSON_SCHEMA_NAME,
        schema=JSON_SCHEMA,
        disabled_message="conversation-intelligence LLM calls are disabled",
        warning_log_name="conversation_intelligence",
        validate_payload=validate_conversation_intelligence_output,
        workflow_label="conversation_intelligence",
        proposal_error_factory=ConversationIntelligenceProposalError,
        retries=1,
        require_live_llm=False,
    )
