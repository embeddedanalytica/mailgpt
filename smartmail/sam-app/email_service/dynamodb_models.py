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
import uuid
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from botocore.exceptions import ClientError
import boto3

logger = logging.getLogger()

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2"))

# Table names
COACH_PROFILES_TABLE = os.getenv("COACH_PROFILES_TABLE_NAME", "coach_profiles")
ACTION_TOKENS_TABLE = os.getenv("ACTION_TOKENS_TABLE_NAME", "action_tokens")
VERIFIED_SESSIONS_TABLE = os.getenv("VERIFIED_SESSIONS_TABLE_NAME", "verified_sessions")
RATE_LIMITS_TABLE = os.getenv("RATE_LIMITS_TABLE_NAME", "rate_limits")
ATHLETE_CONNECTIONS_TABLE = os.getenv("ATHLETE_CONNECTIONS_TABLE_NAME", "athlete_connections")
PROVIDER_TOKENS_TABLE = os.getenv("PROVIDER_TOKENS_TABLE_NAME", "provider_tokens")
ACTIVITIES_TABLE = os.getenv("ACTIVITIES_TABLE_NAME", "activities")
DAILY_METRICS_TABLE = os.getenv("DAILY_METRICS_TABLE_NAME", "daily_metrics")
PLAN_HISTORY_TABLE = os.getenv("PLAN_HISTORY_TABLE_NAME", "plan_history")
RECOMMENDATION_LOG_TABLE = os.getenv("RECOMMENDATION_LOG_TABLE_NAME", "recommendation_log")


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
# ATHLETE ID + CONNECTOR DATA
# ============================================================================

