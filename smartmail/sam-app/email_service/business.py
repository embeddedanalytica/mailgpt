"""
Business logic: single entry point for "what reply to send."
Combine profile gating and conversation intelligence in one place.
Auth, rate limits, and sending stay in auth.py, rate_limits.py, and email_reply_sender.py.
"""
import hashlib
from typing import Optional, Dict, Any, Callable

from coaching import build_profile_gated_reply
from conversation_intelligence import (
    analyze_conversation_intelligence,
    ConversationIntelligenceError,
)
from inbound_rule_router import route_inbound_with_rule_engine
from dynamodb_models import put_message_intelligence
from email_copy import EmailCopy
from config import (
    LIGHTWEIGHT_RESPONSE_MODEL,
    ADVANCED_RESPONSE_MODEL,
    MODEL_ROUTING_LIGHTWEIGHT_MAX_COMPLEXITY,
)


def _build_message_key(inbound_message_id: Optional[str], inbound_body: str) -> str:
    message_id = str(inbound_message_id or "").strip()
    if message_id:
        return message_id[:256]
    body_digest = hashlib.sha256(inbound_body.encode("utf-8")).hexdigest()[:24]
    return f"bodyhash:{body_digest}"


def _route_model_by_complexity(complexity_score: int) -> Dict[str, str]:
    threshold = max(1, min(int(MODEL_ROUTING_LIGHTWEIGHT_MAX_COMPLEXITY), 4))
    if int(complexity_score) <= threshold:
        return {
            "routing_decision": "lightweight",
            "selected_model": LIGHTWEIGHT_RESPONSE_MODEL,
        }
    return {
        "routing_decision": "advanced",
        "selected_model": ADVANCED_RESPONSE_MODEL,
    }


def get_reply_for_inbound(
    athlete_id: str,
    from_email: str,
    email_data: Dict[str, Any],
    *,
    aws_request_id: Optional[str] = None,
    log_outcome: Optional[Callable[..., None]] = None,
) -> str:
    """
    Returns the reply body to send for this inbound email.
    Conversation intelligence is an LLM-gated prerequisite.
    """
    inbound_body = email_data.get("body", "")
    inbound_subject = email_data.get("subject", "")
    inbound_message_id = str(email_data.get("message_id", "")).strip() or None
    message_key = _build_message_key(inbound_message_id, inbound_body)

    try:
        intelligence = analyze_conversation_intelligence(inbound_body)
    except ConversationIntelligenceError:
        if log_outcome is not None:
            log_outcome(
                from_email=from_email,
                verified=True,
                result="conversation_intelligence_failed",
                aws_request_id=aws_request_id,
            )
        return EmailCopy.FALLBACK_AI_ERROR_REPLY

    route = _route_model_by_complexity(intelligence["complexity_score"])
    stored = put_message_intelligence(
        athlete_id=athlete_id,
        message_id=message_key,
        intent=intelligence["intent"],
        complexity_score=intelligence["complexity_score"],
        model_name=intelligence["model_name"],
        routing_decision=route["routing_decision"],
        selected_model=route["selected_model"],
    )
    if not stored:
        if log_outcome is not None:
            log_outcome(
                from_email=from_email,
                verified=True,
                result="conversation_intelligence_store_failed",
                aws_request_id=aws_request_id,
            )
        return EmailCopy.FALLBACK_AI_ERROR_REPLY

    if log_outcome is not None:
        log_outcome(
            from_email=from_email,
            verified=True,
            result="conversation_intelligence_recorded",
            aws_request_id=aws_request_id,
            intent=intelligence["intent"],
            complexity=intelligence["complexity_score"],
            model_name=intelligence["model_name"],
            routing_decision=route["routing_decision"],
            selected_model=route["selected_model"],
        )

    rule_engine_decision = route_inbound_with_rule_engine(
        athlete_id=athlete_id,
        from_email=from_email,
        email_data=email_data,
        conversation_intelligence=intelligence,
        aws_request_id=aws_request_id,
        log_outcome=log_outcome,
    )

    return build_profile_gated_reply(
        athlete_id=athlete_id,
        from_email=from_email,
        inbound_body=inbound_body,
        inbound_message_id=inbound_message_id,
        inbound_subject=inbound_subject,
        selected_model_name=route["selected_model"],
        rule_engine_decision=rule_engine_decision,
        aws_request_id=aws_request_id,
        log_outcome=log_outcome,
    )
