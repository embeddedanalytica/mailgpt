"""
Profile-gated coaching flow: apply profile updates from email and decide reply.
Business logic only; auth/verification/rate limits are handled by the handler.
"""
import logging
import time
from typing import Optional, Dict, Any, Callable

from dynamodb_models import (
    get_coach_profile,
    merge_coach_profile_fields,
    ensure_current_plan,
    fetch_current_plan_summary,
    create_action_token,
    put_manual_activity_snapshot,
    get_progress_snapshot,
)
from config import ACTION_BASE_URL
from activity_snapshot import parse_manual_activity_snapshot_from_email
from profile import (
    parse_profile_updates_from_email,
    get_missing_required_profile_fields,
    build_profile_collection_reply,
)
from email_copy import EmailCopy

logger = logging.getLogger(__name__)


def _build_connect_strava_link(from_email: str) -> Optional[str]:
    """Creates a CONNECT_STRAVA action link for coaching onboarding."""
    if not ACTION_BASE_URL:
        return None
    token_id = create_action_token(
        email=from_email,
        action_type="CONNECT_STRAVA",
        expires_in_seconds=24 * 60 * 60,
        source="ready_for_coaching_reply",
    )
    if not token_id:
        return None
    return f"{ACTION_BASE_URL}{token_id}"


def build_profile_gated_reply(
    athlete_id: str,
    from_email: str,
    inbound_body: str,
    inbound_message_id: Optional[str] = None,
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

    profile_before = get_coach_profile(athlete_id) or {}
    missing_before = get_missing_required_profile_fields(profile_before)

    parsed_updates = parse_profile_updates_from_email(inbound_body)
    if parsed_updates:
        update_ok = merge_coach_profile_fields(athlete_id, parsed_updates)
        log(result="profile_updated", fields="|".join(sorted(parsed_updates.keys())))
        if not update_ok:
            logger.error(
                "athlete_id=%s, from_email=%s, verified=true, result=profile_update_failed%s",
                athlete_id,
                from_email,
                f", aws_request_id={aws_request_id}" if aws_request_id else "",
            )

    manual_snapshot = parse_manual_activity_snapshot_from_email(
        inbound_body, now_epoch=int(time.time())
    )
    if manual_snapshot:
        snapshot_ok = put_manual_activity_snapshot(
            athlete_id=athlete_id,
            activity_type=manual_snapshot["activity_type"],
            timestamp=manual_snapshot["timestamp"],
            snapshot_event_id=inbound_message_id,
            duration=manual_snapshot.get("duration"),
            key_metric=manual_snapshot.get("key_metric"),
            subjective_feedback=manual_snapshot.get("subjective_feedback"),
            subjective_state=manual_snapshot.get("subjective_state"),
            source="manual",
        )
        if snapshot_ok:
            log(result="manual_snapshot_stored", activity_type=manual_snapshot["activity_type"])
        else:
            logger.error(
                "athlete_id=%s, from_email=%s, verified=true, result=manual_snapshot_store_failed%s",
                athlete_id,
                from_email,
                f", aws_request_id={aws_request_id}" if aws_request_id else "",
            )

    profile_after = get_coach_profile(athlete_id) or profile_before
    missing_after = get_missing_required_profile_fields(profile_after)
    plan_goal = str(profile_after.get("primary_goal", "")).strip() or None
    ensure_current_plan(athlete_id, fallback_goal=plan_goal)
    progress_snapshot = get_progress_snapshot(athlete_id)
    if progress_snapshot is None:
        logger.error(
            "athlete_id=%s, from_email=%s, verified=true, result=progress_snapshot_load_failed%s",
            athlete_id,
            from_email,
            f", aws_request_id={aws_request_id}" if aws_request_id else "",
        )
    else:
        log(
            result="progress_snapshot_loaded",
            progress_quality=progress_snapshot.get("data_quality"),
        )

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
    reply = EmailCopy.READY_FOR_COACHING_BASE
    connect_link = _build_connect_strava_link(from_email)
    if connect_link:
        reply += EmailCopy.READY_FOR_COACHING_CONNECT_STRAVA.format(
            connect_link=connect_link
        )

    plan_summary = fetch_current_plan_summary(athlete_id)
    if plan_summary:
        reply += f"\n\n{plan_summary}"
    return reply
