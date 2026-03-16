"""
Profile-gated coaching flow: apply profile updates from email and decide reply.
Business logic only; auth/verification/rate limits are handled by the handler.
"""
import logging
import json
import time
from typing import Optional, Dict, Any, Callable

from dynamodb_models import (
    get_coach_profile,
    merge_coach_profile_fields,
    ensure_current_plan,
    fetch_current_plan_summary,
    get_memory_notes,
    get_continuity_summary,
    get_memory_context_for_response_generation,
    replace_continuity_summary,
    replace_memory_notes,
    create_action_token,
    put_manual_activity_snapshot,
    get_progress_snapshot,
)
from config import ACTION_BASE_URL
from activity_snapshot import parse_manual_activity_snapshot_from_email
from openai_responder import SessionCheckinExtractor, SessionCheckinExtractionError
from ai_extraction_contract import (
    list_missing_or_low_confidence_critical_fields,
    should_request_clarification,
)
from profile import (
    parse_profile_updates_from_email,
    get_missing_required_profile_fields,
)
from config import ENABLE_SESSION_CHECKIN_EXTRACTION
from rule_engine import RuleEngineContractError, validate_rule_engine_output
from skills.memory import MemoryRefreshError, run_memory_refresh, run_memory_router
from coaching_memory import (
    maybe_post_reply_memory_refresh,
    maybe_pre_reply_memory_refresh,
    should_attempt_memory_refresh,
)
from response_generation_contract import normalize_reply_mode
from response_generation_assembly import build_response_brief
from skills.response_generation import (
    ResponseGenerationProposalError,
    run_response_generation_workflow,
)

logger = logging.getLogger(__name__)
_READ_ONLY_REPLY_INTENTS = {"question", "milestone_update"}


def _type_map(payload: Dict[str, Any]) -> Dict[str, str]:
    return {key: type(value).__name__ for key, value in payload.items()}


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


def _resolve_reply_mode(
    *,
    missing_profile_fields: list[str],
    rule_engine_decision: Optional[Dict[str, Any]],
) -> str:
    if missing_profile_fields:
        return normalize_reply_mode("clarification")
    if not isinstance(rule_engine_decision, dict):
        return normalize_reply_mode("normal_coaching")

    reply_strategy = str(rule_engine_decision.get("reply_strategy", "")).strip().lower()
    if reply_strategy == "safety_concern":
        return normalize_reply_mode("safety_risk_managed")
    if reply_strategy == "off_topic":
        return normalize_reply_mode("off_topic_redirect")
    if reply_strategy == "clarification" or bool(rule_engine_decision.get("clarification_needed")):
        return normalize_reply_mode("clarification")

    intent = str(rule_engine_decision.get("intent", "")).strip().lower()
    if intent in _READ_ONLY_REPLY_INTENTS:
        return normalize_reply_mode("lightweight_non_planning")
    return normalize_reply_mode("normal_coaching")


def _generate_llm_reply(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_subject: Optional[str],
    selected_model_name: str,
    profile_after: Dict[str, Any],
    missing_profile_fields: list[str],
    plan_summary: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    parsed_updates: Dict[str, Any],
    manual_snapshot: Optional[Dict[str, Any]],
    log: Callable[..., None],
    from_email: str,
    inbound_message_id: Optional[str],
    connect_strava_link: Optional[str] = None,
) -> Optional[str]:
    reply_mode = _resolve_reply_mode(
        missing_profile_fields=missing_profile_fields,
        rule_engine_decision=rule_engine_decision,
    )
    memory_refresh_reply_kind = "profile_incomplete" if missing_profile_fields else reply_mode
    pre_reply_refresh_attempted = should_attempt_memory_refresh(
        reply_kind=memory_refresh_reply_kind,
        parsed_updates=parsed_updates,
    )
    if pre_reply_refresh_attempted:
        _maybe_pre_refresh(
            athlete_id=athlete_id,
            inbound_body=inbound_body,
            inbound_subject=inbound_subject,
            reply_kind=memory_refresh_reply_kind,
            parsed_updates=parsed_updates,
            manual_snapshot=manual_snapshot,
            selected_model_name=selected_model_name,
            rule_engine_decision=rule_engine_decision,
            log=log,
        )

    memory_context = get_memory_context_for_response_generation(athlete_id)
    post_reply_refresh_eligible = should_attempt_memory_refresh(
        reply_kind=memory_refresh_reply_kind,
        parsed_updates=parsed_updates,
    )
    response_brief = build_response_brief(
        athlete_id=athlete_id,
        reply_kind=reply_mode,
        inbound_subject=inbound_subject,
        selected_model_name=selected_model_name,
        profile_after=profile_after,
        missing_profile_fields=missing_profile_fields,
        plan_summary=plan_summary,
        rule_engine_decision=rule_engine_decision,
        memory_context=memory_context,
        pre_reply_refresh_attempted=pre_reply_refresh_attempted,
        post_reply_refresh_eligible=post_reply_refresh_eligible,
        connect_strava_link=connect_strava_link,
    )
    try:
        generated_response = run_response_generation_workflow(
            response_brief.to_dict(),
            model_name=selected_model_name,
        )
        reply = str(generated_response["final_email_body"]).strip()
        if not reply:
            raise ResponseGenerationProposalError("empty_final_email_body")
    except ResponseGenerationProposalError as exc:
        _log_response_generation_failure(
            athlete_id=athlete_id,
            from_email=from_email,
            inbound_message_id=inbound_message_id,
            inbound_subject=inbound_subject,
            selected_model_name=selected_model_name,
            reply_mode=reply_mode,
            response_brief=response_brief.to_dict(),
            error_code="response_generation_failed",
            error_detail=str(exc),
        )
        return None

    if post_reply_refresh_eligible:
        _maybe_post_refresh(
            athlete_id=athlete_id,
            inbound_body=inbound_body,
            inbound_subject=inbound_subject,
            reply_text=reply,
            reply_kind=memory_refresh_reply_kind,
            parsed_updates=parsed_updates,
            manual_snapshot=manual_snapshot,
            selected_model_name=selected_model_name,
            rule_engine_decision=rule_engine_decision,
            log=log,
        )
    return reply


