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
import json
import hashlib
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
from botocore.exceptions import ClientError
import boto3
from boto3.dynamodb.conditions import Key
from boto3.dynamodb.types import TypeSerializer

logger = logging.getLogger()

# Initialize DynamoDB resource
dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2"))

# Table names
COACH_PROFILES_TABLE = os.getenv("COACH_PROFILES_TABLE_NAME", "coach_profiles")
ACTION_TOKENS_TABLE = os.getenv("ACTION_TOKENS_TABLE_NAME", "action_tokens")
VERIFIED_SESSIONS_TABLE = os.getenv("VERIFIED_SESSIONS_TABLE_NAME", "verified_sessions")
RATE_LIMITS_TABLE = os.getenv("RATE_LIMITS_TABLE_NAME", "rate_limits")
ATHLETE_IDENTITIES_TABLE = os.getenv("ATHLETE_IDENTITIES_TABLE_NAME", "athlete_identities")
ATHLETE_CONNECTIONS_TABLE = os.getenv("ATHLETE_CONNECTIONS_TABLE_NAME", "athlete_connections")
PROVIDER_TOKENS_TABLE = os.getenv("PROVIDER_TOKENS_TABLE_NAME", "provider_tokens")
ACTIVITIES_TABLE = os.getenv("ACTIVITIES_TABLE_NAME", "activities")
DAILY_METRICS_TABLE = os.getenv("DAILY_METRICS_TABLE_NAME", "daily_metrics")
PLAN_HISTORY_TABLE = os.getenv("PLAN_HISTORY_TABLE_NAME", "plan_history")
PLAN_UPDATE_REQUESTS_TABLE = os.getenv("PLAN_UPDATE_REQUESTS_TABLE_NAME", "plan_update_requests")
RECOMMENDATION_LOG_TABLE = os.getenv("RECOMMENDATION_LOG_TABLE_NAME", "recommendation_log")
CONVERSATION_INTELLIGENCE_TABLE = os.getenv(
    "CONVERSATION_INTELLIGENCE_TABLE_NAME", "conversation_intelligence"
)
MANUAL_ACTIVITY_SNAPSHOTS_TABLE = os.getenv(
    "MANUAL_ACTIVITY_SNAPSHOTS_TABLE_NAME", "manual_activity_snapshots"
)
PROGRESS_SNAPSHOTS_TABLE = os.getenv("PROGRESS_SNAPSHOTS_TABLE_NAME", "progress_snapshots")


# ============================================================================
# COACH PROFILES
# ============================================================================

_EXPERIENCE_LEVELS = {"beginner", "intermediate", "advanced", "unknown"}
_CONSTRAINT_TYPES = {"injury", "schedule", "equipment", "medical", "preference", "other"}
_CONSTRAINT_SEVERITIES = {"low", "medium", "high"}
_CONSISTENCY_STATUSES = {"low", "medium", "high"}
_TREND_DIRECTIONS = {"improving", "plateau", "declining", "unknown"}
_GOAL_ALIGNMENT = {"on_track", "at_risk", "off_track", "unknown"}
_ENERGY_STATES = {"low", "ok", "high", "unknown"}
_SORENESS_STATES = {"low", "medium", "high", "unknown"}
_SLEEP_STATES = {"poor", "ok", "good", "unknown"}
_DATA_QUALITY = {"low", "medium", "high"}
_RESPONSE_CADENCE_EXPECTATIONS = {"immediate", "daily", "few_times_per_week", "weekly", "unknown"}
_PROFILE_TEXT_FIELD_MAX_LEN = 1024
_PROFILE_TEXT_FIELDS = {
    "goal_why",
    "success_definition",
    "barriers_summary",
    "lifestyle_baseline",
    "accountability_preferences",
    "feedback_style_preference",
    "coach_expectations",
}
_TYPE_SERIALIZER = TypeSerializer()


def canonicalize_email(email: str) -> str:
    return str(email or "").strip().lower()


