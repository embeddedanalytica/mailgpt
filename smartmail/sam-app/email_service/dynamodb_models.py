"""
DynamoDB data access layer for SmartMail coaching product.

Provides helper functions for:
- coach_profiles: Coaching preferences storage
- action_tokens: Single-use expiring links
- verified_sessions: Verified inbox possession state
- rate_limits: Anti-abuse counters and cooldowns
"""

import os
import time
import logging
import secrets
import base64
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from botocore.exceptions import ClientError
import boto3

logger = logging.getLogger()

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2"))

# Table names
COACH_PROFILES_TABLE = "coach_profiles"
ACTION_TOKENS_TABLE = "action_tokens"
VERIFIED_SESSIONS_TABLE = "verified_sessions"
RATE_LIMITS_TABLE = "rate_limits"


# ============================================================================
# COACH PROFILES
# ============================================================================

def get_coach_profile(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves a coach profile by email.
    
    Args:
        email: Email address (lowercase)
    
    Returns:
        Profile dict or None if not found
    """
    try:
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        response = table.get_item(Key={"email": email.lower()})
        return response.get("Item")
    except ClientError as e:
        logger.error(f"Error getting coach profile for {email}: {e}")
        return None


def create_or_update_coach_profile(
    email: str,
    goal: Optional[str] = None,
    weekly_time_budget_minutes: Optional[int] = None,
    sports: Optional[List[str]] = None,
    timezone: str = "America/Vancouver",
    privacy_mode: str = "normal",
) -> bool:
    """
    Creates or updates a coach profile.
    
    Args:
        email: Email address
        goal: Coaching goal (optional)
        weekly_time_budget_minutes: Weekly time budget in minutes (optional)
        sports: List of sports (optional)
        timezone: Timezone string (default: America/Vancouver)
        privacy_mode: Privacy mode - "normal" or "high" (default: normal)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        now = int(time.time())
        
        # Build update expression
        update_expr_parts = []
        expr_attr_names = {}
        expr_attr_values = {}
        
        if goal is not None:
            update_expr_parts.append("#goal = :goal")
            expr_attr_names["#goal"] = "goal"
            expr_attr_values[":goal"] = goal
        
        if weekly_time_budget_minutes is not None:
            update_expr_parts.append("#weekly_time_budget_minutes = :weekly_time_budget_minutes")
            expr_attr_names["#weekly_time_budget_minutes"] = "weekly_time_budget_minutes"
            expr_attr_values[":weekly_time_budget_minutes"] = weekly_time_budget_minutes
        
        if sports is not None:
            update_expr_parts.append("#sports = :sports")
            expr_attr_names["#sports"] = "sports"
            expr_attr_values[":sports"] = sports
        
        update_expr_parts.append("#timezone = :timezone")
        expr_attr_names["#timezone"] = "timezone"
        expr_attr_values[":timezone"] = timezone
        
        update_expr_parts.append("#privacy_mode = :privacy_mode")
        expr_attr_names["#privacy_mode"] = "privacy_mode"
        expr_attr_values[":privacy_mode"] = privacy_mode
        
        update_expr_parts.append("#updated_at = :updated_at")
        expr_attr_names["#updated_at"] = "updated_at"
        expr_attr_values[":updated_at"] = now
        
        update_expr = "SET " + ", ".join(update_expr_parts)
        update_expr += " SET #created_at = if_not_exists(#created_at, :created_at)"
        expr_attr_names["#created_at"] = "created_at"
        expr_attr_values[":created_at"] = now
        
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression=update_expr,
            ExpressionAttributeNames=expr_attr_names,
            ExpressionAttributeValues=expr_attr_values,
        )
        return True
    except ClientError as e:
        logger.error(f"Error creating/updating coach profile for {email}: {e}")
        return False


def create_default_coach_profile(email: str) -> bool:
    """
    Creates a default coach profile on registration if absent.
    
    Args:
        email: Email address
    
    Returns:
        True if created, False otherwise
    """
    profile = get_coach_profile(email)
    if profile is None:
        return create_or_update_coach_profile(email)
    return True