def _log_response_generation_failure(
    *,
    athlete_id: str,
    from_email: str,
    inbound_message_id: Optional[str],
    inbound_subject: Optional[str],
    selected_model_name: Optional[str],
    reply_mode: str,
    response_brief: Dict[str, Any],
    error_code: str,
    error_detail: str,
    raw_response_preview: Optional[str] = None,
) -> None:
    logger.error(
        "response_generation_send_suppressed athlete_id=%s from_email=%s inbound_message_id=%s inbound_subject=%s reply_mode=%s selected_model_name=%s error_code=%s error_detail=%s raw_response_preview=%s response_brief=%s",
        athlete_id,
        from_email,
        str(inbound_message_id or "").strip() or "none",
        str(inbound_subject or "").strip() or "none",
        reply_mode,
        str(selected_model_name or "").strip() or "none",
        error_code,
        error_detail,
        str(raw_response_preview or "").strip() or "none",
        json.dumps(response_brief, separators=(",", ":"), sort_keys=True, ensure_ascii=True),
    )


def _maybe_pre_refresh(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_subject: Optional[str],
    reply_kind: str,
    parsed_updates: Dict[str, Any],
    manual_snapshot: Optional[Dict[str, Any]],
    selected_model_name: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    log: Callable[..., None],
) -> None:
    maybe_pre_reply_memory_refresh(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        inbound_subject=inbound_subject,
        reply_kind=reply_kind,
        parsed_updates=parsed_updates,
        manual_snapshot=manual_snapshot,
        selected_model_name=selected_model_name,
        rule_engine_decision=rule_engine_decision,
        log=log,
        run_memory_router_fn=run_memory_router,
        get_memory_notes_fn=get_memory_notes,
        get_continuity_summary_fn=get_continuity_summary,
        run_memory_refresh_fn=run_memory_refresh,
        replace_memory_notes_fn=replace_memory_notes,
    )


def _maybe_post_refresh(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_subject: Optional[str],
    reply_text: str,
    reply_kind: str,
    parsed_updates: Dict[str, Any],
    manual_snapshot: Optional[Dict[str, Any]],
    selected_model_name: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    log: Callable[..., None],
) -> None:
    maybe_post_reply_memory_refresh(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        inbound_subject=inbound_subject,
        reply_text=reply_text,
        reply_kind=reply_kind,
        parsed_updates=parsed_updates,
        manual_snapshot=manual_snapshot,
        selected_model_name=selected_model_name,
        rule_engine_decision=rule_engine_decision,
        log=log,
        run_memory_router_fn=run_memory_router,
        get_memory_notes_fn=get_memory_notes,
        get_continuity_summary_fn=get_continuity_summary,
        run_memory_refresh_fn=run_memory_refresh,
        replace_continuity_summary_fn=replace_continuity_summary,
    )


def _apply_profile_updates(
    *,
    athlete_id: str,
    inbound_body: str,
    from_email: str,
    aws_request_id: Optional[str],
    log: Callable[..., None],
) -> tuple[Dict[str, Any], list[str], Dict[str, Any]]:
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
    return profile_before, missing_before, parsed_updates