def _normalize_constraint_item(item: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    if not isinstance(item, dict):
        return None
    summary = str(item.get("summary", "")).strip()
    if not summary:
        return None

    constraint_type = str(item.get("type", "other")).strip().lower() or "other"
    if constraint_type not in _CONSTRAINT_TYPES:
        constraint_type = "other"

    severity = str(item.get("severity", "medium")).strip().lower() or "medium"
    if severity not in _CONSTRAINT_SEVERITIES:
        severity = "medium"

    active = item.get("active")
    if not isinstance(active, bool):
        active = True

    return {
        "type": constraint_type,
        "summary": summary,
        "severity": severity,
        "active": active,
    }


def _dedupe_constraints(constraints: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    deduped: List[Dict[str, Any]] = []
    seen = set()
    for item in constraints:
        normalized = _normalize_constraint_item(item)
        if normalized is None:
            continue
        key = (
            normalized["type"],
            " ".join(normalized["summary"].strip().lower().split()),
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(normalized)
    return deduped


def _normalize_profile_text_field(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    return value.strip()[:_PROFILE_TEXT_FIELD_MAX_LEN]


def normalize_profile_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}

    primary_goal = updates.get("primary_goal")
    if isinstance(primary_goal, str):
        primary_goal = primary_goal.strip()
    if primary_goal:
        normalized["primary_goal"] = primary_goal

    time_availability = updates.get("time_availability")
    if isinstance(time_availability, dict):
        normalized_time: Dict[str, Any] = {}
        sessions_per_week = time_availability.get("sessions_per_week")
        if isinstance(sessions_per_week, (int, float)) and int(sessions_per_week) > 0:
            normalized_time["sessions_per_week"] = int(sessions_per_week)
        hours_per_week = time_availability.get("hours_per_week")
        if isinstance(hours_per_week, (int, float)) and float(hours_per_week) > 0:
            normalized_time["hours_per_week"] = float(hours_per_week)
        if normalized_time:
            normalized["time_availability"] = normalized_time

    experience_level = updates.get("experience_level")
    if isinstance(experience_level, str):
        experience_level = experience_level.strip().lower()
    else:
        experience_level = ""
    if experience_level:
        normalized["experience_level"] = (
            experience_level if experience_level in _EXPERIENCE_LEVELS else "unknown"
        )

    experience_level_note = updates.get("experience_level_note")
    if isinstance(experience_level_note, str):
        experience_level_note = experience_level_note.strip()
        if experience_level_note:
            normalized["experience_level_note"] = experience_level_note

    constraints = updates.get("constraints")
    if isinstance(constraints, list):
        normalized["constraints"] = _dedupe_constraints(constraints)

    for field_name in _PROFILE_TEXT_FIELDS:
        value = _normalize_profile_text_field(updates.get(field_name))
        if value:
            normalized[field_name] = value

    if "response_cadence_expectation" in updates:
        cadence = str(updates.get("response_cadence_expectation", "")).strip().lower()
        if cadence not in _RESPONSE_CADENCE_EXPECTATIONS:
            cadence = "unknown"
        normalized["response_cadence_expectation"] = cadence

    return normalized


def normalize_profile_record(profile: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    profile = profile or {}
    normalized: Dict[str, Any] = {
        "primary_goal": str(profile.get("primary_goal", "")).strip(),
        "time_availability": {},
        "experience_level": "unknown",
        "constraints": [],
        "goal_why": "",
        "success_definition": "",
        "barriers_summary": "",
        "lifestyle_baseline": "",
        "accountability_preferences": "",
        "feedback_style_preference": "",
        "coach_expectations": "",
        "response_cadence_expectation": "unknown",
    }

    time_availability = profile.get("time_availability")
    if isinstance(time_availability, dict):
        sessions_per_week = time_availability.get("sessions_per_week")
        if isinstance(sessions_per_week, int) and sessions_per_week > 0:
            normalized["time_availability"]["sessions_per_week"] = sessions_per_week
        hours_per_week = time_availability.get("hours_per_week")
        if isinstance(hours_per_week, (int, float)) and float(hours_per_week) > 0:
            normalized["time_availability"]["hours_per_week"] = float(hours_per_week)

    experience_level = str(profile.get("experience_level", "unknown")).strip().lower()
    if experience_level in _EXPERIENCE_LEVELS:
        normalized["experience_level"] = experience_level

    experience_level_note = profile.get("experience_level_note")
    if isinstance(experience_level_note, str) and experience_level_note.strip():
        normalized["experience_level_note"] = experience_level_note.strip()

    constraints = profile.get("constraints")
    if isinstance(constraints, list):
        normalized["constraints"] = _dedupe_constraints(constraints)

    for field_name in _PROFILE_TEXT_FIELDS:
        normalized[field_name] = _normalize_profile_text_field(profile.get(field_name))

    cadence = str(profile.get("response_cadence_expectation", "")).strip().lower()
    if cadence in _RESPONSE_CADENCE_EXPECTATIONS:
        normalized["response_cadence_expectation"] = cadence

    return normalized


def get_athlete_id_for_email(email: str) -> Optional[str]:
    canonical_email = canonicalize_email(email)
    if not canonical_email:
        return None
    try:
        table = dynamodb.Table(ATHLETE_IDENTITIES_TABLE)
        response = table.get_item(Key={"email": canonical_email})
        item = response.get("Item", {})
        athlete_id = item.get("athlete_id")
        if isinstance(athlete_id, str) and athlete_id.strip():
            return athlete_id
        return None
    except ClientError as e:
        logger.error(f"Error getting athlete_id for {email}: {e}")
        return None


def ensure_athlete_id_for_email(email: str) -> Optional[str]:
    """
    Ensures email -> athlete_id mapping exists and an athlete-keyed profile shell exists.
    """
    canonical_email = canonicalize_email(email)
    if not canonical_email:
        return None
    try:
        identity_table = dynamodb.Table(ATHLETE_IDENTITIES_TABLE)
        now = int(time.time())
        new_athlete_id = f"ath_{uuid.uuid4().hex}"
        response = identity_table.update_item(
            Key={"email": canonical_email},
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
        if not isinstance(athlete_id, str) or not athlete_id.strip():
            return None

        profile_table = dynamodb.Table(COACH_PROFILES_TABLE)
        profile_table.update_item(
            Key={"athlete_id": athlete_id},
            UpdateExpression="""
                SET #created_at = if_not_exists(#created_at, :created_at),
                    #updated_at = :updated_at,
                    #experience_level = if_not_exists(#experience_level, :experience_level),
                    #constraints = if_not_exists(#constraints, :constraints),
                    #goal_why = if_not_exists(#goal_why, :goal_why),
                    #success_definition = if_not_exists(#success_definition, :success_definition),
                    #barriers_summary = if_not_exists(#barriers_summary, :barriers_summary),
                    #lifestyle_baseline = if_not_exists(#lifestyle_baseline, :lifestyle_baseline),
                    #accountability_preferences = if_not_exists(#accountability_preferences, :accountability_preferences),
                    #feedback_style_preference = if_not_exists(#feedback_style_preference, :feedback_style_preference),
                    #coach_expectations = if_not_exists(#coach_expectations, :coach_expectations),
                    #response_cadence_expectation = if_not_exists(#response_cadence_expectation, :response_cadence_expectation)
            """,
            ExpressionAttributeNames={
                "#created_at": "created_at",
                "#updated_at": "updated_at",
                "#experience_level": "experience_level",
                "#constraints": "constraints",
                "#goal_why": "goal_why",
                "#success_definition": "success_definition",
                "#barriers_summary": "barriers_summary",
                "#lifestyle_baseline": "lifestyle_baseline",
                "#accountability_preferences": "accountability_preferences",
                "#feedback_style_preference": "feedback_style_preference",
                "#coach_expectations": "coach_expectations",
                "#response_cadence_expectation": "response_cadence_expectation",
            },
            ExpressionAttributeValues={
                ":created_at": now,
                ":updated_at": now,
                ":experience_level": "unknown",
                ":constraints": [],
                ":goal_why": "",
                ":success_definition": "",
                ":barriers_summary": "",
                ":lifestyle_baseline": "",
                ":accountability_preferences": "",
                ":feedback_style_preference": "",
                ":coach_expectations": "",
                ":response_cadence_expectation": "unknown",
            },
        )
        return athlete_id
    except ClientError as e:
        logger.error(f"Error ensuring athlete_id for {email}: {e}")
        return None


def get_coach_profile(athlete_id: str) -> Optional[Dict[str, Any]]:
    """Retrieves an athlete profile by athlete_id."""
    try:
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        response = table.get_item(Key={"athlete_id": athlete_id})
        item = response.get("Item")
        if not item:
            return None
        return normalize_profile_record(item)
    except ClientError as e:
        logger.error(f"Error getting coach profile for athlete_id={athlete_id}: {e}")
        return None


def merge_coach_profile_fields(athlete_id: str, updates: Dict[str, Any]) -> bool:
    """
    Merges parsed profile fields for one athlete without overwriting with empty values.
    """
    sanitized_updates = normalize_profile_updates(updates)
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
            Key={"athlete_id": athlete_id},
            UpdateExpression="SET " + ", ".join(set_clauses),
            ExpressionAttributeNames=expression_attribute_names,
            ExpressionAttributeValues=expression_attribute_values,
        )
        return True
    except ClientError as e:
        logger.error(f"Error merging coach profile fields for athlete_id={athlete_id}: {e}")
        return False


# ============================================================================
# ATHLETE ID + CONNECTOR DATA
# ============================================================================

def ensure_athlete_id(email: str) -> Optional[str]:
    """
    Backward-compatible wrapper.
    Prefer ensure_athlete_id_for_email for explicit naming.
    """
    return ensure_athlete_id_for_email(email)


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


def _default_progress_snapshot(athlete_id: str, now: Optional[int] = None) -> Dict[str, Any]:
    now_epoch = int(now if now is not None else time.time())
    return {
        "athlete_id": athlete_id,
        "last_activity_at": None,
        "last_activity_type": "unknown",
        "last_7d_activity_count": 0,
        "last_14d_activity_count": 0,
        "consistency_status": "low",
        "trend_direction": "unknown",
        "goal_alignment": "unknown",
        "last_reported_energy": "unknown",
        "last_reported_soreness": "unknown",
        "last_reported_sleep": "unknown",
        "updated_at": now_epoch,
        "data_quality": "low",
    }


def normalize_progress_snapshot(record: Optional[Dict[str, Any]], athlete_id: str) -> Dict[str, Any]:
    """
    Returns a fully-shaped progress snapshot with safe defaults.
    """
    now = int(time.time())
    base = _default_progress_snapshot(athlete_id=athlete_id, now=now)
    record = record or {}

    last_activity_at = record.get("last_activity_at")
    if isinstance(last_activity_at, int) and last_activity_at > 0:
        base["last_activity_at"] = last_activity_at

    last_activity_type = str(record.get("last_activity_type", "")).strip()
    if last_activity_type:
        base["last_activity_type"] = last_activity_type

    last_7d = record.get("last_7d_activity_count")
    if isinstance(last_7d, int) and last_7d >= 0:
        base["last_7d_activity_count"] = last_7d

    last_14d = record.get("last_14d_activity_count")
    if isinstance(last_14d, int) and last_14d >= 0:
        base["last_14d_activity_count"] = last_14d

    consistency_status = str(record.get("consistency_status", "")).strip().lower()
    if consistency_status in _CONSISTENCY_STATUSES:
        base["consistency_status"] = consistency_status

    trend_direction = str(record.get("trend_direction", "")).strip().lower()
    if trend_direction in _TREND_DIRECTIONS:
        base["trend_direction"] = trend_direction

    goal_alignment = str(record.get("goal_alignment", "")).strip().lower()
    if goal_alignment in _GOAL_ALIGNMENT:
        base["goal_alignment"] = goal_alignment

    energy = str(record.get("last_reported_energy", "")).strip().lower()
    if energy in _ENERGY_STATES:
        base["last_reported_energy"] = energy

    soreness = str(record.get("last_reported_soreness", "")).strip().lower()
    if soreness in _SORENESS_STATES:
        base["last_reported_soreness"] = soreness

    sleep = str(record.get("last_reported_sleep", "")).strip().lower()
    if sleep in _SLEEP_STATES:
        base["last_reported_sleep"] = sleep

    updated_at = record.get("updated_at")
    if isinstance(updated_at, int) and updated_at > 0:
        base["updated_at"] = updated_at

    data_quality = str(record.get("data_quality", "")).strip().lower()
    if data_quality in _DATA_QUALITY:
        base["data_quality"] = data_quality
    else:
        base["data_quality"] = _data_quality(base)

    return base


def ensure_progress_snapshot_exists(athlete_id: str) -> bool:
    """Ensures a progress snapshot record exists (defaulted) for this athlete."""
    try:
        table = dynamodb.Table(PROGRESS_SNAPSHOTS_TABLE)
        now = int(time.time())
        defaults = _default_progress_snapshot(athlete_id, now=now)
        table.update_item(
            Key={"athlete_id": athlete_id},
            UpdateExpression="""
                SET #updated_at = if_not_exists(#updated_at, :updated_at),
                    #last_activity_at = if_not_exists(#last_activity_at, :last_activity_at),
                    #last_activity_type = if_not_exists(#last_activity_type, :last_activity_type),
                    #last_7d_activity_count = if_not_exists(#last_7d_activity_count, :last_7d_activity_count),
                    #last_14d_activity_count = if_not_exists(#last_14d_activity_count, :last_14d_activity_count),
                    #consistency_status = if_not_exists(#consistency_status, :consistency_status),
                    #trend_direction = if_not_exists(#trend_direction, :trend_direction),
                    #goal_alignment = if_not_exists(#goal_alignment, :goal_alignment),
                    #last_reported_energy = if_not_exists(#last_reported_energy, :last_reported_energy),
                    #last_reported_soreness = if_not_exists(#last_reported_soreness, :last_reported_soreness),
                    #last_reported_sleep = if_not_exists(#last_reported_sleep, :last_reported_sleep),
                    #data_quality = if_not_exists(#data_quality, :data_quality)
            """,
            ExpressionAttributeNames={
                "#updated_at": "updated_at",
                "#last_activity_at": "last_activity_at",
                "#last_activity_type": "last_activity_type",
                "#last_7d_activity_count": "last_7d_activity_count",
                "#last_14d_activity_count": "last_14d_activity_count",
                "#consistency_status": "consistency_status",
                "#trend_direction": "trend_direction",
                "#goal_alignment": "goal_alignment",
                "#last_reported_energy": "last_reported_energy",
                "#last_reported_soreness": "last_reported_soreness",
                "#last_reported_sleep": "last_reported_sleep",
                "#data_quality": "data_quality",
            },
            ExpressionAttributeValues={
                ":updated_at": defaults["updated_at"],
                ":last_activity_at": defaults["last_activity_at"],
                ":last_activity_type": defaults["last_activity_type"],
                ":last_7d_activity_count": defaults["last_7d_activity_count"],
                ":last_14d_activity_count": defaults["last_14d_activity_count"],
                ":consistency_status": defaults["consistency_status"],
                ":trend_direction": defaults["trend_direction"],
                ":goal_alignment": defaults["goal_alignment"],
                ":last_reported_energy": defaults["last_reported_energy"],
                ":last_reported_soreness": defaults["last_reported_soreness"],
                ":last_reported_sleep": defaults["last_reported_sleep"],
                ":data_quality": defaults["data_quality"],
            },
        )
        return True
    except ClientError as e:
        logger.error(f"Error ensuring progress snapshot athlete_id={athlete_id}: {e}")
        return False


def get_progress_snapshot(athlete_id: str) -> Optional[Dict[str, Any]]:
    try:
        table = dynamodb.Table(PROGRESS_SNAPSHOTS_TABLE)
        response = table.get_item(Key={"athlete_id": athlete_id})
        item = response.get("Item")
        if not item:
            return normalize_progress_snapshot(None, athlete_id=athlete_id)
        return normalize_progress_snapshot(item, athlete_id=athlete_id)
    except ClientError as e:
        logger.error(f"Error getting progress snapshot athlete_id={athlete_id}: {e}")
        return None


def put_manual_activity_snapshot(
    athlete_id: str,
    activity_type: str,
    timestamp: int,
    snapshot_event_id: Optional[str] = None,
    duration: Optional[str] = None,
    key_metric: Optional[str] = None,
    subjective_feedback: Optional[str] = None,
    subjective_state: Optional[Dict[str, str]] = None,
    source: str = "manual",
) -> bool:
    """Writes one manual activity snapshot and updates aggregate progress snapshot."""
    event_id = str(snapshot_event_id or "").strip() or uuid.uuid4().hex
    snapshot_key = f"{int(timestamp):010d}#{event_id}"
    try:
        snapshots_table = dynamodb.Table(MANUAL_ACTIVITY_SNAPSHOTS_TABLE)
        item: Dict[str, Any] = {
            "athlete_id": athlete_id,
            "snapshot_key": snapshot_key,
            "timestamp": int(timestamp),
            "event_id": event_id,
            "activity_type": activity_type,
            "source": source,
        }
        if duration:
            item["duration"] = duration
        if key_metric:
            item["key_metric"] = key_metric
        if subjective_feedback:
            item["subjective_feedback"] = subjective_feedback
        if subjective_state:
            item["subjective_state"] = subjective_state
        snapshots_table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(snapshot_key)",
        )
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            # Replay for same (athlete_id, snapshot_event_id) is idempotent.
            return True
        logger.error(
            f"Error putting manual activity snapshot athlete_id={athlete_id}, timestamp={timestamp}: {e}"
        )
        return False

    return recompute_progress_snapshot(athlete_id, now_epoch=int(timestamp))


def _query_manual_snapshots_between(
    athlete_id: str,
    start_ts: int,
    end_ts: int,
) -> List[Dict[str, Any]]:
    try:
        from boto3.dynamodb.conditions import Key

        table = dynamodb.Table(MANUAL_ACTIVITY_SNAPSHOTS_TABLE)
        start_key = f"{int(start_ts):010d}#"
        end_key = f"{int(end_ts):010d}#~"
        response = table.query(
            KeyConditionExpression=Key("athlete_id").eq(athlete_id)
            & Key("snapshot_key").between(start_key, end_key),
            ScanIndexForward=False,
        )
        return response.get("Items", [])
    except ClientError as e:
        logger.error(
            f"Error querying manual snapshots athlete_id={athlete_id}, start={start_ts}, end={end_ts}: {e}"
        )
        return []


def _latest_manual_snapshot(athlete_id: str) -> Optional[Dict[str, Any]]:
    try:
        from boto3.dynamodb.conditions import Key

        table = dynamodb.Table(MANUAL_ACTIVITY_SNAPSHOTS_TABLE)
        response = table.query(
            KeyConditionExpression=Key("athlete_id").eq(athlete_id),
            ScanIndexForward=False,
            Limit=1,
        )
        items = response.get("Items", [])
        return items[0] if items else None
    except ClientError as e:
        logger.error(f"Error querying latest manual snapshot athlete_id={athlete_id}: {e}")
        return None


def _count_recent_snapshots(athlete_id: str, now_epoch: int, days: int) -> int:
    window_start = now_epoch - (days * 86400)
    items = _query_manual_snapshots_between(athlete_id, window_start, now_epoch)
    return len(items)


def _consistency_status(last_7d_count: int) -> str:
    if last_7d_count >= 4:
        return "high"
    if last_7d_count >= 2:
        return "medium"
    return "low"


def _trend_direction(athlete_id: str, now_epoch: int) -> str:
    current_start = now_epoch - (7 * 86400)
    previous_start = now_epoch - (14 * 86400)
    previous_end = current_start - 1
    current_count = len(_query_manual_snapshots_between(athlete_id, current_start, now_epoch))
    previous_count = len(_query_manual_snapshots_between(athlete_id, previous_start, previous_end))
    if current_count == 0 and previous_count == 0:
        return "unknown"
    if current_count > previous_count:
        return "improving"
    if current_count < previous_count:
        return "declining"
    return "plateau"


def _goal_alignment(last_7d_count: int, last_14d_count: int) -> str:
    if last_7d_count >= 3:
        return "on_track"
    if last_7d_count >= 1 or last_14d_count >= 2:
        return "at_risk"
    if last_14d_count == 0:
        return "unknown"
    return "off_track"


def _extract_subjective_state(snapshot: Optional[Dict[str, Any]]) -> Dict[str, str]:
    unknowns = {
        "last_reported_energy": "unknown",
        "last_reported_soreness": "unknown",
        "last_reported_sleep": "unknown",
    }
    if not snapshot:
        return unknowns
    subjective_state = snapshot.get("subjective_state")
    if not isinstance(subjective_state, dict):
        return unknowns
    return {
        "last_reported_energy": str(subjective_state.get("energy", "unknown")),
        "last_reported_soreness": str(subjective_state.get("soreness", "unknown")),
        "last_reported_sleep": str(subjective_state.get("sleep", "unknown")),
    }


def _data_quality(snapshot: Dict[str, Any]) -> str:
    score = 0
    if snapshot.get("last_activity_type") and snapshot.get("last_activity_type") != "unknown":
        score += 1
    if snapshot.get("last_7d_activity_count", 0) > 0:
        score += 1
    if snapshot.get("last_reported_energy") != "unknown":
        score += 1
    if snapshot.get("last_reported_soreness") != "unknown":
        score += 1
    if snapshot.get("last_reported_sleep") != "unknown":
        score += 1
    if score >= 4:
        return "high"
    if score >= 2:
        return "medium"
    return "low"


def recompute_progress_snapshot(athlete_id: str, now_epoch: Optional[int] = None) -> bool:
    now = int(now_epoch if now_epoch is not None else time.time())
    latest = _latest_manual_snapshot(athlete_id)
    if latest is None:
        return ensure_progress_snapshot_exists(athlete_id)

    last_7d = _count_recent_snapshots(athlete_id, now, 7)
    last_14d = _count_recent_snapshots(athlete_id, now, 14)
    subjective = _extract_subjective_state(latest)

    snapshot: Dict[str, Any] = {
        "athlete_id": athlete_id,
        "last_activity_at": latest.get("timestamp"),
        "last_activity_type": str(latest.get("activity_type", "unknown")),
        "last_7d_activity_count": last_7d,
        "last_14d_activity_count": last_14d,
        "consistency_status": _consistency_status(last_7d),
        "trend_direction": _trend_direction(athlete_id, now),
        "goal_alignment": _goal_alignment(last_7d, last_14d),
        "last_reported_energy": subjective["last_reported_energy"],
        "last_reported_soreness": subjective["last_reported_soreness"],
        "last_reported_sleep": subjective["last_reported_sleep"],
        "updated_at": now,
    }
    snapshot["data_quality"] = _data_quality(snapshot)
    snapshot = normalize_progress_snapshot(snapshot, athlete_id=athlete_id)

    try:
        table = dynamodb.Table(PROGRESS_SNAPSHOTS_TABLE)
        table.put_item(Item=snapshot)
        return True
    except ClientError as e:
        logger.error(f"Error writing progress snapshot athlete_id={athlete_id}: {e}")
        return False


def append_plan_history(
    athlete_id: str,
    plan_version: int,
    plan: Dict[str, Any],
    logical_request_id: str,
    updated_at: int,
    rationale: Optional[str] = None,
    changes_from_previous: Optional[List[str]] = None,
) -> bool:
    """Appends an immutable training-plan snapshot."""
    try:
        table = dynamodb.Table(PLAN_HISTORY_TABLE)
        item: Dict[str, Any] = {
            "athlete_id": athlete_id,
            "plan_version": int(plan_version),
            "updated_at": int(updated_at),
            "logical_request_id": str(logical_request_id),
            "plan": plan,
        }
        if rationale:
            item["rationale"] = rationale
        if changes_from_previous is not None:
            item["changes_from_previous"] = changes_from_previous

        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(plan_version)",
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(
                f"Plan history already exists athlete_id={athlete_id}, plan_version={plan_version}"
            )
            return False
        logger.error(
            f"Error appending plan history athlete_id={athlete_id}, plan_version={plan_version}: {e}"
        )
        return False
    except Exception as e:
        logger.error(
            f"Unexpected error appending plan history athlete_id={athlete_id}, plan_version={plan_version}: {e}"
        )
        return False


def get_plan_history(
    athlete_id: str,
    *,
    limit: int = 50,
    cursor: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Returns immutable plan history for one athlete in ascending plan_version order."""
    try:
        table = dynamodb.Table(PLAN_HISTORY_TABLE)
        query_kwargs: Dict[str, Any] = {
            "KeyConditionExpression": Key("athlete_id").eq(athlete_id),
            "ScanIndexForward": True,
            "Limit": max(1, min(int(limit), 200)),
        }
        if cursor:
            query_kwargs["ExclusiveStartKey"] = cursor
        response = table.query(**query_kwargs)
        return {
            "items": response.get("Items", []),
            "cursor": response.get("LastEvaluatedKey"),
        }
    except ClientError as e:
        logger.error(f"Error getting plan history athlete_id={athlete_id}: {e}")
        return {"items": [], "cursor": None}


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


def put_message_intelligence(
    athlete_id: str,
    message_id: str,
    intent: str,
    complexity_score: int,
    model_name: str,
    *,
    routing_decision: Optional[str] = None,
    selected_model: Optional[str] = None,
    created_at: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> bool:
    """
    Stores one LLM-derived message intelligence record (intent + complexity).
    """
    normalized_message_id = str(message_id or "").strip()
    if not normalized_message_id:
        return False
    try:
        table = dynamodb.Table(CONVERSATION_INTELLIGENCE_TABLE)
        now = int(time.time())
        item: Dict[str, Any] = {
            "athlete_id": athlete_id,
            "message_id": normalized_message_id,
            "intent": str(intent).strip().lower(),
            "complexity_score": int(complexity_score),
            "model_name": str(model_name).strip(),
            "created_at": int(created_at) if created_at is not None else now,
            "logged_at": now,
        }
        if routing_decision is not None:
            item["routing_decision"] = str(routing_decision).strip()
        if selected_model is not None:
            item["selected_model"] = str(selected_model).strip()
        if metadata is not None:
            item["metadata"] = metadata
        table.put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(message_id)",
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            logger.warning(
                "Message intelligence already exists athlete_id=%s, message_id=%s",
                athlete_id,
                normalized_message_id,
            )
            return False
        logger.error(
            "Error storing message intelligence athlete_id=%s, message_id=%s: %s",
            athlete_id,
            normalized_message_id,
            e,
        )
        return False


# ============================================================================
# CURRENT PLAN (Stored in coach_profiles.current_plan)
# ============================================================================

_PLAN_PHASES = {"base", "build", "peak", "recovery", "unknown"}
_PLAN_STATUSES = {"active", "adjusting", "recovery"}


def _default_plan_start_date(now_epoch: Optional[int] = None) -> str:
    if now_epoch is None:
        now_epoch = int(time.time())
    return datetime.fromtimestamp(now_epoch, tz=timezone.utc).strftime("%Y-%m-%d")


def _normalize_next_recommended_session(value: Any, fallback_date: str) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {
            "date": fallback_date,
            "type": "easy",
            "target": "30 minutes easy effort",
        }
    date_value = str(value.get("date", "")).strip() or fallback_date
    type_value = str(value.get("type", "")).strip() or "easy"
    target_value = str(value.get("target", "")).strip() or "30 minutes easy effort"
    return {"date": date_value, "type": type_value, "target": target_value}


def normalize_current_plan(plan: Optional[Dict[str, Any]], fallback_goal: Optional[str] = None) -> Dict[str, Any]:
    now = int(time.time())
    start_date = _default_plan_start_date(now_epoch=now)
    plan = plan or {}
    primary_goal = str(
        plan.get("primary_goal", "") or fallback_goal or "Build consistency"
    ).strip() or "Build consistency"

    phase = str(plan.get("current_phase", "unknown")).strip().lower()
    if phase not in _PLAN_PHASES:
        phase = "unknown"
    focus = str(plan.get("current_focus", "")).strip() or "Build consistency"

    status = str(plan.get("plan_status", "active")).strip().lower()
    if status not in _PLAN_STATUSES:
        status = "active"

    plan_version_raw = plan.get("plan_version")
    if isinstance(plan_version_raw, int) and plan_version_raw >= 1:
        plan_version = plan_version_raw
    else:
        plan_version = 1

    updated_at_raw = plan.get("updated_at")
    if isinstance(updated_at_raw, int) and updated_at_raw > 0:
        updated_at = updated_at_raw
    else:
        updated_at = now

    next_session = _normalize_next_recommended_session(
        plan.get("next_recommended_session"), fallback_date=start_date
    )
    return {
        "primary_goal": primary_goal,
        "plan_version": plan_version,
        "current_phase": phase,
        "current_focus": focus,
        "next_recommended_session": next_session,
        "plan_status": status,
        "updated_at": updated_at,
    }


def _build_default_current_plan(goal: Optional[str], now_epoch: Optional[int] = None) -> Dict[str, Any]:
    """
    Builds a minimal starter current-plan object in Story 1.2 shape.
    """
    now = int(now_epoch if now_epoch is not None else time.time())
    start_date = _default_plan_start_date(now_epoch=now)
    normalized_goal = (goal or "").strip() or "Build consistency"
    return normalize_current_plan(
        {
            "primary_goal": normalized_goal,
            "plan_version": 1,
            "current_phase": "base",
            "current_focus": "Build consistency",
            "next_recommended_session": {
                "date": start_date,
                "type": "easy",
                "target": "30 minutes easy effort",
            },
            "plan_status": "active",
            "updated_at": now,
        },
        fallback_goal=normalized_goal,
    )


def _serialize_item(item: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {k: _TYPE_SERIALIZER.serialize(v) for k, v in item.items()}


def _serialize_values(values: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    return {k: _TYPE_SERIALIZER.serialize(v) for k, v in values.items()}


def _normalize_changes_from_previous(changes_from_previous: Optional[List[str]]) -> List[str]:
    if not changes_from_previous:
        return []
    normalized: List[str] = []
    for entry in changes_from_previous:
        value = str(entry).strip()
        if value:
            normalized.append(value)
    return normalized


def _normalize_plan_updates(updates: Dict[str, Any]) -> Dict[str, Any]:
    normalized: Dict[str, Any] = {}
    for key in ("primary_goal", "current_phase", "current_focus", "plan_status"):
        value = updates.get(key)
        if isinstance(value, str) and value.strip():
            normalized[key] = value.strip()
    if "next_recommended_session" in updates:
        normalized["next_recommended_session"] = _normalize_next_recommended_session(
            updates.get("next_recommended_session"),
            fallback_date=_default_plan_start_date(),
        )
    return normalized


def _compute_plan_update_payload_hash(
    athlete_id: str,
    updates: Dict[str, Any],
    rationale: Optional[str],
    changes_from_previous: Optional[List[str]],
) -> str:
    canonical_payload = {
        "athlete_id": athlete_id,
        "updates": _normalize_plan_updates(updates),
        "rationale": str(rationale or "").strip(),
        "changes_from_previous": _normalize_changes_from_previous(changes_from_previous),
    }
    canonical_json = json.dumps(canonical_payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


def _get_raw_coach_profile(athlete_id: str) -> Optional[Dict[str, Any]]:
    try:
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        response = table.get_item(Key={"athlete_id": athlete_id})
        return response.get("Item")
    except ClientError as e:
        logger.error(f"Error getting raw coach profile athlete_id={athlete_id}: {e}")
        return None


def _get_plan_update_request(athlete_id: str, logical_request_id: str) -> Optional[Dict[str, Any]]:
    try:
        table = dynamodb.Table(PLAN_UPDATE_REQUESTS_TABLE)
        response = table.get_item(
            Key={"athlete_id": athlete_id, "logical_request_id": logical_request_id}
        )
        return response.get("Item")
    except ClientError as e:
        logger.error(
            "Error reading plan update request athlete_id=%s logical_request_id=%s: %s",
            athlete_id,
            logical_request_id,
            e,
        )
        return None


def ensure_current_plan(athlete_id: str, fallback_goal: Optional[str] = None) -> bool:
    """
    Ensures coach_profiles.current_plan exists for a user.

    If current_plan already exists, it is left unchanged.
    """
    try:
        existing_profile = _get_raw_coach_profile(athlete_id) or {}
        existing_plan = existing_profile.get("current_plan")
        if isinstance(existing_plan, dict) and existing_plan:
            return True

        goal = str(existing_profile.get("primary_goal", "")).strip() or fallback_goal
        default_plan = _build_default_current_plan(goal=goal)
        now = int(time.time())
        table = dynamodb.Table(COACH_PROFILES_TABLE)
        table.update_item(
            Key={"athlete_id": athlete_id},
            UpdateExpression="""
                SET #created_at = if_not_exists(#created_at, :created_at),
                    #updated_at = :updated_at,
                    #current_plan = :current_plan
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
            ConditionExpression="attribute_not_exists(#current_plan)",
        )
        history_ok = append_plan_history(
            athlete_id=athlete_id,
            plan_version=1,
            plan=default_plan,
            logical_request_id=f"ensure_current_plan:{athlete_id}",
            updated_at=default_plan["updated_at"],
            rationale="initial_plan_created",
            changes_from_previous=["initial_version"],
        )
        if not history_ok:
            logger.error("Failed appending initial plan history athlete_id=%s", athlete_id)
            return False
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            return True
        logger.error(f"Error ensuring current plan for athlete_id={athlete_id}: {e}")
        return False


def get_current_plan(athlete_id: str) -> Optional[Dict[str, Any]]:
    """Returns current_plan map for a user if present."""
    profile = _get_raw_coach_profile(athlete_id)
    if not profile:
        return None
    plan = profile.get("current_plan")
    if isinstance(plan, dict):
        return normalize_current_plan(plan, fallback_goal=profile.get("primary_goal"))
    return None


def fetch_current_plan_summary(athlete_id: str) -> Optional[str]:
    """
    Returns a compact human-readable plan summary for reply composition.
    """
    plan = get_current_plan(athlete_id)
    if not plan:
        return None

    goal = str(plan.get("primary_goal", "")).strip() or "Unknown goal"
    version = int(plan.get("plan_version", 1) or 1)
    phase = str(plan.get("current_phase", "unknown")).strip() or "unknown"
    focus = str(plan.get("current_focus", "")).strip() or "TBD"
    status = str(plan.get("plan_status", "active")).strip() or "active"
    next_session = _normalize_next_recommended_session(
        plan.get("next_recommended_session"), fallback_date="unknown-date"
    )
    next_session_text = (
        f"{next_session['date']}: {next_session['type']} ({next_session['target']})"
    )
    return (
        f"Current plan - Goal: {goal}. Version: {version}. "
        f"Phase: {phase}. Focus: {focus}. Status: {status}. "
        f"Next session: {next_session_text}"
    )


def update_current_plan(
    athlete_id: str,
    updates: Dict[str, Any],
    *,
    logical_request_id: str,
    rationale: Optional[str] = None,
    changes_from_previous: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """
    Applies a versioned current-plan update.

    Guarantees:
    - one active plan in coach_profiles.current_plan
    - plan_version increments on each successful update
    - immutable snapshot appended to plan_history
    """
    normalized_request_id = str(logical_request_id or "").strip()
    if not normalized_request_id:
        return {
            "status": "validation_error",
            "plan_version": None,
            "error_code": "missing_logical_request_id",
        }

    payload_hash = _compute_plan_update_payload_hash(
        athlete_id=athlete_id,
        updates=updates,
        rationale=rationale,
        changes_from_previous=changes_from_previous,
    )

    for attempt in range(2):
        current = get_current_plan(athlete_id)
        if current is None:
            if not ensure_current_plan(athlete_id):
                return {
                    "status": "validation_error",
                    "plan_version": None,
                    "error_code": "missing_current_plan",
                }
            current = get_current_plan(athlete_id)
        if current is None:
            return {
                "status": "validation_error",
                "plan_version": None,
                "error_code": "missing_current_plan",
            }

        normalized_current = normalize_current_plan(
            current, fallback_goal=current.get("primary_goal")
        )
        expected_version = int(normalized_current.get("plan_version", 1))
        merged = dict(normalized_current)
        merged.update(_normalize_plan_updates(updates))

        if str(merged.get("current_phase", "unknown")).lower() not in _PLAN_PHASES:
            merged["current_phase"] = "unknown"
        if str(merged.get("plan_status", "active")).lower() not in _PLAN_STATUSES:
            merged["plan_status"] = "active"

        merged["plan_version"] = expected_version + 1
        merged["updated_at"] = int(time.time())
        merged = normalize_current_plan(merged, fallback_goal=merged.get("primary_goal"))
        next_version = int(merged["plan_version"])

        now = int(time.time())
        ledger_item = {
            "athlete_id": athlete_id,
            "logical_request_id": normalized_request_id,
            "payload_hash": payload_hash,
            "resulting_plan_version": next_version,
            "status": "applied",
            "created_at": now,
            "updated_at": now,
        }
        history_item = {
            "athlete_id": athlete_id,
            "plan_version": next_version,
            "updated_at": merged["updated_at"],
            "logical_request_id": normalized_request_id,
            "plan": merged,
        }
        if rationale:
            history_item["rationale"] = rationale
        normalized_changes = _normalize_changes_from_previous(changes_from_previous)
        if normalized_changes:
            history_item["changes_from_previous"] = normalized_changes

        try:
            dynamodb.meta.client.transact_write_items(
                TransactItems=[
                    {
                        "Put": {
                            "TableName": PLAN_UPDATE_REQUESTS_TABLE,
                            "Item": _serialize_item(ledger_item),
                            "ConditionExpression": "attribute_not_exists(logical_request_id)",
                        }
                    },
                    {
                        "Update": {
                            "TableName": COACH_PROFILES_TABLE,
                            "Key": _serialize_item({"athlete_id": athlete_id}),
                            "UpdateExpression": "SET #updated_at = :updated_at, #current_plan = :current_plan",
                            "ConditionExpression": "#current_plan.#plan_version = :expected_version",
                            "ExpressionAttributeNames": {
                                "#updated_at": "updated_at",
                                "#current_plan": "current_plan",
                                "#plan_version": "plan_version",
                            },
                            "ExpressionAttributeValues": _serialize_values(
                                {
                                    ":updated_at": now,
                                    ":current_plan": merged,
                                    ":expected_version": expected_version,
                                }
                            ),
                        }
                    },
                    {
                        "Put": {
                            "TableName": PLAN_HISTORY_TABLE,
                            "Item": _serialize_item(history_item),
                            "ConditionExpression": "attribute_not_exists(plan_version)",
                        }
                    },
                ],
            )
            return {"status": "applied", "plan_version": next_version, "error_code": None}
        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "")
            if error_code != "TransactionCanceledException":
                logger.error("Error updating current plan athlete_id=%s: %s", athlete_id, e)
                return {
                    "status": "validation_error",
                    "plan_version": None,
                    "error_code": "transaction_error",
                }

            existing_request = _get_plan_update_request(athlete_id, normalized_request_id)
            if existing_request is not None:
                existing_hash = str(existing_request.get("payload_hash", ""))
                existing_version = existing_request.get("resulting_plan_version")
                if existing_hash == payload_hash:
                    return {
                        "status": "idempotent_replay",
                        "plan_version": int(existing_version) if isinstance(existing_version, int) else None,
                        "error_code": None,
                    }
                return {
                    "status": "payload_conflict",
                    "plan_version": None,
                    "error_code": "logical_request_id_payload_mismatch",
                }

            if attempt == 0:
                continue
            return {
                "status": "retryable_concurrency_error",
                "plan_version": None,
                "error_code": "version_conflict",
            }

    return {
        "status": "retryable_concurrency_error",
        "plan_version": None,
        "error_code": "version_conflict",
    }


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
