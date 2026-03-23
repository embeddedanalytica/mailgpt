"""
Profile-gated coaching flow: apply profile updates from email and decide reply.
Business logic only; auth/verification/rate limits are handled by the handler.
"""
import logging
import json
from typing import Optional, Dict, Any, Callable

from dynamodb_models import (
    get_coach_profile,
    merge_coach_profile_fields,
    ensure_current_plan,
    fetch_current_plan_summary,
    get_memory_notes,
    get_continuity_summary,
    get_memory_context_for_response_generation,
    replace_memory,
    create_action_token,
    put_manual_activity_snapshot,
    get_progress_snapshot,
)
from config import ACTION_BASE_URL
from activity_snapshot import parse_manual_activity_snapshot_from_email
from ai_extraction_contract import (
    list_missing_or_low_confidence_critical_fields,
    should_request_clarification,
)
from coaching_phases import (
    apply_profile_updates_phase,
    load_profile_gate_state_phase,
    maybe_extract_profile_gate_checkin_phase,
    maybe_store_manual_snapshot_phase,
)
from profile import (
    parse_profile_updates_from_email,
    get_missing_required_profile_fields,
)
from config import ENABLE_COACHING_REASONING, ENABLE_SESSION_CHECKIN_EXTRACTION
from rule_engine import RuleEngineContractError, validate_rule_engine_output
from skills.planner import (
    SessionCheckinExtractionProposalError,
    run_session_checkin_extraction_workflow,
)
from coaching_memory import (
    maybe_post_reply_memory_refresh,
    should_attempt_memory_refresh,
)
from response_generation_contract import normalize_reply_mode
from response_generation_assembly import build_response_brief, build_response_generation_input
from skills.coaching_reasoning import CoachingReasoningError, run_coaching_reasoning_workflow
from skills.response_generation import (
    ResponseGenerationProposalError,
    run_response_generation_workflow,
)

logger = logging.getLogger(__name__)
_READ_ONLY_REPLY_INTENTS = {"question"}


