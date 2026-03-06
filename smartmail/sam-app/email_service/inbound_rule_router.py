"""Business-layer rule-engine routing for inbound coaching emails."""

from __future__ import annotations

from datetime import date
from typing import Any, Callable, Dict, Optional

try:  # pragma: no cover - import style depends on runner context
    from .ai_extraction_contract import list_missing_or_low_confidence_critical_fields
    from .dynamodb_models import get_coach_profile
    from .openai_responder import SessionCheckinExtractionError, SessionCheckinExtractor
    from .rule_engine_orchestrator import (
        RuleEngineOrchestratorError,
        apply_rule_engine_plan_update,
        run_rule_engine_for_week,
    )
except ImportError:  # pragma: no cover
    from ai_extraction_contract import list_missing_or_low_confidence_critical_fields
    from dynamodb_models import get_coach_profile
    from openai_responder import SessionCheckinExtractionError, SessionCheckinExtractor
    from rule_engine_orchestrator import (
        RuleEngineOrchestratorError,
        apply_rule_engine_plan_update,
        run_rule_engine_for_week,
    )

_MUTATE_INTENTS = {"check_in", "plan_change_request", "availability_update"}
_READ_ONLY_INTENTS = {"question", "milestone_update"}
_SPECIAL_INTENT_BEHAVIOR = {
    "off_topic": {
        "mode": "skip",
        "reply_strategy": "off_topic",
        "rule_engine_status": "not_applicable",
    },
    "safety_concern": {
        "mode": "skip",
        "reply_strategy": "safety_concern",
        "rule_engine_status": "not_applicable_safety",
    },
}


class InboundRuleRouterError(ValueError):
    """Raised when router inputs are invalid."""


def _type_map(payload: Dict[str, Any]) -> Dict[str, str]:
    return {key: type(value).__name__ for key, value in payload.items()}


def _logical_request_id(message_id: Optional[str], intent: str) -> str:
    normalized_id = str(message_id or "").strip()
    if normalized_id:
        return f"rule_engine:{intent}:{normalized_id[:120]}"
    return f"rule_engine:{intent}:no_message_id"


def _base_decision(intent: str) -> Dict[str, Any]:
    return {
        "intent": intent,
        "rule_engine_ran": False,
        "mode": "skip",
        "engine_output": None,
        "plan_update_result": None,
        "clarification_needed": False,
        "reply_strategy": "standard",
        "rule_engine_status": "not_applicable",
        "missing_or_low_confidence": [],
    }


def _mode_for_intent(intent: str, clarification_needed: bool, has_extracted_checkin: bool) -> str:
    if intent in _SPECIAL_INTENT_BEHAVIOR:
        return _SPECIAL_INTENT_BEHAVIOR[intent]["mode"]
    if clarification_needed or not has_extracted_checkin:
        return "skip"
    if intent in _MUTATE_INTENTS:
        return "mutate"
    if intent in _READ_ONLY_INTENTS:
        return "read_only"
    return "skip"