def merge_coach_profile_fields(email: str, updates: Dict[str, Any]) -> bool:
    """
    Merges parsed profile fields for one sender without overwriting with empty values.
    """
    allowed_fields = {
        "goal",
        "goal_unknown",
        "weekly_time_budget_minutes",
        "weekly_time_budget_unknown",
        "sports",
        "sports_unknown",
    }
    sanitized_updates: Dict[str, Any] = {}
    for key, value in updates.items():
        if key not in allowed_fields:
            continue
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        if isinstance(value, list) and not value:
            continue
        sanitized_updates[key] = value

    if not sanitized_updates:
        return False

    try:
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        now = int(time.time())
        expression_attribute_names = {
            "#created_at": "created_at",
            "#updated_at": "updated_at",
        }
        expression_attribute_values = {
            ":created_at": now,
            ":updated_at": now,
        }
        set_clauses = [
            "#created_at = if_not_exists(#created_at, :created_at)",
            "#updated_at = :updated_at",
        ]

        for field_name, field_value in sanitized_updates.items():
            name_token = f"#f_{field_name}"
            value_token = f":v_{field_name}"
            expression_attribute_names[name_token] = field_name
            expression_attribute_values[value_token] = field_value
            set_clauses.append(f"{name_token} = {value_token}")

        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="SET " + ", ".join(set_clauses),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
        return True
    except ClientError as e:
        logger.error(f"Error merging coach profile fields for {email}: {e}")
        return False


# ============================================================================
# ACTION TOKENS
# ============================================================================

def generate_token_id() -> str:
    """Generates a random 32+ byte base64url token ID."""
    token_bytes = secrets.token_bytes(32)
    return base64.urlsafe_b64encode(token_bytes).decode("utf-8").rstrip("=")


def create_action_token(
    email: str,
    action_type: str,
    payload: Optional[Dict[str, Any]] = None,
    expires_in_seconds: int = 86400,  # Default 24 hours
    source: str = "email_inbound",
) -> Optional[str]:
    """
    Creates a single-use action token.
    
    Args:
        email: Email address
        action_type: Type of action (VERIFY_SESSION, CONNECT_STRAVA, PAUSE, etc.)
        payload: Optional JSON payload
        expires_in_seconds: Time until expiration (default: 86400 = 24 hours)
        source: Source of token creation
    
    Returns:
        Token ID if successful, None otherwise
    """
    try:
        table = dynamodb.Table(ACTION_TOKENS_TABLE)
        token_id = generate_token_id()
        now = int(time.time())
        expires_at = now + expires_in_seconds
        
        item = {
            "token_id": token_id,
            "email": email.lower(),
            "action_type": action_type,
            "expires_at": expires_at,
            "created_at": now,
            "source": source,
        }
        
        if payload:
            item["payload"] = payload
        
        table.put_item(Item=item)
        return token_id
    except ClientError as e:
        logger.error(f"Error creating action token: {e}")
        return None


