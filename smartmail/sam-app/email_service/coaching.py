"""
Profile-gated coaching flow: apply profile updates from email and decide reply.
Business logic only; auth/verification/rate limits are handled by the handler.
"""
import hashlib
import logging
import json
from typing import Optional, Dict, Any, Callable

from datetime import date

from dynamodb_models import (
    get_coach_profile,
    merge_coach_profile_fields,
    ensure_current_plan,
    fetch_current_plan_summary,
    get_memory_notes,
    get_continuity_summary,
    get_continuity_state,
    get_memory_context_for_response_generation,
    replace_memory,
    update_continuity_state,
    create_action_token,
    put_manual_activity_snapshot,
    get_progress_snapshot,
)
from continuity_state_contract import ContinuityState, ContinuityStateContractError
from continuity_bootstrap import bootstrap_continuity_state
from continuity_recommendation_contract import ContinuityRecommendation, ContinuityRecommendationError
from continuity_updater import apply_continuity_recommendation
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
from skills.planner import (
    SessionCheckinExtractionProposalError,
    run_session_checkin_extraction_workflow,
)
from coaching_memory import (
    maybe_post_reply_memory_refresh,
    should_attempt_memory_refresh,
)
from rule_engine_orchestrator import (
    RuleEngineOrchestratorError,
    apply_rule_engine_plan_update,
    run_rule_engine_for_week,
)
from response_generation_contract import normalize_reply_mode
from response_generation_assembly import build_response_brief, build_response_generation_input
from skills.coaching_reasoning import CoachingReasoningError, run_coaching_reasoning_workflow
from skills.response_generation import (
    ResponseGenerationProposalError,
    run_response_generation_workflow,
)
from skills.obedience_eval import run_obedience_eval
from config import LIGHTWEIGHT_RESPONSE_MODEL
import skills.runtime as skill_runtime

logger = logging.getLogger(__name__)
_READ_ONLY_REPLY_INTENTS = {"question"}
_LIGHTWEIGHT_ACTIONS = {"checkin_ack", "clarify_only"}
_QUICK_REPLY_ACTIONS = {"checkin_ack"}
SUPPRESSED_REPLY = object()

# Last obedience eval result — set after each response generation for observability.
# Consumers (e.g. live_athlete_sim_runner) can read this after each turn.
last_obedience_eval_result: Optional[Dict[str, Any]] = None

# Pipeline trace — captures strategist/writer inputs and outputs for observability.
last_pipeline_trace: Optional[Dict[str, Any]] = None


_QUICK_REPLY_SCHEMA_NAME = "quick_reply"
_QUICK_REPLY_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["reply"],
    "properties": {
        "reply": {"type": "string", "minLength": 1},
    },
}


def _build_quick_reply_avoid_list(
    memory_context: Optional[Dict[str, Any]],
    profile_after: Dict[str, Any],
) -> list[str]:
    """Build an avoid list from memory facts and profile constraints for the quick-reply path."""
    avoid: list[str] = []
    # Inactive injury constraints (athlete asked not to mention)
    for ic in profile_after.get("injury_constraints") or []:
        if not ic.get("active", True):
            summary = str(ic.get("summary", "")).strip()
            if summary:
                avoid.append(summary)
    # Contradicted facts from memory
    if isinstance(memory_context, dict):
        for fact in memory_context.get("contradicted_facts") or []:
            if isinstance(fact, str) and fact.strip():
                avoid.append(fact.strip())
    return avoid


def _generate_quick_reply(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_subject: Optional[str],
    memory_context: Optional[Dict[str, Any]],
    profile_after: Dict[str, Any],
    continuity_context: Optional[Dict[str, Any]],
) -> Optional[str]:
    """Generate a 1-sentence reply for simple ack/confirmation messages.

    Skips the full strategist + response-generation pipeline. Uses a minimal
    prompt with a lightweight model. Returns None on failure so the caller
    can fall through to the full pipeline.
    """
    avoid = _build_quick_reply_avoid_list(memory_context, profile_after)
    avoid_section = ""
    if avoid:
        items = "\n".join(f"- {a}" for a in avoid)
        avoid_section = f"\n\nDo NOT mention or reference:\n{items}"

    system_prompt = (
        "You answer a person's message in no more than 1 short sentence."
        " Be direct and helpful. Do not ask follow-up questions."
        " Do not give coaching advice, plans, or suggestions."
        f"{avoid_section}"
    )

    user_content = inbound_body
    if inbound_subject:
        user_content = f"Subject: {inbound_subject}\n\n{inbound_body}"

    try:
        payload, _ = skill_runtime.execute_json_schema(
            logger=logger,
            model_name=LIGHTWEIGHT_RESPONSE_MODEL,
            system_prompt=system_prompt,
            user_content=user_content,
            schema_name=_QUICK_REPLY_SCHEMA_NAME,
            schema=_QUICK_REPLY_SCHEMA,
            disabled_message="live quick-reply LLM calls are disabled",
            warning_log_name="quick_reply",
            retries=1,
        )
        reply = str(payload.get("reply", "")).strip()
        if not reply:
            return None
        logger.info(
            "quick_reply_generated athlete_id=%s reply_len=%d",
            athlete_id, len(reply),
        )
        return reply
    except Exception as exc:
        logger.warning(
            "quick_reply_failed athlete_id=%s error=%s — falling through to full pipeline",
            athlete_id, exc,
        )
        return None


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


