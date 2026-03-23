"""Phase helpers for the profile-gated coaching pipeline.

Callers in coaching.py pass explicit callables (get_profile_fn, merge_profile_fn,
etc.) so unit tests can patch symbols on the coaching module and have those
patches apply. Defaults use the real dynamodb/profile/planner implementations.
"""

from __future__ import annotations

import logging
import time
from typing import Any, Callable, Dict, Optional

from activity_snapshot import parse_manual_activity_snapshot_from_email
from ai_extraction_contract import (
    list_missing_or_low_confidence_critical_fields,
    should_request_clarification,
)
from dynamodb_models import (
    ensure_current_plan,
    get_coach_profile,
    get_progress_snapshot,
    merge_coach_profile_fields,
    put_manual_activity_snapshot,
)
from profile import get_missing_required_profile_fields, parse_profile_updates_from_email
from skills.planner import (
    SessionCheckinExtractionProposalError,
    run_session_checkin_extraction_workflow,
)

logger = logging.getLogger(__name__)


def _type_map(payload: Dict[str, Any]) -> Dict[str, str]:
    return {key: type(value).__name__ for key, value in payload.items()}


def apply_profile_updates_phase(
    *,
    athlete_id: str,
    inbound_body: str,
    from_email: str,
    aws_request_id: Optional[str],
    log: Callable[..., None],
    get_profile_fn: Callable[[str], Optional[Dict[str, Any]]] = get_coach_profile,
    get_missing_fields_fn: Callable[[Dict[str, Any]], list[str]] = get_missing_required_profile_fields,
    parse_updates_fn: Callable[..., Dict[str, Any]] = parse_profile_updates_from_email,
    merge_profile_fn: Callable[[str, Dict[str, Any]], bool] = merge_coach_profile_fields,
) -> tuple[Dict[str, Any], list[str], Dict[str, Any]]:
    profile_before = get_profile_fn(athlete_id) or {}
    missing_before = get_missing_fields_fn(profile_before)
    parsed_updates = parse_updates_fn(
        inbound_body,
        missing_fields=missing_before or None,
    )
    if parsed_updates:
        update_ok = merge_profile_fn(athlete_id, parsed_updates)
        log(result="profile_updated", fields="|".join(sorted(parsed_updates.keys())))
        if not update_ok:
            logger.error(
                "athlete_id=%s, from_email=%s, verified=true, result=profile_update_failed%s",
                athlete_id,
                from_email,
                f", aws_request_id={aws_request_id}" if aws_request_id else "",
            )
    return profile_before, missing_before, parsed_updates


def maybe_extract_profile_gate_checkin_phase(
    *,
    athlete_id: str,
    inbound_body: str,
    log: Callable[..., None],
    run_checkin_extraction_fn: Callable[[str], Dict[str, Any]] = run_session_checkin_extraction_workflow,
    should_clarify_fn: Callable[[Dict[str, Any]], bool] = should_request_clarification,
    list_missing_fn: Callable[[Dict[str, Any]], list[str]] = list_missing_or_low_confidence_critical_fields,
) -> None:
    logger.info(
        "Session check-in extraction starting in profile gate: athlete_id=%s body_chars=%s",
        athlete_id,
        len(str(inbound_body or "")),
    )
    try:
        extracted_checkin = run_checkin_extraction_fn(inbound_body)
        if extracted_checkin:
            needs_clarification = should_clarify_fn(extracted_checkin)
            missing_fields = list_missing_fn(extracted_checkin)
            logger.info(
                "Session check-in extraction completed in profile gate: athlete_id=%s keys=%s field_types=%s clarification_needed=%s missing_or_low=%s",
                athlete_id,
                sorted(extracted_checkin.keys()),
                _type_map(extracted_checkin),
                needs_clarification,
                missing_fields,
            )
            log(
                result="session_checkin_extracted",
                extracted_fields="|".join(sorted(extracted_checkin.keys())),
                clarification_needed=needs_clarification,
            )
            if needs_clarification:
                log(
                    result="session_checkin_clarification_needed",
                    missing_or_low_confidence="|".join(missing_fields),
                )
    except SessionCheckinExtractionProposalError as exc:
        logger.error(
            "Session check-in extraction failed in profile gate: athlete_id=%s error=%s",
            athlete_id,
            exc,
        )
        log(result="session_checkin_extraction_failed")


def maybe_store_manual_snapshot_phase(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_message_id: Optional[str],
    from_email: str,
    aws_request_id: Optional[str],
    log: Callable[..., None],
    parse_snapshot_fn: Callable[[str, int], Optional[Dict[str, Any]]] = parse_manual_activity_snapshot_from_email,
    put_snapshot_fn: Callable[..., bool] = put_manual_activity_snapshot,
) -> Optional[Dict[str, Any]]:
    manual_snapshot = parse_snapshot_fn(inbound_body, int(time.time()))
    if not manual_snapshot:
        return None

    snapshot_ok = put_snapshot_fn(
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
    return manual_snapshot


def load_profile_gate_state_phase(
    *,
    athlete_id: str,
    from_email: str,
    aws_request_id: Optional[str],
    profile_before: Dict[str, Any],
    log: Callable[..., None],
    get_profile_fn: Callable[[str], Optional[Dict[str, Any]]] = get_coach_profile,
    get_missing_fields_fn: Callable[[Dict[str, Any]], list[str]] = get_missing_required_profile_fields,
    ensure_current_plan_fn: Callable[..., bool] = ensure_current_plan,
    get_progress_snapshot_fn: Callable[[str], Optional[Dict[str, Any]]] = get_progress_snapshot,
) -> tuple[Dict[str, Any], list[str]]:
    profile_after = get_profile_fn(athlete_id) or profile_before
    missing_after = get_missing_fields_fn(profile_after)
    plan_goal = str(profile_after.get("primary_goal", "")).strip() or None
    ensure_current_plan_fn(athlete_id, fallback_goal=plan_goal)
    progress_snapshot = get_progress_snapshot_fn(athlete_id)
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
    return profile_after, missing_after
