"""
Canonical contract for bounded athlete-facing response generation inputs.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

from athlete_memory_contract import (
    AthleteMemoryContractError,
    ContinuitySummary,
)


# ---------------------------------------------------------------------------
# Shared contract constants
# ---------------------------------------------------------------------------

ALLOWED_REPLY_MODES = {
    "normal_coaching",
    "clarification",
    "intake",
    "safety_risk_managed",
    "lightweight_non_planning",
    "off_topic_redirect",
}
_REQUIRED_TOP_LEVEL_FIELDS = {
    "reply_mode",
    "athlete_context",
    "decision_context",
    "validated_plan",
    "delivery_context",
    "memory_context",
}
_OPTIONAL_TOP_LEVEL_FIELDS = {
    "continuity_context",
}
_ALLOWED_TOP_LEVEL_FIELDS = _REQUIRED_TOP_LEVEL_FIELDS | _OPTIONAL_TOP_LEVEL_FIELDS
_ATHLETE_CONTEXT_FIELDS = {
    "goal_summary",
    "experience_level",
    "structure_preference",
    "constraints_summary",
    "primary_sport",
}
_DECISION_CONTEXT_FIELDS = {
    "track",
    "phase",
    "risk_flag",
    "today_action",
    "clarification_needed",
    "clarification_questions",
    "missing_profile_fields",
    "plan_update_status",
    "risk_recent_history",
    "weeks_in_coaching",
    "intake_completed_this_turn",
    "brevity_preference",
}
_VALIDATED_PLAN_FIELDS = {
    "weekly_skeleton",
    "planner_rationale",
    "plan_summary",
    "session_guidance",
    "adjustments_or_priorities",
    "if_then_rules",
    "safety_note",
}
_DELIVERY_CONTEXT_FIELDS = {
    "inbound_subject",
    "inbound_body",
    "selected_model_name",
    "response_channel",
    "connect_strava_link",
}
_MEMORY_CONTEXT_FIELDS = {
    "memory_available",
    "priority_facts",
    "structure_facts",
    "context_facts",
    "continuity_summary",
    "continuity_focus",
    "contradicted_facts",
}
_REQUIRED_MEMORY_CONTEXT_FIELDS = {
    "memory_available",
    "continuity_summary",
}
_CURRENT_TO_CANONICAL_REPLY_MODES = {
    "profile_incomplete": "clarification",
    "rule_engine_guided": "normal_coaching",
    "coaching_reply": "normal_coaching",
    "safety_concern": "safety_risk_managed",
    "off_topic": "off_topic_redirect",
    "lightweight_non_planning": "lightweight_non_planning",
}
_REQUIRED_RESPONSE_PAYLOAD_FIELDS = {
    "subject_hint",
    "opening",
    "coach_take",
    "weekly_focus",
    "session_guidance",
    "adjustments_or_priorities",
    "if_then_rules",
    "reply_prompt",
    "safety_note",
    "disclaimer_short",
}
_ALLOWED_FINAL_EMAIL_RESPONSE_FIELDS = {
    "final_email_body",
    "model_name",
}


# ---------------------------------------------------------------------------
# Shared primitives
# ---------------------------------------------------------------------------

class ResponseGenerationContractError(ValueError):
    """Raised when response-generation payloads violate the contract."""


def _require_dict(field_name: str, value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ResponseGenerationContractError(f"{field_name} must be a dict")
    return value


def _require_non_empty_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ResponseGenerationContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_string(field_name: str, value: Any) -> str:
    if not isinstance(value, str):
        raise ResponseGenerationContractError(f"{field_name} must be a string")
    return value.strip()


def _require_bool(field_name: str, value: Any) -> bool:
    if not isinstance(value, bool):
        raise ResponseGenerationContractError(f"{field_name} must be a bool")
    return value


def _require_string_list(field_name: str, value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ResponseGenerationContractError(f"{field_name} must be a list")
    normalized: list[str] = []
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise ResponseGenerationContractError(f"{field_name}[{idx}] must be a string")
        normalized.append(item.strip())
    return normalized


def _require_non_empty_string_list(field_name: str, value: Any) -> list[str]:
    normalized = _require_string_list(field_name, value)
    for idx, item in enumerate(normalized):
        if not item:
            raise ResponseGenerationContractError(
                f"{field_name}[{idx}] must be a non-empty string"
            )
    return normalized


def _validate_allowed_fields(
    *,
    payload: Dict[str, Any],
    allowed_fields: set[str],
    object_name: str,
) -> None:
    extra_fields = sorted(set(payload.keys()) - allowed_fields)
    if extra_fields:
        raise ResponseGenerationContractError(
            f"{object_name} has unknown fields: {', '.join(extra_fields)}"
        )


def normalize_reply_mode(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    canonical = _CURRENT_TO_CANONICAL_REPLY_MODES.get(normalized, normalized)
    if canonical not in ALLOWED_REPLY_MODES:
        raise ResponseGenerationContractError(
            f"reply_mode must be one of {sorted(ALLOWED_REPLY_MODES)}"
        )
    return canonical


# ---------------------------------------------------------------------------
# ResponseBrief validation + model
# ---------------------------------------------------------------------------

def _validate_athlete_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = _require_dict("athlete_context", payload)
    _validate_allowed_fields(
        payload=context,
        allowed_fields=_ATHLETE_CONTEXT_FIELDS,
        object_name="athlete_context",
    )

    normalized: Dict[str, Any] = {}
    for field_name in sorted(_ATHLETE_CONTEXT_FIELDS):
        if field_name in context:
            normalized[field_name] = _require_string(f"athlete_context.{field_name}", context[field_name])
    return normalized


def _validate_decision_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = _require_dict("decision_context", payload)
    _validate_allowed_fields(
        payload=context,
        allowed_fields=_DECISION_CONTEXT_FIELDS,
        object_name="decision_context",
    )

    normalized: Dict[str, Any] = {}
    for field_name in ("track", "phase", "risk_flag", "today_action"):
        if field_name in context:
            normalized[field_name] = _require_string(
                f"decision_context.{field_name}",
                context[field_name],
            )
    if "clarification_needed" in context:
        normalized["clarification_needed"] = _require_bool(
            "decision_context.clarification_needed",
            context["clarification_needed"],
        )
    if "clarification_questions" in context:
        normalized["clarification_questions"] = _require_non_empty_string_list(
            "decision_context.clarification_questions",
            context["clarification_questions"],
        )
    if "missing_profile_fields" in context:
        normalized["missing_profile_fields"] = _require_non_empty_string_list(
            "decision_context.missing_profile_fields",
            context["missing_profile_fields"],
        )
    if "plan_update_status" in context:
        normalized["plan_update_status"] = _require_string(
            "decision_context.plan_update_status",
            context["plan_update_status"],
        )
    if "risk_recent_history" in context:
        normalized["risk_recent_history"] = _require_string_list(
            "decision_context.risk_recent_history",
            context["risk_recent_history"],
        )
    if "weeks_in_coaching" in context:
        val = context["weeks_in_coaching"]
        if not isinstance(val, int) or val < 1:
            raise ResponseGenerationContractError(
                "decision_context.weeks_in_coaching must be a positive integer"
            )
        normalized["weeks_in_coaching"] = val
    if "intake_completed_this_turn" in context:
        normalized["intake_completed_this_turn"] = _require_bool(
            "decision_context.intake_completed_this_turn",
            context["intake_completed_this_turn"],
        )
    if "brevity_preference" in context:
        normalized["brevity_preference"] = _require_string(
            "decision_context.brevity_preference",
            context["brevity_preference"],
        )
    return normalized


def _validate_validated_plan(payload: Dict[str, Any]) -> Dict[str, Any]:
    plan = _require_dict("validated_plan", payload)
    _validate_allowed_fields(
        payload=plan,
        allowed_fields=_VALIDATED_PLAN_FIELDS,
        object_name="validated_plan",
    )

    normalized: Dict[str, Any] = {}
    if "weekly_skeleton" in plan:
        normalized["weekly_skeleton"] = _require_string_list(
            "validated_plan.weekly_skeleton",
            plan["weekly_skeleton"],
        )
    for field_name in ("planner_rationale", "plan_summary", "safety_note"):
        if field_name in plan:
            normalized[field_name] = _require_string(
                f"validated_plan.{field_name}",
                plan[field_name],
            )
    for field_name in ("session_guidance", "adjustments_or_priorities", "if_then_rules"):
        if field_name in plan:
            normalized[field_name] = _require_non_empty_string_list(
                f"validated_plan.{field_name}",
                plan[field_name],
            )
    return normalized


def _validate_delivery_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = _require_dict("delivery_context", payload)
    _validate_allowed_fields(
        payload=context,
        allowed_fields=_DELIVERY_CONTEXT_FIELDS,
        object_name="delivery_context",
    )

    normalized: Dict[str, Any] = {}
    for field_name in (
        "inbound_subject",
        "inbound_body",
        "selected_model_name",
        "response_channel",
        "connect_strava_link",
    ):
        if field_name in context:
            normalized[field_name] = _require_string(
                f"delivery_context.{field_name}",
                context[field_name],
            )
    if "response_channel" not in normalized:
        normalized["response_channel"] = "email"

    return normalized


def _validate_memory_context(payload: Dict[str, Any]) -> Dict[str, Any]:
    context = _require_dict("memory_context", payload)
    _validate_allowed_fields(
        payload=context,
        allowed_fields=_MEMORY_CONTEXT_FIELDS,
        object_name="memory_context",
    )

    missing_fields = sorted(_REQUIRED_MEMORY_CONTEXT_FIELDS - set(context.keys()))
    if missing_fields:
        raise ResponseGenerationContractError(
            f"memory_context is missing required fields: {', '.join(missing_fields)}"
        )

    normalized_memory_available = _require_bool(
        "memory_context.memory_available",
        context["memory_available"],
    )

    # AM2: priority_facts (optional list of summary strings — goals + constraints)
    normalized_priority_facts: list[str] = []
    if "priority_facts" in context:
        raw = context["priority_facts"]
        if not isinstance(raw, list):
            raise ResponseGenerationContractError("memory_context.priority_facts must be a list")
        for idx, item in enumerate(raw):
            if not isinstance(item, str) or not item.strip():
                raise ResponseGenerationContractError(
                    f"memory_context.priority_facts[{idx}] must be a non-empty string"
                )
            normalized_priority_facts.append(item.strip())

    # AM2: structure_facts (optional list of summary strings — schedule)
    normalized_structure_facts: list[str] = []
    if "structure_facts" in context:
        raw = context["structure_facts"]
        if not isinstance(raw, list):
            raise ResponseGenerationContractError("memory_context.structure_facts must be a list")
        for idx, item in enumerate(raw):
            if not isinstance(item, str) or not item.strip():
                raise ResponseGenerationContractError(
                    f"memory_context.structure_facts[{idx}] must be a non-empty string"
                )
            normalized_structure_facts.append(item.strip())

    # AM2: context_facts (optional list of summary strings — preference + other)
    normalized_context_facts: list[str] = []
    if "context_facts" in context:
        raw = context["context_facts"]
        if not isinstance(raw, list):
            raise ResponseGenerationContractError("memory_context.context_facts must be a list")
        for idx, item in enumerate(raw):
            if not isinstance(item, str) or not item.strip():
                raise ResponseGenerationContractError(
                    f"memory_context.context_facts[{idx}] must be a non-empty string"
                )
            normalized_context_facts.append(item.strip())

    # Contradicted durable facts (optional list of strings describing what was superseded)
    normalized_contradicted_facts: list[str] = []
    if "contradicted_facts" in context:
        raw = context["contradicted_facts"]
        if not isinstance(raw, list):
            raise ResponseGenerationContractError("memory_context.contradicted_facts must be a list")
        for idx, item in enumerate(raw):
            if not isinstance(item, str) or not item.strip():
                raise ResponseGenerationContractError(
                    f"memory_context.contradicted_facts[{idx}] must be a non-empty string"
                )
            normalized_contradicted_facts.append(item.strip())

    raw_continuity_summary = context["continuity_summary"]
    normalized_continuity_summary = None
    if raw_continuity_summary is not None:
        try:
            normalized_continuity_summary = ContinuitySummary.from_dict(raw_continuity_summary).to_dict()
        except AthleteMemoryContractError as exc:
            raise ResponseGenerationContractError(
                f"memory_context.continuity_summary invalid: {exc}"
            ) from exc

    normalized_continuity_focus = None
    if "continuity_focus" in context:
        normalized_continuity_focus = _require_non_empty_string(
            "memory_context.continuity_focus",
            context["continuity_focus"],
        )

    if not normalized_memory_available and (
        normalized_priority_facts
        or normalized_structure_facts
        or normalized_context_facts
        or normalized_continuity_summary
        or normalized_continuity_focus
    ):
        raise ResponseGenerationContractError(
            "memory_context.memory_available must be true when memory artifacts are present"
        )

    result: Dict[str, Any] = {
        "memory_available": normalized_memory_available,
        "continuity_summary": normalized_continuity_summary,
    }
    if normalized_priority_facts:
        result["priority_facts"] = normalized_priority_facts
    if normalized_structure_facts:
        result["structure_facts"] = normalized_structure_facts
    if normalized_context_facts:
        result["context_facts"] = normalized_context_facts
    if normalized_continuity_focus:
        result["continuity_focus"] = normalized_continuity_focus
    if normalized_contradicted_facts:
        result["contradicted_facts"] = normalized_contradicted_facts
    return result


def validate_response_brief(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ResponseGenerationContractError("payload must be a dict")

    missing_fields = sorted(_REQUIRED_TOP_LEVEL_FIELDS - set(payload.keys()))
    if missing_fields:
        raise ResponseGenerationContractError(
            f"response_brief is missing required fields: {', '.join(missing_fields)}"
        )

    extra_fields = sorted(set(payload.keys()) - _ALLOWED_TOP_LEVEL_FIELDS)
    if extra_fields:
        raise ResponseGenerationContractError(
            f"response_brief has unknown fields: {', '.join(extra_fields)}"
        )

    normalize_reply_mode(payload["reply_mode"])
    _validate_athlete_context(payload["athlete_context"])
    _validate_decision_context(payload["decision_context"])
    _validate_validated_plan(payload["validated_plan"])
    _validate_delivery_context(payload["delivery_context"])
    _validate_memory_context(payload["memory_context"])


def validate_response_payload(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ResponseGenerationContractError("response_payload must be a dict")

    missing_fields = sorted(_REQUIRED_RESPONSE_PAYLOAD_FIELDS - set(payload.keys()))
    if missing_fields:
        raise ResponseGenerationContractError(
            f"response_payload is missing required fields: {', '.join(missing_fields)}"
        )

    extra_fields = sorted(set(payload.keys()) - _REQUIRED_RESPONSE_PAYLOAD_FIELDS)
    if extra_fields:
        raise ResponseGenerationContractError(
            f"response_payload has unknown fields: {', '.join(extra_fields)}"
        )

    _require_non_empty_string("response_payload.subject_hint", payload["subject_hint"])
    _require_non_empty_string("response_payload.opening", payload["opening"])
    _require_non_empty_string("response_payload.coach_take", payload["coach_take"])
    _require_non_empty_string("response_payload.weekly_focus", payload["weekly_focus"])
    _require_non_empty_string("response_payload.reply_prompt", payload["reply_prompt"])
    _require_non_empty_string("response_payload.safety_note", payload["safety_note"])
    _require_non_empty_string_list(
        "response_payload.session_guidance",
        payload["session_guidance"],
    )
    _require_non_empty_string_list(
        "response_payload.adjustments_or_priorities",
        payload["adjustments_or_priorities"],
    )
    _require_non_empty_string_list(
        "response_payload.if_then_rules",
        payload["if_then_rules"],
    )
    _require_string("response_payload.disclaimer_short", payload["disclaimer_short"])


def validate_final_email_response(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise ResponseGenerationContractError("final_email_response must be a dict")

    missing_fields = ["final_email_body"] if "final_email_body" not in payload else []
    if missing_fields:
        raise ResponseGenerationContractError(
            "final_email_response is missing required fields: final_email_body"
        )

    extra_fields = sorted(set(payload.keys()) - _ALLOWED_FINAL_EMAIL_RESPONSE_FIELDS)
    if extra_fields:
        raise ResponseGenerationContractError(
            f"final_email_response has unknown fields: {', '.join(extra_fields)}"
        )

    _require_non_empty_string(
        "final_email_response.final_email_body",
        payload["final_email_body"],
    )
    if "model_name" in payload:
        _require_non_empty_string("final_email_response.model_name", payload["model_name"])


@dataclass(frozen=True)
class ResponseBrief:
    reply_mode: str
    athlete_context: Dict[str, Any]
    decision_context: Dict[str, Any]
    validated_plan: Dict[str, Any]
    delivery_context: Dict[str, Any]
    memory_context: Dict[str, Any]
    continuity_context: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ResponseBrief":
        validate_response_brief(payload)
        return cls(
            reply_mode=normalize_reply_mode(payload["reply_mode"]),
            athlete_context=_validate_athlete_context(payload["athlete_context"]),
            decision_context=_validate_decision_context(payload["decision_context"]),
            validated_plan=_validate_validated_plan(payload["validated_plan"]),
            delivery_context=_validate_delivery_context(payload["delivery_context"]),
            memory_context=_validate_memory_context(payload["memory_context"]),
            continuity_context=payload.get("continuity_context"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "reply_mode": self.reply_mode,
            "athlete_context": dict(self.athlete_context),
            "decision_context": dict(self.decision_context),
            "validated_plan": dict(self.validated_plan),
            "delivery_context": dict(self.delivery_context),
            "memory_context": dict(self.memory_context),
        }
        if self.continuity_context is not None:
            result["continuity_context"] = dict(self.continuity_context)
        return result


# ---------------------------------------------------------------------------
# ResponsePayload validation + model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ResponsePayload:
    subject_hint: str
    opening: str
    coach_take: str
    weekly_focus: str
    session_guidance: list[str]
    adjustments_or_priorities: list[str]
    if_then_rules: list[str]
    reply_prompt: str
    safety_note: str
    disclaimer_short: str

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "ResponsePayload":
        validate_response_payload(payload)
        return cls(
            subject_hint=_require_non_empty_string(
                "response_payload.subject_hint",
                payload["subject_hint"],
            ),
            opening=_require_non_empty_string(
                "response_payload.opening",
                payload["opening"],
            ),
            coach_take=_require_non_empty_string(
                "response_payload.coach_take",
                payload["coach_take"],
            ),
            weekly_focus=_require_non_empty_string(
                "response_payload.weekly_focus",
                payload["weekly_focus"],
            ),
            session_guidance=_require_non_empty_string_list(
                "response_payload.session_guidance",
                payload["session_guidance"],
            ),
            adjustments_or_priorities=_require_non_empty_string_list(
                "response_payload.adjustments_or_priorities",
                payload["adjustments_or_priorities"],
            ),
            if_then_rules=_require_non_empty_string_list(
                "response_payload.if_then_rules",
                payload["if_then_rules"],
            ),
            reply_prompt=_require_non_empty_string(
                "response_payload.reply_prompt",
                payload["reply_prompt"],
            ),
            safety_note=_require_non_empty_string(
                "response_payload.safety_note",
                payload["safety_note"],
            ),
            disclaimer_short=_require_string(
                "response_payload.disclaimer_short",
                payload["disclaimer_short"],
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "subject_hint": self.subject_hint,
            "opening": self.opening,
            "coach_take": self.coach_take,
            "weekly_focus": self.weekly_focus,
            "session_guidance": list(self.session_guidance),
            "adjustments_or_priorities": list(self.adjustments_or_priorities),
            "if_then_rules": list(self.if_then_rules),
            "reply_prompt": self.reply_prompt,
            "safety_note": self.safety_note,
            "disclaimer_short": self.disclaimer_short,
        }


# ---------------------------------------------------------------------------
# FinalEmailResponse validation + model
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class FinalEmailResponse:
    final_email_body: str
    model_name: str = ""

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "FinalEmailResponse":
        validate_final_email_response(payload)
        return cls(
            final_email_body=_require_non_empty_string(
                "final_email_response.final_email_body",
                payload["final_email_body"],
            ),
            model_name=_require_string(
                "final_email_response.model_name",
                payload.get("model_name", ""),
            ),
        )

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "final_email_body": self.final_email_body,
        }
        if self.model_name:
            payload["model_name"] = self.model_name
        return payload


# ---------------------------------------------------------------------------
# WriterBrief validation + model (directive-guided writer input)
# ---------------------------------------------------------------------------

_WRITER_BRIEF_REQUIRED_FIELDS = {
    "reply_mode",
    "coaching_directive",
    "plan_data",
    "delivery_context",
}
_WRITER_BRIEF_OPTIONAL_FIELDS = {
    "continuity_context",
}
_WRITER_BRIEF_TOP_LEVEL_FIELDS = _WRITER_BRIEF_REQUIRED_FIELDS | _WRITER_BRIEF_OPTIONAL_FIELDS

_COACHING_DIRECTIVE_FIELDS = {
    "opening",
    "main_message",
    "content_plan",
    "avoid",
    "tone",
    "recommend_material",
}


def is_directive_input(payload: Dict[str, Any]) -> bool:
    """Check if a payload is a WriterBrief (directive-guided) vs a ResponseBrief."""
    if not isinstance(payload, dict):
        return False
    keys = set(payload.keys())
    return _WRITER_BRIEF_REQUIRED_FIELDS <= keys <= _WRITER_BRIEF_TOP_LEVEL_FIELDS


def _validate_coaching_directive_for_writer(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate the coaching_directive section of a WriterBrief.

    Note: rationale should already be stripped before reaching the writer.
    """
    directive = _require_dict("coaching_directive", payload)
    _validate_allowed_fields(
        payload=directive,
        allowed_fields=_COACHING_DIRECTIVE_FIELDS,
        object_name="coaching_directive",
    )

    normalized: Dict[str, Any] = {}
    for str_field in ("opening", "main_message", "tone"):
        if str_field in directive:
            normalized[str_field] = _require_non_empty_string(
                f"coaching_directive.{str_field}", directive[str_field]
            )

    if "content_plan" in directive:
        normalized["content_plan"] = _require_non_empty_string_list(
            "coaching_directive.content_plan", directive["content_plan"]
        )

    if "avoid" in directive:
        normalized["avoid"] = _require_string_list(
            "coaching_directive.avoid", directive["avoid"]
        )

    recommend_material = directive.get("recommend_material")
    if recommend_material is not None and not isinstance(recommend_material, str):
        raise ResponseGenerationContractError(
            "coaching_directive.recommend_material must be a string or null"
        )
    normalized["recommend_material"] = recommend_material
    return normalized