def _enrich_checkin_payload(extracted: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(extracted)
    if "week_start" not in payload:
        payload["week_start"] = date.today().strftime("%Y-%m-%d")
    if "time_bucket" not in payload and profile.get("time_bucket"):
        payload["time_bucket"] = profile.get("time_bucket")
    if "main_sport_current" not in payload and profile.get("main_sport_current"):
        payload["main_sport_current"] = profile.get("main_sport_current")
    if "schedule_variability" not in payload and profile.get("schedule_variability"):
        payload["schedule_variability"] = profile.get("schedule_variability")
    if "has_upcoming_event" not in payload:
        payload["has_upcoming_event"] = None
    return payload


def _log_router_decision(
    *,
    decision: Dict[str, Any],
    from_email: str,
    aws_request_id: Optional[str],
    log_outcome: Optional[Callable[..., None]],
) -> None:
    if log_outcome is None:
        return
    engine_output = decision.get("engine_output") or {}
    plan_update_result = decision.get("plan_update_result") or {}
    log_outcome(
        from_email=from_email,
        verified=True,
        result="rule_engine_routed",
        aws_request_id=aws_request_id,
        intent=decision["intent"],
        rule_engine_mode=decision["mode"],
        rule_engine_status=decision["rule_engine_status"],
        plan_update_status=engine_output.get("plan_update_status"),
        plan_update_result_status=plan_update_result.get("status"),
        clarification_needed=decision["clarification_needed"],
    )


def route_inbound_with_rule_engine(
    athlete_id: str,
    from_email: str,
    email_data: Dict[str, Any],
    conversation_intelligence: Dict[str, Any],
    *,
    aws_request_id: Optional[str] = None,
    log_outcome: Optional[Callable[..., None]] = None,
) -> Dict[str, Any]:
    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise InboundRuleRouterError("athlete_id must be a non-empty string")
    if not isinstance(from_email, str) or not from_email.strip():
        raise InboundRuleRouterError("from_email must be a non-empty string")
    if not isinstance(email_data, dict):
        raise InboundRuleRouterError("email_data must be a dict")
    if not isinstance(conversation_intelligence, dict):
        raise InboundRuleRouterError("conversation_intelligence must be a dict")

    intent = str(conversation_intelligence.get("intent", "off_topic")).strip().lower() or "off_topic"
    decision = _base_decision(intent)
    special_behavior = _SPECIAL_INTENT_BEHAVIOR.get(intent)
    if special_behavior is not None:
        decision.update(special_behavior)
        _log_router_decision(
            decision=decision,
            from_email=from_email,
            aws_request_id=aws_request_id,
            log_outcome=log_outcome,
        )
        return decision

    inbound_body = str(email_data.get("body", ""))
    inbound_message_id = str(email_data.get("message_id", "")).strip() or None
    profile = get_coach_profile(athlete_id) or {}

    extracted_checkin: Dict[str, Any] = {}
    extraction_failed = False
    missing_or_low: list[str] = []
    if log_outcome is not None:
        log_outcome(
            from_email=from_email,
            verified=True,
            result="session_checkin_extraction_started",
            aws_request_id=aws_request_id,
            intent=intent,
            body_chars=len(inbound_body),
        )
    try:
        extracted_checkin = SessionCheckinExtractor.extract_session_checkin_fields(inbound_body)
        if extracted_checkin:
            missing_or_low = list_missing_or_low_confidence_critical_fields(extracted_checkin)
            if log_outcome is not None:
                log_outcome(
                    from_email=from_email,
                    verified=True,
                    result="session_checkin_extraction_parsed",
                    aws_request_id=aws_request_id,
                    intent=intent,
                    extracted_fields="|".join(sorted(extracted_checkin.keys())),
                    extracted_field_types="|".join(
                        f"{k}:{v}" for k, v in sorted(_type_map(extracted_checkin).items())
                    ),
                    missing_or_low_confidence="|".join(missing_or_low),
                )
    except SessionCheckinExtractionError:
        extraction_failed = True
        if log_outcome is not None:
            log_outcome(
                from_email=from_email,
                verified=True,
                result="session_checkin_extraction_failed",
                aws_request_id=aws_request_id,
                intent=intent,
            )

    clarification_needed = extraction_failed or bool(missing_or_low)
    decision["clarification_needed"] = clarification_needed
    decision["missing_or_low_confidence"] = list(missing_or_low)
    decision["mode"] = _mode_for_intent(intent, clarification_needed, bool(extracted_checkin))
    if decision["mode"] == "skip" and clarification_needed:
        decision["rule_engine_status"] = "clarification_needed"
        decision["reply_strategy"] = "clarification"

    if decision["mode"] in {"mutate", "read_only"}:
        checkin_payload = _enrich_checkin_payload(extracted_checkin, profile)
        try:
            engine_output = run_rule_engine_for_week(
                athlete_id=athlete_id,
                profile=profile,
                checkin=checkin_payload,
                today_date=date.today(),
                persist_state=(decision["mode"] == "mutate"),
            )
            decision["engine_output"] = engine_output.to_dict()
            decision["rule_engine_ran"] = True
            decision["reply_strategy"] = "rule_engine_guided"
            decision["rule_engine_status"] = "ok"

            if decision["mode"] == "mutate":
                if decision["engine_output"].get("plan_update_status") == "updated":
                    plan_update_result = apply_rule_engine_plan_update(
                        athlete_id=athlete_id,
                        engine_output=engine_output,
                        logical_request_id=_logical_request_id(inbound_message_id, intent),
                    )
                    decision["plan_update_result"] = plan_update_result
                else:
                    decision["plan_update_result"] = {
                        "status": "skipped",
                        "plan_version": None,
                        "error_code": None,
                    }
        except RuleEngineOrchestratorError:
            decision["rule_engine_status"] = "orchestrator_error"
            decision["reply_strategy"] = "clarification"
            decision["clarification_needed"] = True

    _log_router_decision(
        decision=decision,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log_outcome=log_outcome,
    )
    return decision
