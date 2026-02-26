"""
Rate limiting and spam protection for verified users.
Quota claiming and throttled rate-limit notices; no business/LLM logic.
"""
import logging
import time
import boto3  # type: ignore
from typing import Optional, Dict, Any

from dynamodb_models import (
    claim_verified_quota_slot,
    atomically_set_verified_notice_cooldown_if_allowed,
)
from config import (
    AWS_REGION,
    VERIFIED_HOURLY_QUOTA,
    VERIFIED_DAILY_QUOTA,
    SEND_RATE_LIMIT_NOTICE,
    RATE_LIMIT_NOTICE_COOLDOWN_MINUTES,
)

logger = logging.getLogger(__name__)


class RateLimitNoticeSender:
    """Sends throttled rate-limit notices (no business logic)."""

    @staticmethod
    def send_rate_limit_notice(email: str) -> bool:
        try:
            ses_client = boto3.client("ses", region_name=AWS_REGION)
            subject = "SmartMail usage limit reached"
            body_text = (
                "You've reached your SmartMail request limit for now.\n\n"
                "Please try again later. Your limit resets automatically each hour/day.\n\n"
                "SmartMail Coach"
            )
            body_html = """<html>
<body>
<p>You've reached your SmartMail request limit for now.</p>
<p>Please try again later. Your limit resets automatically each hour/day.</p>
<p>SmartMail Coach</p>
</body>
</html>"""
            ses_client.send_email(
                Source="hello@geniml.com",
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body_text, "Charset": "UTF-8"},
                        "Html": {"Data": body_html, "Charset": "UTF-8"},
                    },
                },
            )
            logger.info("Rate-limit notice sent to %s", email)
            return True
        except Exception as e:
            logger.error("Error sending rate-limit notice to %s: %s", email, e)
            return False


def maybe_send_rate_limit_notice(
    email: str,
    block_reason: str,
    aws_request_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Sends a throttled rate-limit notice when enabled.
    Returns a small outcome dict for logging.
    """
    if not SEND_RATE_LIMIT_NOTICE:
        return {"status": "notice_disabled"}

    now = int(time.time())
    cooldown_until = now + (RATE_LIMIT_NOTICE_COOLDOWN_MINUTES * 60)
    notice_claim = atomically_set_verified_notice_cooldown_if_allowed(
        email=email, cooldown_until=cooldown_until, now=now
    )

    if not notice_claim.get("send_notice", False):
        log_parts = [
            f"from_email={email}",
            "verified=true",
            "result=rate_limit_notice_suppressed",
            f"reason={notice_claim.get('reason')}",
            f"block_reason={block_reason}",
        ]
        if aws_request_id:
            log_parts.append(f"aws_request_id={aws_request_id}")
        logger.info(", ".join(log_parts))
        return {"status": "suppressed", "reason": str(notice_claim.get("reason", ""))}

    sent = RateLimitNoticeSender.send_rate_limit_notice(email)
    log_parts = [
        f"from_email={email}",
        "verified=true",
        "result=rate_limit_notice_attempted",
        f"notice_sent={str(sent).lower()}",
        f"block_reason={block_reason}",
        f"cooldown_until={notice_claim.get('cooldown_until')}",
    ]
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(log_parts))
    return {"status": "sent" if sent else "send_failed"}


def check_verified_quota_or_block(
    from_email: str, aws_request_id: Optional[str]
) -> Optional[Dict[str, Any]]:
    """
    Claims a quota slot for the verified user. Returns None if allowed;
    returns a response dict (statusCode 200, body) if blocked (quota exceeded or error).
    """
    quota_result = claim_verified_quota_slot(
        email=from_email,
        hourly_limit=VERIFIED_HOURLY_QUOTA,
        daily_limit=VERIFIED_DAILY_QUOTA,
    )
    if quota_result.get("allowed", False):
        return None

    block_reason = str(quota_result.get("reason", ""))
    fail_closed = block_reason in {"quota_check_error", "quota_claim_conflict"}
    log_parts = [
        f"from_email={from_email}",
        "verified=true",
        "result=verified_quota_blocked",
        f"reason={block_reason}",
        f"fail_closed={str(fail_closed).lower()}",
        f"hour_bucket={quota_result.get('hour_bucket')}",
        f"day_bucket={quota_result.get('day_bucket')}",
        f"hour_count={quota_result.get('hour_count')}",
        f"day_count={quota_result.get('day_count')}",
    ]
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(str(p) for p in log_parts))

    maybe_send_rate_limit_notice(
        email=from_email,
        block_reason=block_reason,
        aws_request_id=aws_request_id,
    )
    return {"statusCode": 200, "body": "Dropped (verified quota exceeded)"}
