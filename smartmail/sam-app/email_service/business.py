"""
Business logic: single entry point for "what reply to send."
Combine profile gating and (when ready) LLM reply here so you can improve the LLM flow in one place.
Auth, rate limits, and sending stay in auth.py, rate_limits.py, and email_reply_sender.py.
"""
from typing import Optional, Dict, Any, Callable

from coaching import build_profile_gated_reply


def get_reply_for_inbound(
    from_email: str,
    email_data: Dict[str, Any],
    *,
    aws_request_id: Optional[str] = None,
    log_outcome: Optional[Callable[..., None]] = None,
) -> str:
    """
    Returns the reply body to send for this inbound email.
    - Today: profile-gated reply (collect missing profile or "ready for coaching").
    - Later: when profile is complete, call OpenAIResponder.generate_response(...) and return that.
    All LLM and coaching decisions live here so you can iterate on the flow without touching the handler.
    """
    inbound_body = email_data.get("body", "")
    return build_profile_gated_reply(
        from_email=from_email,
        inbound_body=inbound_body,
        aws_request_id=aws_request_id,
        log_outcome=log_outcome,
    )