def get_and_consume_action_token(token_id: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves and marks an action token as used (single-use).
    
    Args:
        token_id: Token ID to retrieve
    
    Returns:
        Token data if valid and unused, None otherwise
    """
    try:
        table = dynamodb.Table(ACTION_TOKENS_TABLE)
        now = int(time.time())
        
        # Get token
        response = table.get_item(Key={"token_id": token_id})
        if "Item" not in response:
            return None
        
        token = response["Item"]
        
        # Check if already used
        if token.get("used_at"):
            logger.warning(f"Token {token_id} already used")
            return None
        
        # Check if expired
        if token.get("expires_at", 0) < now:
            logger.warning(f"Token {token_id} expired")
            return None
        
        # Mark as used atomically
        try:
            table.update_item(
                Key={"token_id": token_id},
                UpdateExpression="SET used_at = :used_at",
                ConditionExpression="attribute_not_exists(used_at)",
                ExpressionAttributeValues={":used_at": now},
            )
            return token
        except ClientError as e:
            if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
                logger.warning(f"Token {token_id} was used concurrently")
                return None
            raise
    except ClientError as e:
        logger.error(f"Error getting/consuming action token {token_id}: {e}")
        return None


# ============================================================================
# VERIFIED SESSIONS
# ============================================================================

def is_verified(email: str) -> bool:
    """
    Checks if an email has a valid verified session.
    
    Args:
        email: Email address
    
    Returns:
        True if verified and session not expired, False otherwise
    """
    try:
        table = dynamodb.Table(VERIFIED_SESSIONS_TABLE)
        response = table.get_item(Key={"email": email.lower()})
        
        if "Item" not in response:
            return False
        
        session = response["Item"]
        now = int(time.time())
        
        # Check if session is expired
        session_expires_at = session.get("session_expires_at", 0)
        if session_expires_at < now:
            return False
        
        return True
    except ClientError as e:
        logger.error(f"Error checking verification for {email}: {e}")
        return False


def create_or_extend_verified_session(
    email: str,
    session_duration_days: int = 30,
) -> bool:
    """
    Creates or extends a verified session.
    
    Args:
        email: Email address
        session_duration_days: Number of days the session should last (default: 30)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = dynamodb.Table(VERIFIED_SESSIONS_TABLE)
        now = int(time.time())
        session_expires_at = now + (session_duration_days * 86400)
        
        # Get existing session to increment verification_count
        existing = table.get_item(Key={"email": email.lower()})
        verification_count = 1
        if "Item" in existing:
            verification_count = existing["Item"].get("verification_count", 0) + 1
        
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET session_expires_at = :session_expires_at,
                    last_verified_at = :last_verified_at,
                    last_seen_at = :last_seen_at,
                    verification_count = :verification_count
            """,
            ExpressionAttributeValues={
                ":session_expires_at": session_expires_at,
                ":last_verified_at": now,
                ":last_seen_at": now,
                ":verification_count": verification_count,
            },
        )
        return True
    except ClientError as e:
        logger.error(f"Error creating/extending verified session for {email}: {e}")
        return False


def update_last_seen(email: str) -> bool:
    """
    Updates the last_seen_at timestamp for a verified session.
    
    Args:
        email: Email address
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = dynamodb.Table(VERIFIED_SESSIONS_TABLE)
        now = int(time.time())
        
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="SET last_seen_at = :last_seen_at",
            ConditionExpression="attribute_exists(email)",
            ExpressionAttributeValues={":last_seen_at": now},
        )
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "ConditionalCheckFailedException":
            # Session doesn't exist, that's okay
            return False
        logger.error(f"Error updating last_seen for {email}: {e}")
        return False


def get_verified_session(email: str) -> Optional[Dict[str, Any]]:
    """
    Retrieves verified session data.
    
    Args:
        email: Email address
    
    Returns:
        Session data or None if not found
    """
    try:
        table = dynamodb.Table(VERIFIED_SESSIONS_TABLE)
        response = table.get_item(Key={"email": email.lower()})
        return response.get("Item")
    except ClientError as e:
        logger.error(f"Error getting verified session for {email}: {e}")
        return None


# ============================================================================
# RATE LIMITS
# ============================================================================

def _current_utc_buckets(now_epoch: Optional[int] = None) -> Dict[str, str]:
    """
    Returns current UTC hour/day buckets in string format.

    - hour_bucket: YYYYMMDDHH
    - day_bucket: YYYYMMDD
    """
    if now_epoch is None:
        now_epoch = int(time.time())
    now_utc = datetime.fromtimestamp(now_epoch, tz=timezone.utc)
    return {
        "hour_bucket": now_utc.strftime("%Y%m%d%H"),
        "day_bucket": now_utc.strftime("%Y%m%d"),
    }