def ensure_athlete_id(email: str) -> Optional[str]:
    """
    Ensures an opaque athlete_id exists for a profile and returns it.

    This lets connector/activity tables avoid using raw email as the primary key.
    """
    try:
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        now = int(time.time())
        new_athlete_id = f"ath_{uuid.uuid4().hex}"
        response = table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET #created_at = if_not_exists(#created_at, :created_at),
                    #updated_at = :updated_at,
                    #athlete_id = if_not_exists(#athlete_id, :athlete_id)
            """,
            ExpressionAttributeNames={
                "#created_at": "created_at",
                "#updated_at": "updated_at",
                "#athlete_id": "athlete_id",
            },
            ExpressionAttributeValues={
                ":created_at": now,
                ":updated_at": now,
                ":athlete_id": new_athlete_id,
            },
            ReturnValues="ALL_NEW",
        )
        item = response.get("Attributes", {})
        athlete_id = item.get("athlete_id")
        if isinstance(athlete_id, str) and athlete_id.strip():
            return athlete_id
        return None
    except ClientError as e:
        logger.error(f"Error ensuring athlete_id for {email}: {e}")
        return None


def upsert_athlete_connection(
    athlete_id: str,
    provider: str,
    status: str = "connected",
    provider_athlete_id: Optional[str] = None,
    scopes: Optional[List[str]] = None,
    sync_cursor: Optional[str] = None,
    last_sync_at: Optional[int] = None,
    revoked_at: Optional[int] = None,
) -> bool:
    """Creates or updates connector state for an athlete/provider pair."""
    try:
        table = dynamodb.Table(ATHLETE_CONNECTIONS_TABLE)
        now = int(time.time())
        provider_norm = provider.strip().lower()

        expression_attribute_names = {
            "#created_at": "created_at",
            "#updated_at": "updated_at",
            "#status": "status",
            "#gsi_provider": "gsi_provider",
            "#provider": "provider",
        }
        expression_attribute_values = {
            ":created_at": now,
            ":updated_at": now,
            ":status": status,
            ":gsi_provider": provider_norm,
            ":provider": provider_norm,
        }
        set_clauses = [
            "#created_at = if_not_exists(#created_at, :created_at)",
            "#updated_at = :updated_at",
            "#status = :status",
            "#gsi_provider = :gsi_provider",
            "#provider = :provider",
        ]

        if provider_athlete_id:
            expression_attribute_names["#provider_athlete_id"] = "provider_athlete_id"
            expression_attribute_names["#gsi_provider_athlete_id"] = "gsi_provider_athlete_id"
            expression_attribute_values[":provider_athlete_id"] = provider_athlete_id
            set_clauses.append("#provider_athlete_id = :provider_athlete_id")
            set_clauses.append("#gsi_provider_athlete_id = :provider_athlete_id")
        if scopes is not None:
            expression_attribute_names["#scopes"] = "scopes"
            expression_attribute_values[":scopes"] = scopes
            set_clauses.append("#scopes = :scopes")
        if sync_cursor is not None:
            expression_attribute_names["#sync_cursor"] = "sync_cursor"
            expression_attribute_values[":sync_cursor"] = sync_cursor
            set_clauses.append("#sync_cursor = :sync_cursor")
        if last_sync_at is not None:
            expression_attribute_names["#last_sync_at"] = "last_sync_at"
            expression_attribute_values[":last_sync_at"] = last_sync_at
            set_clauses.append("#last_sync_at = :last_sync_at")
        if revoked_at is not None:
            expression_attribute_names["#revoked_at"] = "revoked_at"
            expression_attribute_values[":revoked_at"] = revoked_at
            set_clauses.append("#revoked_at = :revoked_at")

        table.update_item(
            Key={"athlete_id": athlete_id, "provider": provider_norm},
            UpdateExpression="SET " + ", ".join(set_clauses),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
        return True
    except ClientError as e:
        logger.error(
            f"Error upserting athlete connection athlete_id={athlete_id}, provider={provider}: {e}"
        )
        return False


def get_athlete_connection(athlete_id: str, provider: str) -> Optional[Dict[str, Any]]:
    """Returns connector state for an athlete/provider pair."""
    try:
        table = dynamodb.Table(ATHLETE_CONNECTIONS_TABLE)
        response = table.get_item(Key={"athlete_id": athlete_id, "provider": provider.lower()})
        return response.get("Item")
    except ClientError as e:
        logger.error(
            f"Error getting athlete connection athlete_id={athlete_id}, provider={provider}: {e}"
        )
        return None


def lookup_athlete_connection_by_provider_id(
    provider: str,
    provider_athlete_id: str,
) -> Optional[Dict[str, Any]]:
    """Looks up a connection by external provider identity (OAuth callback helper)."""
    try:
        from boto3.dynamodb.conditions import Key

        table = dynamodb.Table(ATHLETE_CONNECTIONS_TABLE)
        response = table.query(
            IndexName="ProviderAthleteLookupIndex",
            KeyConditionExpression=Key("gsi_provider").eq(provider.lower())
            & Key("gsi_provider_athlete_id").eq(provider_athlete_id),
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0] if items else None
    except ClientError as e:
        logger.error(
            f"Error looking up connection provider={provider}, provider_athlete_id={provider_athlete_id}: {e}"
        )
        return None


def upsert_provider_tokens(
    connection_id: str,
    access_token_enc: str,
    refresh_token_enc: Optional[str],
    expires_at: int,
) -> bool:
    """
    Stores encrypted provider OAuth tokens by connection_id.

    NOTE: Encryption should happen before calling this method.
    """
    try:
        table = dynamodb.Table(PROVIDER_TOKENS_TABLE)
        now = int(time.time())
        table.update_item(
            Key={"connection_id": connection_id},
            UpdateExpression="""
                SET #created_at = if_not_exists(#created_at, :created_at),
                    #updated_at = :updated_at,
                    #access_token_enc = :access_token_enc,
                    #refresh_token_enc = :refresh_token_enc,
                    #expires_at = :expires_at
            """,
            ExpressionAttributeNames={
                "#created_at": "created_at",
                "#updated_at": "updated_at",
                "#access_token_enc": "access_token_enc",
                "#refresh_token_enc": "refresh_token_enc",
                "#expires_at": "expires_at",
            },
            ExpressionAttributeValues={
                ":created_at": now,
                ":updated_at": now,
                ":access_token_enc": access_token_enc,
                ":refresh_token_enc": refresh_token_enc,
                ":expires_at": int(expires_at),
            },
        )
        return True
    except ClientError as e:
        logger.error(f"Error upserting provider tokens for connection_id={connection_id}: {e}")
        return False


def get_provider_tokens(connection_id: str) -> Optional[Dict[str, Any]]:
    """Returns encrypted token payload for a connector connection_id."""
    try:
        table = dynamodb.Table(PROVIDER_TOKENS_TABLE)
        response = table.get_item(Key={"connection_id": connection_id})
        return response.get("Item")
    except ClientError as e:
        logger.error(f"Error getting provider tokens for connection_id={connection_id}: {e}")
        return None


def put_normalized_activity(
    athlete_id: str,
    provider: str,
    provider_activity_id: str,
    activity_start_ts: int,
    sport: str,
    metrics: Dict[str, Any],
    source_payload_version: str = "v1",
) -> Dict[str, Any]:
    """
    Inserts one normalized activity idempotently.

    Dedupe key: (athlete_id, provider_activity_key), where provider_activity_key = "{provider}#{provider_activity_id}".
    """
    provider_norm = provider.strip().lower()
    provider_activity_key = f"{provider_norm}#{provider_activity_id}"
    now = int(time.time())

    item = {
        "athlete_id": athlete_id,
        "provider_activity_key": provider_activity_key,
        "provider": provider_norm,
        "provider_activity_id": provider_activity_id,
        "activity_start_ts": int(activity_start_ts),
        "sport": sport,
        "metrics": metrics,
        "source_payload_version": source_payload_version,
        "ingested_at": now,
    }

    try:
        table = dynamodb.Table(ACTIVITIES_TABLE)
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(provider_activity_key)",
        )
        return {"inserted": True, "reason": "inserted", "provider_activity_key": provider_activity_key}
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return {
                "inserted": False,
                "reason": "duplicate",
                "provider_activity_key": provider_activity_key,
            }
        logger.error(
            f"Error putting normalized activity athlete_id={athlete_id}, key={provider_activity_key}: {e}"
        )
        return {
            "inserted": False,
            "reason": "storage_error",
            "provider_activity_key": provider_activity_key,
        }


def put_daily_metrics(
    athlete_id: str,
    metric_date: str,
    metrics: Dict[str, Any],
    source_window_start_ts: Optional[int] = None,
    source_window_end_ts: Optional[int] = None,
) -> bool:
    """Upserts daily derived metrics for an athlete/date."""
    try:
        table = dynamodb.Table(DAILY_METRICS_TABLE)
        now = int(time.time())
        item = {
            "athlete_id": athlete_id,
            "metric_date": metric_date,
            "metrics": metrics,
            "updated_at": now,
        }
        if source_window_start_ts is not None:
            item["source_window_start_ts"] = int(source_window_start_ts)
        if source_window_end_ts is not None:
            item["source_window_end_ts"] = int(source_window_end_ts)
        table.put_item(Item=item)
        return True
    except ClientError as e:
        logger.error(f"Error putting daily metrics athlete_id={athlete_id}, metric_date={metric_date}: {e}")
        return False


def append_plan_history(
    athlete_id: str,
    plan_version_ts: int,
    plan: Dict[str, Any],
    rationale: Optional[str] = None,
    changes_from_previous: Optional[List[str]] = None,
) -> bool:
    """Appends an immutable training-plan snapshot."""
    try:
        table = dynamodb.Table(PLAN_HISTORY_TABLE)
        now = int(time.time())
        item: Dict[str, Any] = {
            "athlete_id": athlete_id,
            "plan_version_ts": int(plan_version_ts),
            "plan": plan,
            "created_at": now,
        }
        if rationale:
            item["rationale"] = rationale
        if changes_from_previous is not None:
            item["changes_from_previous"] = changes_from_previous

        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(plan_version_ts)",
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(
                f"Plan history already exists athlete_id={athlete_id}, plan_version_ts={plan_version_ts}"
            )
            return False
        logger.error(
            f"Error appending plan history athlete_id={athlete_id}, plan_version_ts={plan_version_ts}: {e}"
        )
        return False


def log_recommendation(
    athlete_id: str,
    recommendation_text: str,
    evidence_window_days: int,
    confidence: Optional[float] = None,
    status: str = "proposed",
    metadata: Optional[Dict[str, Any]] = None,
    created_at: Optional[int] = None,
) -> bool:
    """Writes one recommendation log entry for feedback loop tracking."""
    try:
        table = dynamodb.Table(RECOMMENDATION_LOG_TABLE)
        now = int(time.time())
        created_ts = int(created_at) if created_at is not None else now

        item: Dict[str, Any] = {
            "athlete_id": athlete_id,
            "created_at": created_ts,
            "recommendation_text": recommendation_text,
            "evidence_window_days": int(evidence_window_days),
            "status": status,
            "logged_at": now,
        }
        if confidence is not None:
            item["confidence"] = float(confidence)
        if metadata is not None:
            item["metadata"] = metadata

        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(created_at)",
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(
                f"Recommendation log collision athlete_id={athlete_id}, created_at={created_at}"
            )
            return False
        logger.error(
            f"Error logging recommendation athlete_id={athlete_id}, created_at={created_at}: {e}"
        )
        return False


# ============================================================================
# CURRENT PLAN (Stored in coach_profiles.current_plan)
# ============================================================================

def _default_plan_start_date(now_epoch: Optional[int] = None) -> str:
    if now_epoch is None:
        now_epoch = int(time.time())
    return datetime.fromtimestamp(now_epoch, tz=timezone.utc).strftime("%Y-%m-%d")


def _build_default_current_plan(goal: Optional[str], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    """
    Builds a minimal, structured starter plan.

    Required shape:
    - goal
    - start_date
    - week_index
    - sessions: [{date, type, target}]
    - revision
    """
    start_date = _default_plan_start_date(now_epoch=now_epoch)
    normalized_goal = (goal or "").strip() or "Build consistency"
    return {
        "goal": normalized_goal,
        "start_date": start_date,
        "week_index": 1,
        "sessions": [
            {"date": start_date, "type": "easy", "target": "30 minutes easy effort"},
        ],
        "revision": 1,
    }


def ensure_current_plan(email: str, fallback_goal: Optional[str] = None) -> bool:
    """
    Ensures coach_profiles.current_plan exists for a user.

    If current_plan already exists, it is left unchanged.
    """
    try:
        existing_profile = get_coach_profile(email) or {}
        existing_plan = existing_profile.get("current_plan")
        if isinstance(existing_plan, dict) and existing_plan:
            return True

        goal = str(existing_profile.get("goal", "")).strip() or fallback_goal
        default_plan = _build_default_current_plan(goal=goal)
        now = int(time.time())
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET #created_at = if_not_exists(#created_at, :created_at),
                    #updated_at = :updated_at,
                    #current_plan = if_not_exists(#current_plan, :current_plan)
            """,
            ExpressionAttributeNames={
                "#created_at": "created_at",
                "#updated_at": "updated_at",
                "#current_plan": "current_plan",
            },
            ExpressionAttributeValues={
                ":created_at": now,
                ":updated_at": now,
                ":current_plan": default_plan,
            },
        )
        return True
    except ClientError as e:
        logger.error(f"Error ensuring current plan for {email}: {e}")
        return False


