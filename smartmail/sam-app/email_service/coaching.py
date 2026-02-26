"""
Profile-gated coaching flow: apply profile updates from email and decide reply.
Business logic only; auth/verification/rate limits are handled by the handler.
"""
import logging
from typing import Optional, Dict, Any, Callable

from dynamodb_models import get_coach_profile, merge_coach_profile_fields
from profile import (
    parse_profile_updates_from_email,
    get_missing_required_profile_fields,
    build_profile_collection_reply,
)

logger = logging.getLogger(__name__)


def build_profile_gated_reply(
    from_email: str,
    inbound_body: str,
    *,
    aws_request_id: Optional[str] = None,
    log_outcome: Optional[Callable[..., None]] = None,
) -> str:
    """
    Applies profile updates from the email, then returns the reply text:
    - If profile is still incomplete: prompt for missing fields.
    - If profile is complete: ready-for-coaching message.

    log_outcome(from_email=..., verified=..., result=..., **kwargs) is called
    for structured logging when provided.
    """
    def log(*, result: str, **kwargs: Any) -> None:
        if log_outcome is None:
            return
        log_outcome(from_email=from_email, verified=True, result=result, aws_request_id=aws_request_id, **kwargs)

    profile_before = get_coach_profile(from_email) or {}
    missing_before = get_missing_required_profile_fields(profile_before)

    parsed_updates = parse_profile_updates_from_email(inbound_body)
    if parsed_updates:
        update_ok = merge_coach_profile_fields(from_email, parsed_updates)
        log(result="profile_updated", fields="|".join(sorted(parsed_updates.keys())))
        if not update_ok:
            logger.error(
                "from_email=%s, verified=true, result=profile_update_failed%s",
                from_email,
                f", aws_request_id={aws_request_id}" if aws_request_id else "",
            )

    profile_after = get_coach_profile(from_email) or profile_before
    missing_after = get_missing_required_profile_fields(profile_after)

    if missing_after:
        log(
            result="profile_missing_context",
            missing_fields="|".join(missing_after),
            missing_count=len(missing_after),
        )
        return build_profile_collection_reply(missing_after)

    log(result="profile_ready_for_coaching")
    log(
        result="profile_gate_evaluated",
        missing_before=len(missing_before),
        missing_after=len(missing_after),
    )
    return (
        "✅ You're ready for coaching. Share your latest training question "
        "or session details and I'll help you plan next steps."
    )