def claim_verified_quota_slot(
    email: str,
    hourly_limit: int,
    daily_limit: int,
    now_epoch: Optional[int] = None,
    max_retries: int = 5,
) -> Dict[str, Any]:
    """
    Atomically claims one verified-user quota slot across both hour and day.

    This uses optimistic locking with conditional updates to stay race-safe:
    when only one slot remains, concurrent requests will allow at most one.
    """
    if now_epoch is None:
        now_epoch = int(time.time())

    table = dynamodb.Table(RATE_LIMITS_TABLE)
    buckets = _current_utc_buckets(now_epoch=now_epoch)
    current_hour_bucket = buckets["hour_bucket"]
    current_day_bucket = buckets["day_bucket"]

    for _ in range(max_retries):
        try:
            response = table.get_item(
                Key={"email": email.lower()},
                ConsistentRead=True,
            )
            item = response.get("Item", {})

            stored_hour_bucket = item.get("hour_bucket")
            stored_day_bucket = item.get("day_bucket")
            stored_hour_count = int(item.get("verified_requests_hour", 0))
            stored_day_count = int(item.get("verified_requests_day", 0))

            effective_hour_count = (
                stored_hour_count if stored_hour_bucket == current_hour_bucket else 0
            )
            effective_day_count = (
                stored_day_count if stored_day_bucket == current_day_bucket else 0
            )

            if effective_hour_count >= hourly_limit:
                return {
                    "allowed": False,
                    "reason": "hourly_limit_exceeded",
                    "hour_bucket": current_hour_bucket,
                    "day_bucket": current_day_bucket,
                    "hour_count": effective_hour_count,
                    "day_count": effective_day_count,
                }

            if effective_day_count >= daily_limit:
                return {
                    "allowed": False,
                    "reason": "daily_limit_exceeded",
                    "hour_bucket": current_hour_bucket,
                    "day_bucket": current_day_bucket,
                    "hour_count": effective_hour_count,
                    "day_count": effective_day_count,
                }

            new_hour_count = effective_hour_count + 1
            new_day_count = effective_day_count + 1

            expr_values = {
                ":new_hour_bucket": current_hour_bucket,
                ":new_day_bucket": current_day_bucket,
                ":new_hour_count": new_hour_count,
                ":new_day_count": new_day_count,
                ":now": now_epoch,
            }
            condition_parts = []

            for attr_name, prev_token in (
                ("hour_bucket", ":prev_hour_bucket"),
                ("day_bucket", ":prev_day_bucket"),
                ("verified_requests_hour", ":prev_hour_count"),
                ("verified_requests_day", ":prev_day_count"),
            ):
                if attr_name in item:
                    condition_parts.append(f"{attr_name} = {prev_token}")
                    expr_values[prev_token] = item[attr_name]
                else:
                    condition_parts.append(f"attribute_not_exists({attr_name})")

            table.update_item(
                Key={"email": email.lower()},
                UpdateExpression="""
                    SET hour_bucket = :new_hour_bucket,
                        day_bucket = :new_day_bucket,
                        verified_requests_hour = :new_hour_count,
                        verified_requests_day = :new_day_count,
                        last_verified_request_at = :now
                """,
                ConditionExpression=" AND ".join(condition_parts),
                ExpressionAttributeValues=expr_values,
            )

            return {
                "allowed": True,
                "reason": "allowed",
                "hour_bucket": current_hour_bucket,
                "day_bucket": current_day_bucket,
                "hour_count": new_hour_count,
                "day_count": new_day_count,
            }
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code == "ConditionalCheckFailedException":
                continue
            logger.error(f"Error claiming verified quota slot for {email}: {e}")
            return {
                "allowed": False,
                "reason": "quota_check_error",
                "hour_bucket": current_hour_bucket,
                "day_bucket": current_day_bucket,
                "hour_count": 0,
                "day_count": 0,
            }

    return {
        "allowed": False,
        "reason": "quota_claim_conflict",
        "hour_bucket": current_hour_bucket,
        "day_bucket": current_day_bucket,
        "hour_count": 0,
        "day_count": 0,
    }