def validate_writer_brief(payload: Dict[str, Any]) -> None:
    """Validate a WriterBrief payload."""
    if not isinstance(payload, dict):
        raise ResponseGenerationContractError("payload must be a dict")

    keys = set(payload.keys())
    missing = sorted(_WRITER_BRIEF_REQUIRED_FIELDS - keys)
    extra = sorted(keys - _WRITER_BRIEF_TOP_LEVEL_FIELDS)
    if missing or extra:
        parts = []
        if missing:
            parts.append(f"missing: {', '.join(missing)}")
        if extra:
            parts.append(f"unexpected: {', '.join(extra)}")
        raise ResponseGenerationContractError(
            f"writer_brief field mismatch: {'; '.join(parts)}"
        )

    normalize_reply_mode(payload["reply_mode"])
    _validate_coaching_directive_for_writer(payload["coaching_directive"])
    _validate_validated_plan(payload["plan_data"])
    _validate_delivery_context(payload["delivery_context"])


@dataclass(frozen=True)
class WriterBrief:
    reply_mode: str
    coaching_directive: Dict[str, Any]
    plan_data: Dict[str, Any]
    delivery_context: Dict[str, Any]
    continuity_context: Optional[Dict[str, Any]] = None

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "WriterBrief":
        validate_writer_brief(payload)
        return cls(
            reply_mode=normalize_reply_mode(payload["reply_mode"]),
            coaching_directive=_validate_coaching_directive_for_writer(payload["coaching_directive"]),
            plan_data=_validate_validated_plan(payload["plan_data"]),
            delivery_context=_validate_delivery_context(payload["delivery_context"]),
            continuity_context=payload.get("continuity_context"),
        )

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "reply_mode": self.reply_mode,
            "coaching_directive": dict(self.coaching_directive),
            "plan_data": dict(self.plan_data),
            "delivery_context": dict(self.delivery_context),
        }
        if self.continuity_context is not None:
            result["continuity_context"] = dict(self.continuity_context)
        return result