def get_current_plan(email: str) -> Optional[Dict[str, Any]]:
    """Returns current_plan map for a user if present."""
    profile = get_coach_profile(email)
    if not profile:
        return None
    plan = profile.get("current_plan")
    if isinstance(plan, dict):
        return plan
    return None


def fetch_current_plan_summary(email: str) -> Optional[str]:
    """
    Returns a compact human-readable plan summary for reply composition.
    """
    plan = get_current_plan(email)
    if not plan:
        return None

    goal = str(plan.get("goal", "")).strip() or "Unknown goal"
    start_date = str(plan.get("start_date", "")).strip() or "unknown"
    week_index = int(plan.get("week_index", 1) or 1)
    revision = int(plan.get("revision", 1) or 1)
    sessions = plan.get("sessions")

    session_chunks: List[str] = []
    if isinstance(sessions, list):
        for session in sessions[:3]:
            if not isinstance(session, dict):
                continue
            date_value = str(session.get("date", "")).strip() or "unknown-date"
            type_value = str(session.get("type", "")).strip() or "session"
            target_value = str(session.get("target", "")).strip() or "target TBD"
            session_chunks.append(f"{date_value}: {type_value} ({target_value})")

    sessions_text = "; ".join(session_chunks) if session_chunks else "No sessions yet."
    return (
        f"Current plan - Goal: {goal}. Start: {start_date}. "
        f"Week: {week_index}. Revision: {revision}. Sessions: {sessions_text}"
    )


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
