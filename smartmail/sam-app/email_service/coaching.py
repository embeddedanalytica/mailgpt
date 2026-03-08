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
from openai_responder import OpenAIResponder
from openai_responder import SessionCheckinExtractor, SessionCheckinExtractionError
from ai_extraction_contract import (
    list_missing_or_low_confidence_critical_fields,
    should_request_clarification,
)
from profile import (
    parse_profile_updates_from_email,
    get_missing_required_profile_fields,
    build_profile_collection_reply,
)
from email_copy import EmailCopy
from config import ENABLE_SESSION_CHECKIN_EXTRACTION
from rule_engine import RuleEngineContractError, validate_rule_engine_output

logger = logging.getLogger(__name__)


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


def _render_rule_engine_payload_reply(
    next_email_payload: Dict[str, Any],
    *,
    include_plan_summary: Optional[str] = None,
) -> str:
    subject_hint = str(next_email_payload.get("subject_hint", "")).strip()
    summary = str(next_email_payload.get("summary", "")).strip()
    sessions = [
        str(item).strip()
        for item in next_email_payload.get("sessions", [])
        if str(item).strip()
    ]
    plan_focus_line = str(next_email_payload.get("plan_focus_line", "")).strip()
    technique_cue = str(next_email_payload.get("technique_cue", "")).strip()
    recovery_target = str(next_email_payload.get("recovery_target", "")).strip()
    if_then_rules = [
        str(item).strip()
        for item in next_email_payload.get("if_then_rules", [])
        if str(item).strip()
    ]
    disclaimer_short = str(next_email_payload.get("disclaimer_short", "")).strip()
    safety_note = str(next_email_payload.get("safety_note", "")).strip()

    lines = []
    if subject_hint:
        lines.append(subject_hint)
    if summary:
        lines.append(summary)
    if include_plan_summary:
        lines.append(include_plan_summary)
    if sessions:
        lines.append("Sessions:")
        lines.extend(f"- {session}" for session in sessions)
    if plan_focus_line:
        lines.append(f"Plan focus: {plan_focus_line}")
    if technique_cue:
        lines.append(f"Technique cue: {technique_cue}")
    if recovery_target:
        lines.append(f"Recovery target: {recovery_target}")
    if if_then_rules:
        lines.append("If-then rules:")
        lines.extend(f"- {rule}" for rule in if_then_rules)
    if safety_note:
        lines.append(f"Safety note: {safety_note}")
    if disclaimer_short:
        lines.append(disclaimer_short)
    return "\n\n".join(lines)


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

    if ENABLE_SESSION_CHECKIN_EXTRACTION:
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

    if isinstance(rule_engine_decision, dict):
        reply_strategy = str(rule_engine_decision.get("reply_strategy", "")).strip()
        if reply_strategy == "safety_concern":
            return EmailCopy.SAFETY_CONCERN_REPLY
        if reply_strategy == "off_topic":
            return EmailCopy.OFF_TOPIC_REDIRECT_REPLY
        if rule_engine_decision.get("clarification_needed"):
            reply += (
                "\n\nBefore I change your plan, I need a clearer weekly check-in "
                "(event date, available days, and pain score)."
            )
        engine_output = rule_engine_decision.get("engine_output")
        if isinstance(engine_output, dict):
            track = str(engine_output.get("track", "")).strip()
            risk_flag = str(engine_output.get("risk_flag", "")).strip()
            plan_update_status = str(engine_output.get("plan_update_status", "")).strip()
            next_email_payload = engine_output.get("next_email_payload")
            if reply_strategy == "rule_engine_guided" and isinstance(next_email_payload, dict):
                try:
                    validate_rule_engine_output(engine_output)
                    return _render_rule_engine_payload_reply(
                        next_email_payload,
                        include_plan_summary=plan_summary,
                    )
                except RuleEngineContractError:
                    logger.error("Invalid rule_engine output supplied to final reply path")
            if track or risk_flag or plan_update_status:
                reply += (
                    "\n\nRule-engine context: "
                    f"track={track or 'n/a'}, risk={risk_flag or 'n/a'}, "
                    f"plan_update_status={plan_update_status or 'n/a'}."
                )

    # LLM-first path: when routing selected a response model, generate coaching reply
    # with current inbound context plus plan summary.
    if selected_model_name:
        llm_subject = str(inbound_subject or "").strip() or "Coaching follow-up"
        llm_body = inbound_body
        if plan_summary:
            llm_body = f"{llm_body}\n\nCurrent plan context:\n{plan_summary}"
        if isinstance(rule_engine_decision, dict):
            llm_body = f"{llm_body}\n\nRule engine decision context:\n{rule_engine_decision}"
        generated = OpenAIResponder.generate_response(
            subject=llm_subject,
            body=llm_body,
            model_name=selected_model_name,
        )
        if generated:
            reply = generated

    return reply
