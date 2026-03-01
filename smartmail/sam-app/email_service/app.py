"""
Lambda handler: orchestration only.
- Parse inbound (EmailProcessor)
- Auth & rate limits (auth, rate_limits)
- Business reply (business.get_reply_for_inbound)
- Send (EmailReplySender)
All business/LLM logic lives in business.py, openai_responder.py, response_evaluator.py, coaching.py, profile.py.
"""
import sys
import logging
from typing import Optional, Dict, Any

sys.path.append("vendor")
sys.path.append(".")

from dynamodb_models import (
    is_verified,
    canonicalize_email,
    ensure_athlete_id_for_email,
    ensure_progress_snapshot_exists,
)
from auth import is_registered, handle_unverified_sender
from rate_limits import check_verified_quota_or_block
from business import get_reply_for_inbound
from email_processor import EmailProcessor
from email_reply_sender import EmailReplySender
from email_copy import EmailCopy

logger = logging.getLogger()
logger.setLevel(logging.INFO)


def _aws_request_id_from_context(context: Any) -> Optional[str]:
    if context and hasattr(context, "aws_request_id"):
        return context.aws_request_id
    return None


def _log_inbound_outcome(
    from_email: str,
    verified: bool,
    result: str,
    aws_request_id: Optional[str] = None,
    **metadata: Any,
) -> None:
    log_parts = [
        f"from_email={from_email}",
        f"verified={str(verified).lower()}",
        f"result={result}",
    ]
    for key, value in metadata.items():
        if value is None:
            continue
        log_parts.append(f"{key}={value}")
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(log_parts))


def _handle_unregistered_sender(
    email_data: Dict[str, Any],
    aws_request_id: Optional[str],
) -> Dict[str, Any]:
    from_email = email_data["sender"]
    _log_inbound_outcome(
        from_email=from_email,
        verified=False,
        result="unregistered_blocked_before_verification",
        aws_request_id=aws_request_id,
    )
    message_id = EmailReplySender.send_reply(
        email_data,
        {
            "text": EmailCopy.REGISTRATION_REQUIRED_REPLY,
            "html": EmailCopy.REGISTRATION_REQUIRED_REPLY_HTML,
        },
    )
    return {"statusCode": 200, "body": f"Registration required. Message ID: {message_id}"}


def lambda_handler(event, context):
    """AWS Lambda function handler."""
    try:
        email_data = EmailProcessor.parse_sns_event(event)
        if not email_data:
            return {"statusCode": 400, "body": "Invalid email data."}

        from_email = canonicalize_email(email_data["sender"])
        email_data["sender"] = from_email
        aws_request_id = _aws_request_id_from_context(context)

        if not is_registered(from_email):
            return _handle_unregistered_sender(email_data, aws_request_id)

        if not is_verified(from_email):
            return handle_unverified_sender(from_email, aws_request_id)

        logger.info("User %s is verified. Proceeding with response.", from_email)

        quota_block_response = check_verified_quota_or_block(from_email, aws_request_id)
        if quota_block_response is not None:
            return quota_block_response

        athlete_id = ensure_athlete_id_for_email(from_email)
        if not athlete_id:
            logger.error("Could not resolve athlete_id for verified sender %s", from_email)
            return {"statusCode": 500, "body": "Could not initialize athlete profile state."}
        ensure_progress_snapshot_exists(athlete_id)

        reply_body = get_reply_for_inbound(
            athlete_id=athlete_id,
            from_email=from_email,
            email_data=email_data,
            aws_request_id=aws_request_id,
            log_outcome=_log_inbound_outcome,
        )
        message_id = EmailReplySender.send_reply(email_data, reply_body)
        return {"statusCode": 200, "body": f"Reply sent! Message ID: {message_id}"}

    except Exception as e:
        logger.error("Lambda execution error: %s", e)
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
