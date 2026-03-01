"""
Account verification, registration checks, and verification-email cooldown.
Separate from business logic (LLM, coaching, profile).
"""
import os
import logging
import time
import boto3  # type: ignore
from botocore.exceptions import ClientError  # type: ignore
from typing import Optional, Dict, Any

from dynamodb_models import create_action_token
from config import (
    USERS_TABLE,
    RATE_LIMITS_TABLE_NAME,
    ACTION_BASE_URL,
    AWS_REGION,
    VERIFY_EMAIL_COOLDOWN_MINUTES,
    VERIFY_TOKEN_TTL_MINUTES,
)
from email_copy import EmailCopy

logger = logging.getLogger(__name__)
dynamodb = boto3.resource("dynamodb", region_name=AWS_REGION)


def is_registered(email_address: str) -> bool:
    """
    Checks if the email exists in the DynamoDB 'users' table.
    Returns True if found, False if not found or on error.
    """
    try:
        table = dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={"email_address": email_address.lower()})
        if "Item" in response:
            logger.info("User %s is registered.", email_address)
            return True
        logger.info("User %s is not registered.", email_address)
        return False
    except ClientError as e:
        logger.error("Error checking registration for %s: %s", email_address, e)
        return False


def atomically_set_cooldown_if_allowed(
    email: str, cooldown_until: int, now: int
) -> bool:
    """
    Atomically sets cooldown only if it doesn't exist or is in the past.
    Prevents race conditions when multiple requests try to send verification emails.

    Returns True if cooldown was successfully set (this request "won"), False otherwise.
    """
    try:
        if not RATE_LIMITS_TABLE_NAME:
            logger.error("RATE_LIMITS_TABLE_NAME environment variable not set")
            return False
        table = dynamodb.Table(RATE_LIMITS_TABLE_NAME)
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET verify_email_cooldown_until = :cooldown_until,
                    last_verify_token_sent_at = :now
            """,
            ConditionExpression="""
                attribute_not_exists(verify_email_cooldown_until) OR
                verify_email_cooldown_until <= :now
            """,
            ExpressionAttributeValues={":cooldown_until": cooldown_until, ":now": now},
        )
        return True
    except ClientError as e:
        if e.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            return False
        logger.error("Error setting cooldown for %s: %s", email, e)
        return False


def get_cooldown_until(email: str) -> Optional[int]:
    """Returns cooldown_until epoch seconds for the email, or None."""
    try:
        if not RATE_LIMITS_TABLE_NAME:
            return None
        table = dynamodb.Table(RATE_LIMITS_TABLE_NAME)
        response = table.get_item(Key={"email": email.lower()})
        if "Item" in response:
            return response["Item"].get("verify_email_cooldown_until")
        return None
    except ClientError as e:
        logger.error("Error getting cooldown for %s: %s", email, e)
        return None


class VerificationEmailSender:
    """Sends verification emails with action links (no business logic)."""

    @staticmethod
    def send_verification_email(email: str, token_id: str) -> bool:
        import boto3  # type: ignore

        try:
            if not ACTION_BASE_URL:
                logger.error("ACTION_BASE_URL environment variable not set")
                return False
            verification_link = f"{ACTION_BASE_URL}{token_id}"
            from_address = "hello@geniml.com"
            copy = EmailCopy.render_verify_email(
                verification_link=verification_link,
                verify_token_ttl_minutes=VERIFY_TOKEN_TTL_MINUTES,
            )
            ses_client = boto3.client("ses", region_name=AWS_REGION)
            ses_client.send_email(
                Source=from_address,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": copy["subject"], "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": copy["text"], "Charset": "UTF-8"},
                        "Html": {"Data": copy["html"], "Charset": "UTF-8"},
                    },
                },
            )
            logger.info("Verification email sent to %s", email)
            return True
        except Exception as e:
            logger.error("Error sending verification email to %s: %s", email, e)
            return False


def handle_unverified_sender(
    from_email: str, aws_request_id: Optional[str]
) -> Dict[str, Any]:
    """
    Handles an unverified sender: applies cooldown and optionally sends
    a verification email. Pure auth/verification; no LLM or business logic.
    """

    def log_outcome(result: str, **meta: Any) -> None:
        parts = [f"from_email={from_email}", "verified=false", f"result={result}"]
        for k, v in meta.items():
            if v is not None:
                parts.append(f"{k}={v}")
        if aws_request_id:
            parts.append(f"aws_request_id={aws_request_id}")
        logger.info(", ".join(parts))

    now = int(time.time())
    cooldown_seconds = VERIFY_EMAIL_COOLDOWN_MINUTES * 60
    cooldown_until = now + cooldown_seconds

    existing = get_cooldown_until(from_email)
    if existing and existing > now:
        log_outcome("unverified_dropped_cooldown", cooldown_until=existing)
        return {"statusCode": 200, "body": "Dropped (cooldown active)"}

    if not atomically_set_cooldown_if_allowed(from_email, cooldown_until, now):
        log_outcome("cooldown_race_lost")
        return {"statusCode": 200, "body": "Dropped (race condition)"}

    verify_ttl_seconds = VERIFY_TOKEN_TTL_MINUTES * 60
    token_id = create_action_token(
        email=from_email,
        action_type="VERIFY_SESSION",
        expires_in_seconds=verify_ttl_seconds,
        source="email_inbound",
    )
    if not token_id:
        logger.error("Failed to create verification token for %s", from_email)
        return {"statusCode": 500, "body": "Failed to create verification token."}

    if not VerificationEmailSender.send_verification_email(from_email, token_id):
        logger.error("Failed to send verification email to %s", from_email)
        return {"statusCode": 500, "body": "Failed to send verification email."}

    log_outcome("verification_email_sent", cooldown_until=cooldown_until)
    return {"statusCode": 200, "body": "Verification email sent."}