def _missing_injury_only(missing_profile_fields: list[str]) -> bool:
    return set(missing_profile_fields) == {"injury_status"}


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
    if not isinstance(rule_engine_decision, dict):
        if missing_profile_fields:
            return normalize_reply_mode("intake")
        return normalize_reply_mode("normal_coaching")

    reply_strategy = str(rule_engine_decision.get("reply_strategy", "")).strip().lower()
    if reply_strategy == "safety_concern":
        return normalize_reply_mode("safety_risk_managed")
    if reply_strategy == "off_topic":
        return normalize_reply_mode("off_topic_redirect")
    if reply_strategy == "clarification" or bool(rule_engine_decision.get("clarification_needed")):
        return normalize_reply_mode("clarification")

    intent = str(rule_engine_decision.get("intent", "")).strip().lower()
    if intent in _READ_ONLY_REPLY_INTENTS and _missing_injury_only(missing_profile_fields):
        return normalize_reply_mode("lightweight_non_planning")
    if missing_profile_fields:
        return normalize_reply_mode("intake")
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
    intake_just_completed: bool = False,
) -> Optional[str]:
    reply_mode = _resolve_reply_mode(
        missing_profile_fields=missing_profile_fields,
        rule_engine_decision=rule_engine_decision,
    )
    memory_refresh_reply_kind = "profile_incomplete" if missing_profile_fields else reply_mode

    memory_context = get_memory_context_for_response_generation(athlete_id)
    response_brief = build_response_brief(
        athlete_id=athlete_id,
        reply_kind=reply_mode,
        inbound_subject=inbound_subject,
        inbound_body=inbound_body,
        selected_model_name=selected_model_name,
        profile_after=profile_after,
        missing_profile_fields=missing_profile_fields,
        plan_summary=plan_summary,
        rule_engine_decision=rule_engine_decision,
        memory_context=memory_context,
        connect_strava_link=connect_strava_link,
        intake_completed_this_turn=intake_just_completed and reply_mode == "normal_coaching",
    )
    # Two-stage pipeline: coaching reasoning → response generation (if enabled)
    coaching_result = None
    if ENABLE_COACHING_REASONING:
        try:
            coaching_result = run_coaching_reasoning_workflow(
                response_brief.to_dict(), model_name=selected_model_name,
            )
            logger.info(
                "coaching_directive athlete_id=%s rationale=%s doctrine_files=%s",
                athlete_id,
                coaching_result["directive"].get("rationale", ""),
                coaching_result.get("doctrine_files_loaded", []),
            )
        except CoachingReasoningError as exc:
            logger.warning(
                "coaching_reasoning_fallback athlete_id=%s error=%s", athlete_id, exc,
            )

    if coaching_result is not None:
        rg_input = build_response_generation_input(
            directive=coaching_result["directive"], brief=response_brief,
        )
    else:
        rg_input = response_brief.to_dict()

    try:
        generated_response = run_response_generation_workflow(
            rg_input,
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

    # AM2: single post-reply candidate-operation memory refresh
    maybe_post_reply_memory_refresh(
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
        get_memory_notes_fn=get_memory_notes,
        get_continuity_summary_fn=get_continuity_summary,
        replace_memory_fn=replace_memory,
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


def _apply_profile_updates(
    *,
    athlete_id: str,
    inbound_body: str,
    from_email: str,
    aws_request_id: Optional[str],
    log: Callable[..., None],
) -> tuple[Dict[str, Any], list[str], Dict[str, Any]]:
    return apply_profile_updates_phase(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log=log,
        get_profile_fn=get_coach_profile,
        get_missing_fields_fn=get_missing_required_profile_fields,
        parse_updates_fn=parse_profile_updates_from_email,
        merge_profile_fn=merge_coach_profile_fields,
    )


def _maybe_extract_profile_gate_checkin(
    *,
    athlete_id: str,
    inbound_body: str,
    log: Callable[..., None],
) -> None:
    if not ENABLE_SESSION_CHECKIN_EXTRACTION:
        return
    maybe_extract_profile_gate_checkin_phase(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        log=log,
        run_checkin_extraction_fn=run_session_checkin_extraction_workflow,
        should_clarify_fn=should_request_clarification,
        list_missing_fn=list_missing_or_low_confidence_critical_fields,
    )


def _maybe_store_manual_snapshot(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_message_id: Optional[str],
    from_email: str,
    aws_request_id: Optional[str],
    log: Callable[..., None],
) -> Optional[Dict[str, Any]]:
    return maybe_store_manual_snapshot_phase(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        inbound_message_id=inbound_message_id,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log=log,
        parse_snapshot_fn=parse_manual_activity_snapshot_from_email,
        put_snapshot_fn=put_manual_activity_snapshot,
    )


def _load_profile_gate_state(
    *,
    athlete_id: str,
    from_email: str,
    aws_request_id: Optional[str],
    profile_before: Dict[str, Any],
    log: Callable[..., None],
) -> tuple[Dict[str, Any], list[str]]:
    return load_profile_gate_state_phase(
        athlete_id=athlete_id,
        from_email=from_email,
        aws_request_id=aws_request_id,
        profile_before=profile_before,
        log=log,
        get_profile_fn=get_coach_profile,
        get_missing_fields_fn=get_missing_required_profile_fields,
        ensure_current_plan_fn=ensure_current_plan,
        get_progress_snapshot_fn=get_progress_snapshot,
    )


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

    intake_just_completed = bool(missing_before and not missing_after)

    if missing_after:
        log(
            result="profile_missing_context",
            missing_fields="|".join(missing_after),
            missing_count=len(missing_after),
        )
        if not selected_model_name:
            logger.error("selected_model_name is required for profile-gated athlete replies")
            return None
        reply = _generate_llm_reply(
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
        return reply

    if intake_just_completed:
        log(result="intake_completed")

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
        intake_just_completed=intake_just_completed,
    )
