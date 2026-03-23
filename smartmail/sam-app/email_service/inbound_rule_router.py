"""Business-layer rule-engine routing for inbound coaching emails."""

from __future__ import annotations

import logging
from datetime import date
from typing import Any, Callable, Dict, Optional

try:  # pragma: no cover - import style depends on runner context
    from .ai_extraction_contract import list_missing_or_low_confidence_critical_fields
    from .dynamodb_models import get_coach_profile
    from .rule_engine_orchestrator import (
        RuleEngineOrchestratorError,
        apply_rule_engine_plan_update,
        run_rule_engine_for_week,
    )
    from .skills.planner import (
        SessionCheckinExtractionProposalError,
        run_session_checkin_extraction_workflow,
    )
except ImportError:  # pragma: no cover
    from ai_extraction_contract import list_missing_or_low_confidence_critical_fields
    from dynamodb_models import get_coach_profile
    from rule_engine_orchestrator import (
        RuleEngineOrchestratorError,
        apply_rule_engine_plan_update,
        run_rule_engine_for_week,
    )
    from skills.planner import (
        SessionCheckinExtractionProposalError,
        run_session_checkin_extraction_workflow,
    )

_MUTATE_INTENTS = {"coaching"}
_READ_ONLY_INTENTS = {"question"}
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

logger = logging.getLogger(__name__)


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
    if clarification_needed:
        return "skip"
    if intent in _MUTATE_INTENTS:
        return "mutate"
    if intent in _READ_ONLY_INTENTS:
        return "read_only"
    return "skip"


def _enrich_checkin_payload(extracted: Dict[str, Any], profile: Dict[str, Any]) -> Dict[str, Any]:
    payload = dict(extracted)
    injected_fields: list[str] = []
    if "week_start" not in payload:
        payload["week_start"] = date.today().strftime("%Y-%m-%d")
    if "time_bucket" not in payload and profile.get("time_bucket"):
        payload["time_bucket"] = profile.get("time_bucket")
        injected_fields.append("time_bucket")
    if "main_sport_current" not in payload and profile.get("main_sport_current"):
        payload["main_sport_current"] = profile.get("main_sport_current")
        injected_fields.append("main_sport_current")
    if "schedule_variability" not in payload and profile.get("schedule_variability"):
        payload["schedule_variability"] = profile.get("schedule_variability")
        injected_fields.append("schedule_variability")
    if "experience_level" not in payload and profile.get("experience_level"):
        payload["experience_level"] = profile.get("experience_level")
        injected_fields.append("experience_level")
    if "structure_preference" not in payload and profile.get("structure_preference"):
        payload["structure_preference"] = profile.get("structure_preference")
        injected_fields.append("structure_preference")
    if "days_available" not in payload:
        time_availability = profile.get("time_availability")
        if isinstance(time_availability, dict):
            sessions_per_week = time_availability.get("sessions_per_week")
            if isinstance(sessions_per_week, int):
                payload["days_available"] = sessions_per_week
                injected_fields.append("days_available")
    if injected_fields:
        logger.info(
            "Rule-engine payload backfilled from profile: injected_fields=%s",
            "|".join(injected_fields),
        )
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


def _extract_checkin_for_routing(
    *,
    inbound_body: str,
    intent: str,
    from_email: str,
    aws_request_id: Optional[str],
    log_outcome: Optional[Callable[..., None]],
) -> tuple[Dict[str, Any], bool, list[str]]:
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
        extracted_checkin = run_session_checkin_extraction_workflow(inbound_body)
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
    except SessionCheckinExtractionProposalError:
        extraction_failed = True
        if log_outcome is not None:
            log_outcome(
                from_email=from_email,
                verified=True,
                result="session_checkin_extraction_failed",
                aws_request_id=aws_request_id,
                intent=intent,
            )
    return extracted_checkin, extraction_failed, missing_or_low


def _run_rule_engine_route(
    *,
    decision: Dict[str, Any],
    athlete_id: str,
    profile: Dict[str, Any],
    extracted_checkin: Dict[str, Any],
    inbound_message_id: Optional[str],
    intent: str,
) -> None:
    checkin_payload = _enrich_checkin_payload(extracted_checkin, profile)
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

    intent = str(conversation_intelligence.get("intent", "coaching")).strip().lower() or "coaching"
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

    extracted_checkin, extraction_failed, missing_or_low = _extract_checkin_for_routing(
        inbound_body=inbound_body,
        intent=intent,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log_outcome=log_outcome,
    )

    clarification_needed = extraction_failed
    decision["clarification_needed"] = clarification_needed
    decision["missing_or_low_confidence"] = list(missing_or_low)
    decision["mode"] = _mode_for_intent(intent, clarification_needed, bool(extracted_checkin))
    if decision["mode"] == "skip" and clarification_needed:
        decision["rule_engine_status"] = "clarification_needed"
        decision["reply_strategy"] = "clarification"

    if decision["mode"] in {"mutate", "read_only"}:
        try:
            _run_rule_engine_route(
                decision=decision,
                athlete_id=athlete_id,
                profile=profile,
                extracted_checkin=extracted_checkin,
                inbound_message_id=inbound_message_id,
                intent=intent,
            )
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