def _build_logical_request_id(
    inbound_message_id: Optional[str],
    inbound_body: str,
) -> str:
    message_id = str(inbound_message_id or "").strip()
    if message_id:
        return f"reply_mutation:{message_id[:256]}"
    body_digest = hashlib.sha256(str(inbound_body or "").encode("utf-8")).hexdigest()[:24]
    return f"reply_mutation:bodyhash:{body_digest}"


def _maybe_apply_rule_engine_mutation(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_message_id: Optional[str],
    profile_after: Dict[str, Any],
    rule_engine_decision: Optional[Dict[str, Any]],
    effective_today: Optional[date],
    log: Callable[..., None],
) -> Optional[Dict[str, Any]]:
    if not isinstance(rule_engine_decision, dict):
        return rule_engine_decision
    if str(rule_engine_decision.get("mode", "")).strip().lower() != "mutate":
        return rule_engine_decision
    if bool(rule_engine_decision.get("clarification_needed")):
        return rule_engine_decision

    try:
        extracted_checkin = run_session_checkin_extraction_workflow(inbound_body)
    except SessionCheckinExtractionProposalError as exc:
        logger.warning(
            "rule_engine_mutation_extraction_failed athlete_id=%s error=%s",
            athlete_id,
            exc,
        )
        log(result="rule_engine_mutation_extraction_failed")
        return dict(rule_engine_decision)

    if not extracted_checkin:
        logger.info("rule_engine_mutation_skipped_empty_checkin athlete_id=%s", athlete_id)
        log(result="rule_engine_mutation_skipped_empty_checkin")
        return dict(rule_engine_decision)

    try:
        engine_output = run_rule_engine_for_week(
            athlete_id=athlete_id,
            profile=profile_after,
            checkin=extracted_checkin,
            today_date=effective_today or date.today(),
            memory_notes=get_memory_notes(athlete_id),
        )
        plan_update_result = apply_rule_engine_plan_update(
            athlete_id=athlete_id,
            engine_output=engine_output,
            logical_request_id=_build_logical_request_id(inbound_message_id, inbound_body),
        )
    except RuleEngineOrchestratorError as exc:
        logger.error("rule_engine_mutation_failed athlete_id=%s error=%s", athlete_id, exc)
        log(result="rule_engine_mutation_failed", error_code="rule_engine_orchestrator_error")
        return dict(rule_engine_decision)

    mutated_decision = dict(rule_engine_decision)
    mutated_decision["rule_engine_ran"] = True
    mutated_decision["engine_output"] = engine_output.to_dict()
    mutated_decision["plan_update_result"] = plan_update_result
    mutated_decision["rule_engine_status"] = (
        str(plan_update_result.get("status", "")).strip().lower() or "completed"
    )
    log(
        result="rule_engine_mutation_applied",
        plan_update_status=engine_output.plan_update_status,
        plan_update_result_status=plan_update_result.get("status"),
    )
    return mutated_decision