def _maybe_extract_profile_gate_checkin(
    *,
    athlete_id: str,
    inbound_body: str,
    log: Callable[..., None],
) -> None:
    if not ENABLE_SESSION_CHECKIN_EXTRACTION:
        return

    logger.info(
        "Session check-in extraction starting in profile gate: athlete_id=%s body_chars=%s",
        athlete_id,
        len(str(inbound_body or "")),
    )
    try:
        extracted_checkin = SessionCheckinExtractor.extract_session_checkin_fields(inbound_body)
        if extracted_checkin:
            needs_clarification = should_request_clarification(extracted_checkin)
            missing_fields = list_missing_or_low_confidence_critical_fields(extracted_checkin)
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
    except SessionCheckinExtractionError as exc:
        logger.error(
            "Session check-in extraction failed in profile gate: athlete_id=%s error=%s",
            athlete_id,
            exc,
        )
        log(result="session_checkin_extraction_failed")


def _maybe_store_manual_snapshot(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_message_id: Optional[str],
    from_email: str,
    aws_request_id: Optional[str],
    log: Callable[..., None],
) -> Optional[Dict[str, Any]]:
    manual_snapshot = parse_manual_activity_snapshot_from_email(
        inbound_body, now_epoch=int(time.time())
    )
    if not manual_snapshot:
        return None

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
    return manual_snapshot


def _load_profile_gate_state(
    *,
    athlete_id: str,
    from_email: str,
    aws_request_id: Optional[str],
    profile_before: Dict[str, Any],
    log: Callable[..., None],
) -> tuple[Dict[str, Any], list[str]]:
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
    return profile_after, missing_after


def build_profile_gated_reply(
    athlete_id: str,
    from_email: str,
    inbound_body: str,
    inbound_message_id: Optional[str] = None,
    inbound_subject: Optional[str] = None,
    selected_model_name: Optional[str] = None,
    rule_engine_decision: Optional[Dict[str, Any]] = None,
    *,
    aws_request_id: Optional[str] = None,
    log_outcome: Optional[Callable[..., None]] = None,
) -> Optional[str]:
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

    profile_before, missing_before, parsed_updates = _apply_profile_updates(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log=log,
    )
    _maybe_extract_profile_gate_checkin(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        log=log,
    )
    manual_snapshot = _maybe_store_manual_snapshot(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        inbound_message_id=inbound_message_id,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log=log,
    )
    profile_after, missing_after = _load_profile_gate_state(
        athlete_id=athlete_id,
        from_email=from_email,
        aws_request_id=aws_request_id,
        profile_before=profile_before,
        log=log,
    )
    connect_link = _build_connect_strava_link(from_email)

    if missing_after:
        log(
            result="profile_missing_context",
            missing_fields="|".join(missing_after),
            missing_count=len(missing_after),
        )
        if not selected_model_name:
            logger.error("selected_model_name is required for profile-gated athlete replies")
            return None
        return _generate_llm_reply(
            athlete_id=athlete_id,
            inbound_body=inbound_body,
            inbound_subject=inbound_subject,
            selected_model_name=selected_model_name,
            profile_after=profile_after,
            missing_profile_fields=missing_after,
            plan_summary=None,
            rule_engine_decision=rule_engine_decision,
            parsed_updates=parsed_updates,
            manual_snapshot=manual_snapshot,
            log=log,
            from_email=from_email,
            inbound_message_id=inbound_message_id,
            connect_strava_link=connect_link,
        )

    log(result="profile_ready_for_coaching")
    log(
        result="profile_gate_evaluated",
        missing_before=len(missing_before),
        missing_after=len(missing_after),
    )
    plan_summary = fetch_current_plan_summary(athlete_id)
    if isinstance(rule_engine_decision, dict):
        engine_output = rule_engine_decision.get("engine_output")
        if isinstance(engine_output, dict):
            try:
                validate_rule_engine_output(engine_output)
            except RuleEngineContractError:
                logger.error("Invalid rule_engine output supplied to final reply path")

    if not selected_model_name:
        logger.error("selected_model_name is required for profile-gated athlete replies")
        return None
    return _generate_llm_reply(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        inbound_subject=inbound_subject,
        selected_model_name=selected_model_name,
        profile_after=profile_after,
        missing_profile_fields=missing_after,
        plan_summary=plan_summary,
        rule_engine_decision=rule_engine_decision,
        parsed_updates=parsed_updates,
        manual_snapshot=manual_snapshot,
        log=log,
        from_email=from_email,
        inbound_message_id=inbound_message_id,
        connect_strava_link=connect_link,
    )