def atomically_set_verified_notice_cooldown_if_allowed(
    email: str,
    cooldown_until: int,
    now: int,
) -> Dict[str, Any]:
    """
    Atomically sets rate-limit notice cooldown if notice sending is allowed.

    Returns:
        {
            "send_notice": bool,
            "reason": str,
            "cooldown_until": int,
        }
    """
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET verified_rate_limit_notice_cooldown_until = :cooldown_until,
                    last_rate_limit_notice_sent_at = :now
            """,
            ConditionExpression="""
                attribute_not_exists(verified_rate_limit_notice_cooldown_until) OR
                verified_rate_limit_notice_cooldown_until <= :now
            """,
            ExpressionAttributeValues={
                ":cooldown_until": cooldown_until,
                ":now": now,
            },
        )
        return {
            "send_notice": True,
            "reason": "notice_allowed",
            "cooldown_until": cooldown_until,
        }
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return {
                "send_notice": False,
                "reason": "notice_cooldown_active",
                "cooldown_until": cooldown_until,
            }
        logger.error(f"Error setting verified notice cooldown for {email}: {e}")
        return {
            "send_notice": False,
            "reason": "notice_storage_error",
            "cooldown_until": cooldown_until,
        }


def get_rate_limit(email: str) -> Dict[str, Any]:
    """
    Gets rate limit data for an email, creating if it doesn't exist.
    
    Args:
        email: Email address
    
    Returns:
        Rate limit data dict
    """
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        response = table.get_item(Key={"email": email.lower()})
        if "Item" in response:
            return response["Item"]
        return {}
    except ClientError as e:
        logger.error(f"Error getting rate limit for {email}: {e}")
        return {}


def check_verify_email_cooldown(email: str, cooldown_seconds: int = 300) -> bool:
    """
    Checks if email verification is in cooldown period.
    Returns True if cooldown is active (should NOT send), False if okay to send.
    
    Args:
        email: Email address
        cooldown_seconds: Cooldown period in seconds (default: 300 = 5 minutes)
    
    Returns:
        True if in cooldown (don't send), False if okay to send
    """
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        now = int(time.time())
        
        response = table.get_item(Key={"email": email.lower()})
        if "Item" not in response:
            return False  # No cooldown
        
        cooldown_until = response["Item"].get("verify_email_cooldown_until", 0)
        return cooldown_until > now
    except ClientError as e:
        logger.error(f"Error checking verify email cooldown for {email}: {e}")
        return False  # Fail open - allow sending


def set_verify_email_cooldown(email: str, cooldown_seconds: int = 300) -> bool:
    """
    Sets a cooldown period for sending verification emails.
    
    Args:
        email: Email address
        cooldown_seconds: Cooldown period in seconds (default: 300 = 5 minutes)
    
    Returns:
        True if successful, False otherwise
    """
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        now = int(time.time())
        cooldown_until = now + cooldown_seconds
        
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="SET verify_email_cooldown_until = :cooldown_until",
            ExpressionAttributeValues={":cooldown_until": cooldown_until},
        )
        return True
    except ClientError as e:
        logger.error(f"Error setting verify email cooldown for {email}: {e}")
        return False


def increment_unverified_drop_count(email: str) -> int:
    """
    Atomically increments the unverified drop count for the current day.
    Returns the new count.
    
    Args:
        email: Email address
    
    Returns:
        New drop count for the day
    """
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        now = int(time.time())
        day_bucket = now // 86400  # Days since epoch
        
        response = table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                ADD unverified_drop_count_day :one
                SET day_bucket = :day_bucket
            """,
            ExpressionAttributeValues={
                ":one": 1,
                ":day_bucket": day_bucket,
            },
            ReturnValues="UPDATED_NEW",
        )
        
        # If day_bucket changed, reset count
        current_day_bucket = response["Attributes"].get("day_bucket", day_bucket)
        if current_day_bucket != day_bucket:
            # Day changed, reset count
            table.update_item(
                Key={"email": email.lower()},
                UpdateExpression="""
                    SET unverified_drop_count_day = :one,
                        day_bucket = :day_bucket
                """,
                ExpressionAttributeValues={
                    ":one": 1,
                    ":day_bucket": day_bucket,
                },
            )
            return 1
        
        return response["Attributes"].get("unverified_drop_count_day", 0)
    except ClientError as e:
        logger.error(f"Error incrementing unverified drop count for {email}: {e}")
        return 0