def _resolve_reply_mode(
    *,
    missing_profile_fields: list[str],
    rule_engine_decision: Optional[Dict[str, Any]],
) -> str:
    if not isinstance(rule_engine_decision, dict):
        if missing_profile_fields:
            return normalize_reply_mode("intake")
        return normalize_reply_mode("normal_coaching")

    intent = str(rule_engine_decision.get("intent", "")).strip().lower()
    if intent == "safety_concern":
        return normalize_reply_mode("safety_risk_managed")
    if intent == "off_topic":
        return normalize_reply_mode("off_topic_redirect")
    if bool(rule_engine_decision.get("clarification_needed")):
        return normalize_reply_mode("clarification")

    requested_action = str(rule_engine_decision.get("requested_action", "")).strip().lower()
    is_lightweight = intent in _READ_ONLY_REPLY_INTENTS or requested_action in _LIGHTWEIGHT_ACTIONS
    if is_lightweight and _missing_injury_only(missing_profile_fields):
        return normalize_reply_mode("lightweight_non_planning")
    if missing_profile_fields:
        return normalize_reply_mode("intake")
    if is_lightweight:
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
    effective_today: Optional[date] = None,
) -> Optional[str]:
    global last_obedience_eval_result, last_pipeline_trace
    last_pipeline_trace = None
    reply_mode = _resolve_reply_mode(
        missing_profile_fields=missing_profile_fields,
        rule_engine_decision=rule_engine_decision,
    )
    memory_refresh_reply_kind = "profile_incomplete" if missing_profile_fields else reply_mode

    memory_context = get_memory_context_for_response_generation(athlete_id)

    # -- Continuity state: load or bootstrap --
    today = effective_today or date.today()
    current_continuity_state = None
    raw_continuity = get_continuity_state(athlete_id)
    if raw_continuity is not None:
        try:
            current_continuity_state = ContinuityState.from_dict(raw_continuity)
        except ContinuityStateContractError as exc:
            logger.warning(
                "continuity_state_invalid athlete_id=%s error=%s — will bootstrap",
                athlete_id, exc,
            )
    if current_continuity_state is None:
        current_continuity_state = bootstrap_continuity_state(
            profile_after, "base", today,
        )
        logger.info(
            "continuity_state_bootstrap athlete_id=%s focus=%s horizon=%s",
            athlete_id,
            current_continuity_state.current_block_focus,
            current_continuity_state.goal_horizon_type,
        )

    current_continuity_context = current_continuity_state.to_continuity_context(today)

    # -- Quick-reply short-circuit for simple ack/confirmation messages --
    requested_action = ""
    if isinstance(rule_engine_decision, dict):
        requested_action = str(rule_engine_decision.get("requested_action", "")).strip().lower()

    if (
        reply_mode == "lightweight_non_planning"
        and requested_action in _QUICK_REPLY_ACTIONS
    ):
        quick_reply = _generate_quick_reply(
            athlete_id=athlete_id,
            inbound_body=inbound_body,
            inbound_subject=inbound_subject,
            memory_context=memory_context,
            profile_after=profile_after,
            continuity_context=current_continuity_context,
        )
        if quick_reply is not None:
            # Build a minimal directive for obedience eval
            quick_directive = {
                "avoid": _build_quick_reply_avoid_list(memory_context, profile_after),
                "content_plan": ["Answer the person's message"],
                "main_message": "Brief acknowledgment",
                "tone": "warm, brief",
            }
            try:
                obedience_result = run_obedience_eval(
                    email_body=quick_reply,
                    directive=quick_directive,
                    continuity_context=current_continuity_context,
                )
                if obedience_result["passed"]:
                    logger.info("quick_reply_obedience_passed athlete_id=%s", athlete_id)
                else:
                    violation_tags = [v["violation_type"] for v in obedience_result["violations"]]
                    logger.warning(
                        "quick_reply_obedience_corrected athlete_id=%s tags=%s",
                        athlete_id, ",".join(violation_tags),
                    )
                    quick_reply = obedience_result["corrected_email_body"]
                last_obedience_eval_result = {
                    "passed": obedience_result["passed"],
                    "violations": obedience_result["violations"],
                    "corrected": not obedience_result["passed"],
                    "original_email_body": quick_reply if not obedience_result["passed"] else None,
                    "reasoning": obedience_result["reasoning"],
                }
            except Exception:
                logger.warning(
                    "quick_reply_obedience_error athlete_id=%s — using original",
                    athlete_id, exc_info=True,
                )
                last_obedience_eval_result = {"passed": None, "error": True}

            # Memory refresh still runs on quick-reply path
            maybe_post_reply_memory_refresh(
                athlete_id=athlete_id,
                inbound_body=inbound_body,
                inbound_subject=inbound_subject,
                reply_text=quick_reply,
                reply_kind=memory_refresh_reply_kind,
                parsed_updates=parsed_updates,
                manual_snapshot=manual_snapshot,
                selected_model_name=selected_model_name,
                rule_engine_decision=None,
                log=log,
                get_memory_notes_fn=get_memory_notes,
                get_continuity_summary_fn=get_continuity_summary,
                replace_memory_fn=replace_memory,
            )
            log(result="quick_reply_sent")
            return quick_reply

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

    # -- Two-stage pipeline: coaching reasoning → response generation --
    coaching_result = None
    next_continuity_state = current_continuity_state
    if ENABLE_COACHING_REASONING:
        try:
            coaching_result = run_coaching_reasoning_workflow(
                response_brief.to_dict(),
                model_name=selected_model_name,
                continuity_context=current_continuity_context,
            )
            logger.info(
                "coaching_directive athlete_id=%s rationale=%s doctrine_files=%s",
                athlete_id,
                coaching_result["directive"].get("rationale", ""),
                coaching_result.get("doctrine_files_loaded", []),
            )

            # Apply continuity recommendation
            raw_rec = coaching_result.get("continuity_recommendation")
            if raw_rec is not None:
                try:
                    rec = ContinuityRecommendation.from_dict(raw_rec)
                    next_continuity_state = apply_continuity_recommendation(
                        current_continuity_state, rec, today,
                    )
                    logger.info(
                        "continuity_update athlete_id=%s action=%s focus=%s phase=%s",
                        athlete_id,
                        raw_rec.get("recommended_transition_action"),
                        next_continuity_state.current_block_focus,
                        next_continuity_state.current_phase,
                    )
                except ContinuityRecommendationError as exc:
                    logger.warning(
                        "continuity_recommendation_invalid athlete_id=%s error=%s",
                        athlete_id, exc,
                    )
        except CoachingReasoningError as exc:
            logger.error(
                "coaching_reasoning_failed athlete_id=%s error=%s", athlete_id, exc,
            )
            return None

    # Build response generation input with NEXT continuity state (post-decision)
    next_continuity_context = next_continuity_state.to_continuity_context(today)

    directive = coaching_result["directive"]
    if directive.get("reply_action") == "suppress":
        if next_continuity_state != current_continuity_state or raw_continuity is None:
            if not update_continuity_state(athlete_id, next_continuity_state.to_dict()):
                logger.error(
                    "continuity_state_persist_failed athlete_id=%s", athlete_id,
                )
        log(result="coach_suppressed_no_reply_needed")
        logger.info(
            "coach_reply_suppressed athlete_id=%s reason=no_reply_needed",
            athlete_id,
        )
        return SUPPRESSED_REPLY

    rg_input = build_response_generation_input(
        directive=directive,
        brief=response_brief,
        continuity_context=next_continuity_context,
    )

    try:
        generated_response = run_response_generation_workflow(
            rg_input,
            model_name=selected_model_name,
        )
        reply = str(generated_response["final_email_body"]).strip()
        if not reply:
            raise ResponseGenerationProposalError("empty_final_email_body")

        last_pipeline_trace = {
            "strategist_input": response_brief.to_dict(),
            "strategist_output": coaching_result["directive"] if coaching_result else None,
            "writer_input": rg_input,
            "writer_output": generated_response,
        }

        # Obedience eval: LLM-based last-line compliance check + correction
        try:
            obedience_result = run_obedience_eval(
                email_body=reply,
                directive=directive,
                continuity_context=next_continuity_context,
            )
            original_reply = reply
            if obedience_result["passed"]:
                logger.info("obedience_eval_passed athlete_id=%s", athlete_id)
            else:
                violation_tags = [v["violation_type"] for v in obedience_result["violations"]]
                logger.warning(
                    "obedience_eval_corrected athlete_id=%s tags=%s reasoning=%s",
                    athlete_id,
                    ",".join(violation_tags),
                    obedience_result["reasoning"],
                )
                reply = obedience_result["corrected_email_body"]
            last_obedience_eval_result = {
                "passed": obedience_result["passed"],
                "violations": obedience_result["violations"],
                "corrected": not obedience_result["passed"],
                "original_email_body": original_reply if not obedience_result["passed"] else None,
                "reasoning": obedience_result["reasoning"],
            }
        except Exception:
            logger.warning("obedience_eval_error athlete_id=%s — using original email", athlete_id, exc_info=True)
            last_obedience_eval_result = {"passed": None, "error": True}

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

    # Persist continuity state (skip write if unchanged)
    if next_continuity_state != current_continuity_state or raw_continuity is None:
        if not update_continuity_state(athlete_id, next_continuity_state.to_dict()):
            logger.error(
                "continuity_state_persist_failed athlete_id=%s", athlete_id,
            )

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
        rule_engine_decision=None,
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
    effective_today: Optional[date] = None,
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
            effective_today=effective_today,
        )
        return reply

    if intake_just_completed:
        log(result="intake_completed")

    rule_engine_decision = _maybe_apply_rule_engine_mutation(
        athlete_id=athlete_id,
        inbound_body=inbound_body,
        inbound_message_id=inbound_message_id,
        profile_after=profile_after,
        rule_engine_decision=rule_engine_decision,
        effective_today=effective_today,
        log=log,
    )

    log(result="profile_ready_for_coaching")
    log(
        result="profile_gate_evaluated",
        missing_before=len(missing_before),
        missing_after=len(missing_after),
    )
    plan_summary = fetch_current_plan_summary(athlete_id)
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
        effective_today=effective_today,
    )
