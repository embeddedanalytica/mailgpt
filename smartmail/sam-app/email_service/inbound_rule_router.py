"""Business-layer routing for inbound coaching emails.

The legacy deterministic rule engine is intentionally not part of the
authoritative request path. This router now performs only broad mode
selection plus optional clarification/extraction telemetry.
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, Optional

try:  # pragma: no cover - import style depends on runner context
    from .ai_extraction_contract import list_missing_or_low_confidence_critical_fields
    from .skills.planner import (
        SessionCheckinExtractionProposalError,
        run_session_checkin_extraction_workflow,
    )
except ImportError:  # pragma: no cover
    from ai_extraction_contract import list_missing_or_low_confidence_critical_fields
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


_ACTION_MODE_MAP = {
    "plan_update": "mutate",
    "answer_question": "read_only",
    "checkin_ack": "read_only",
    "clarify_only": "read_only",
}


def _mode_for_intent(
    intent: str,
    clarification_needed: bool,
    has_extracted_checkin: bool,
    requested_action: str = "",
) -> str:
    if intent in _SPECIAL_INTENT_BEHAVIOR:
        return _SPECIAL_INTENT_BEHAVIOR[intent]["mode"]
    if clarification_needed:
        return "skip"
    # requested_action is the primary routing signal when present
    action_mode = _ACTION_MODE_MAP.get(requested_action)
    if action_mode is not None:
        return action_mode
    # Fallback to intent-based routing (backward compat / missing field)
    if intent in _MUTATE_INTENTS:
        return "mutate"
    if intent in _READ_ONLY_INTENTS:
        return "read_only"
    return "skip"


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
    requested_action = str(conversation_intelligence.get("requested_action", "")).strip().lower()
    brevity_preference = str(conversation_intelligence.get("brevity_preference", "normal")).strip().lower()
    decision = _base_decision(intent)
    decision["requested_action"] = requested_action or None
    decision["brevity_preference"] = brevity_preference or "normal"
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
    decision["mode"] = _mode_for_intent(intent, clarification_needed, bool(extracted_checkin), requested_action)
    if decision["mode"] == "skip" and clarification_needed:
        decision["rule_engine_status"] = "clarification_needed"
        decision["reply_strategy"] = "clarification"
    else:
        decision["rule_engine_status"] = "inactive"

    _log_router_decision(
        decision=decision,
        from_email=from_email,
        aws_request_id=aws_request_id,
        log_outcome=log_outcome,
    )
    return decision