def increment_verified_request_count(email: str, limit_type: str = "hour") -> int:
    """
    Atomically increments verified request count for hour or day.
    Returns the new count.
    
    Args:
        email: Email address
        limit_type: "hour" or "day" (default: "hour")
    
    Returns:
        New request count
    """
    try:
        table = dynamodb.Table(RATE_LIMITS_TABLE)
        now = int(time.time())
        
        if limit_type == "hour":
            bucket = now // 3600  # Hours since epoch
            attr_name = "verified_requests_hour"
            bucket_attr = "hour_bucket"
        else:
            bucket = now // 86400  # Days since epoch
            attr_name = "verified_requests_day"
            bucket_attr = "day_bucket"
        
        response = table.update_item(
            Key={"email": email.lower()},
            UpdateExpression=f"""
                ADD {attr_name} :one
                SET {bucket_attr} = :bucket
            """,
            ExpressionAttributeValues={
                ":one": 1,
                ":bucket": bucket,
            },
            ReturnValues="UPDATED_NEW",
        )
        
        # Check if bucket changed (time window rolled over)
        current_bucket = response["Attributes"].get(bucket_attr, bucket)
        if current_bucket != bucket:
            # Time window changed, reset count
            table.update_item(
                Key={"email": email.lower()},
                UpdateExpression=f"""
                    SET {attr_name} = :one,
                        {bucket_attr} = :bucket
                """,
                ExpressionAttributeValues={
                    ":one": 1,
                    ":bucket": bucket,
                },
            )
            return 1
        
        return response["Attributes"].get(attr_name, 0)
    except ClientError as e:
        logger.error(f"Error incrementing verified request count for {email}: {e}")
        return 0


def check_rate_limit_exceeded(
    email: str,
    unverified_drop_limit: int = 10,
    verified_hour_limit: int = 20,
    verified_day_limit: int = 100,
) -> Dict[str, Any]:
    """
    Checks if any rate limits are exceeded.
    
    Args:
        email: Email address
        unverified_drop_limit: Max unverified drops per day (default: 10)
        verified_hour_limit: Max verified requests per hour (default: 20)
        verified_day_limit: Max verified requests per day (default: 100)
    
    Returns:
        Dict with "exceeded" (bool) and "reason" (str) if exceeded
    """
    rate_data = get_rate_limit(email)
    now = int(time.time())
    
    # Check unverified drop count
    day_bucket = now // 86400
    if rate_data.get("day_bucket") == day_bucket:
        drop_count = rate_data.get("unverified_drop_count_day", 0)
        if drop_count >= unverified_drop_limit:
            return {
                "exceeded": True,
                "reason": f"Unverified drop limit exceeded: {drop_count}/{unverified_drop_limit}",
            }
    
    # Check verified request counts
    if is_verified(email):
        hour_bucket = now // 3600
        if rate_data.get("hour_bucket") == hour_bucket:
            hour_count = rate_data.get("verified_requests_hour", 0)
            if hour_count >= verified_hour_limit:
                return {
                    "exceeded": True,
                    "reason": f"Verified hour limit exceeded: {hour_count}/{verified_hour_limit}",
                }
        
        day_bucket = now // 86400
        if rate_data.get("day_bucket") == day_bucket:
            day_count = rate_data.get("verified_requests_day", 0)
            if day_count >= verified_day_limit:
                return {
                    "exceeded": True,
                    "reason": f"Verified day limit exceeded: {day_count}/{verified_day_limit}",
                }
    
    return {"exceeded": False}
