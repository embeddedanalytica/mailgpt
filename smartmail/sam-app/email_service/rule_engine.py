"""Deterministic RE1/RE2 rule logic."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any, Dict, List, Optional, Tuple


CANONICAL_TRACKS = {
    "general_low_time",
    "general_moderate_time",
    "main_base",
    "main_build",
    "main_peak_taper",
    "return_or_risk_managed",
}
CANONICAL_GOAL_CATEGORIES = {
    "general_consistency",
    "event_8_16w",
    "performance_16w_plus",
}
PHASES = {"base", "build", "peak_taper", "return_to_training"}
RISK_FLAGS = {"green", "yellow", "red_a", "red_b"}
TRACKS = set(CANONICAL_TRACKS)
PLAN_UPDATE_STATUSES = {
    "updated",
    "unchanged_clarification_needed",
    "unchanged_infeasible_week",
}
EVENT_DATE_VALIDATION_STATUSES = {
    "valid",
    "invalid_missing",
    "invalid_format",
    "invalid_past",
}
HARD_SESSION_TAGS = {
    "quality",
    "intervals",
    "tempo",
    "threshold",
    "vo2",
    "race_sim",
    "hills_hard",
}
NON_HARD_SESSION_TAGS = {
    "easy_aerobic",
    "recovery",
    "skills",
    "mobility",
    "strength",
}
ALLOWED_SESSION_TAGS = HARD_SESSION_TAGS | NON_HARD_SESSION_TAGS

_TRACK_ALIASES = {
    "main_sport_base": "main_base",
    "main_sport_build": "main_build",
    "main_sport_peak_taper": "main_peak_taper",
}
_GOAL_CATEGORY_ALIASES = {
    "no_event": "general_consistency",
    "event_8_16w": "event_8_16w",
    "8_16w": "event_8_16w",
    "event_16w_plus": "performance_16w_plus",
    "performance": "performance_16w_plus",
    "16w_plus": "performance_16w_plus",
}
_REQUIRED_TOP_LEVEL_FIELDS = {
    "classification_label",
    "track",
    "phase",
    "risk_flag",
    "weekly_skeleton",
    "today_action",
    "plan_update_status",
    "adjustments",
    "next_email_payload",
}
_OPTIONAL_TOP_LEVEL_FIELDS = {
    "risk_recent_history",
    "planner_rationale",
}
_REQUIRED_NEXT_EMAIL_PAYLOAD_FIELDS = {
    "subject_hint",
    "summary",
    "sessions",
    "plan_focus_line",
    "technique_cue",
    "recovery_target",
    "if_then_rules",
    "disclaimer_short",
    "safety_note",
}
_PHASE_ORDER = {"base": 0, "build": 1, "peak_taper": 2}
_PROGRESSION_PHASES = set(_PHASE_ORDER)
_RED_TIER_FLAGS = {"red_a", "red_b"}
_MAIN_SPORT_PHASE_TO_TRACK = {
    "base": "main_base",
    "build": "main_build",
    "peak_taper": "main_peak_taper",
}
_GENERAL_TRACKS = {"general_low_time", "general_moderate_time"}
_MAIN_TRACKS = {"main_base", "main_build", "main_peak_taper"}
_LOW_TIME_BUCKET = "2_3h"
_REQUIRED_CONSECUTIVE_UPGRADE_CHECKINS = 2


class RuleEngineContractError(ValueError):
    """Raised when rule engine output violates the strict contract."""


class RuleEngineDateValidationError(ValueError):
    """Raised when event-date validation inputs are invalid."""


class RuleEngineIntentError(ValueError):
    """Raised when performance-intent resolution inputs are invalid."""


class RuleEngineRiskError(ValueError):
    """Raised when risk derivation inputs are invalid."""


class RuleEnginePhaseError(ValueError):
    """Raised when phase derivation inputs are invalid."""


class RuleEngineTrackError(ValueError):
    """Raised when track selection inputs are invalid."""


class RuleEngineSwitchingError(ValueError):
    """Raised when switching inputs are invalid."""


class RuleEngineDeloadError(ValueError):
    """Raised when deload inputs are invalid."""


class RuleEngineArchetypeError(ValueError):
    """Raised when archetype inputs are invalid."""


class RuleEngineSkeletonError(ValueError):
    """Raised when weekly skeleton inputs are invalid."""


class RuleEngineStabilizationError(ValueError):
    """Raised when stabilization inputs are invalid."""


def _coerce_bool(value: Any, *, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _coerce_int(value: Any, *, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return default


def _coerce_float(value: Any, *, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def _coerce_non_negative_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    parsed = _coerce_int(value, default=-1)
    return parsed if parsed >= 0 else None


def _normalize_phase(value: Any, *, fallback: str = "base") -> str:
    normalized = str(value or "").strip().lower()
    return normalized if normalized in PHASES else fallback


def _normalize_sport(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"", "none", "null"}:
        return ""
    return text


def _parse_event_date(value: Any) -> Optional[date]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    try:
        return datetime.strptime(text, "%Y-%m-%d").date()
    except ValueError:
        return None


def _require_non_empty_string(field_name: str, value: Any) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RuleEngineContractError(f"{field_name} must be a non-empty string")


def _require_string_list(field_name: str, value: Any) -> None:
    if not isinstance(value, list):
        raise RuleEngineContractError(f"{field_name} must be a list")
    for idx, item in enumerate(value):
        if not isinstance(item, str):
            raise RuleEngineContractError(f"{field_name}[{idx}] must be a string")


def _require_non_empty_string_list(field_name: str, value: Any) -> None:
    if not isinstance(value, list):
        raise RuleEngineContractError(f"{field_name} must be a list")
    for idx, item in enumerate(value):
        if not isinstance(item, str) or not item.strip():
            raise RuleEngineContractError(f"{field_name}[{idx}] must be a non-empty string")


def _validate_required_fields_only(
    payload: Dict[str, Any],
    required_fields: set[str],
    field_scope: str,
    *,
    optional_fields: set[str] | None = None,
) -> None:
    provided = set(payload.keys())
    missing = required_fields - provided
    if missing:
        raise RuleEngineContractError(
            f"{field_scope} missing required fields: {', '.join(sorted(missing))}"
        )
    allowed = required_fields | (optional_fields or set())
    extra = provided - allowed
    if extra:
        raise RuleEngineContractError(
            f"{field_scope} has unknown fields: {', '.join(sorted(extra))}"
        )


def normalize_track_name(value: Any) -> str:
    text = str(value or "").strip().lower()
    return _TRACK_ALIASES.get(text, text)


def normalize_goal_category(profile: Dict[str, Any]) -> str:
    if not isinstance(profile, dict):
        return "general_consistency"

    goal_category = str(profile.get("goal_category", "") or "").strip().lower()
    if goal_category in CANONICAL_GOAL_CATEGORIES:
        return goal_category

    legacy = str(profile.get("primary_goal_timeframe", "") or "").strip().lower()
    return _GOAL_CATEGORY_ALIASES.get(legacy, "general_consistency")


def is_valid_phase(value: Any) -> bool:
    return isinstance(value, str) and value in PHASES


def is_valid_risk_flag(value: Any) -> bool:
    return isinstance(value, str) and value in RISK_FLAGS


def is_valid_track(value: Any) -> bool:
    return isinstance(value, str) and value in TRACKS


def is_valid_plan_update_status(value: Any) -> bool:
    return isinstance(value, str) and value in PLAN_UPDATE_STATUSES


def is_valid_event_date_status(value: Any) -> bool:
    return isinstance(value, str) and value in EVENT_DATE_VALIDATION_STATUSES


def is_hard_session_tag(tag: Any) -> bool:
    return isinstance(tag, str) and tag.strip().lower() in HARD_SESSION_TAGS


def validate_hard_session_tags(tags: List[str]) -> None:
    if not isinstance(tags, list):
        raise RuleEngineContractError("session_tags must be a list")
    allowed = HARD_SESSION_TAGS | NON_HARD_SESSION_TAGS
    for idx, tag in enumerate(tags):
        if not isinstance(tag, str):
            raise RuleEngineContractError(f"session_tags[{idx}] must be a string")
        if tag.strip().lower() not in allowed:
            raise RuleEngineContractError(f"session_tags[{idx}] must be one of {sorted(allowed)}")


def _dedupe_preserving_order(items: List[str]) -> List[str]:
    seen: set[str] = set()
    ordered: List[str] = []
    for item in items:
        token = str(item).strip()
        if not token or token in seen:
            continue
        seen.add(token)
        ordered.append(token)
    return ordered


@dataclass(frozen=True)
class RuleEngineOutput:
    classification_label: str
    track: str
    phase: str
    risk_flag: str
    weekly_skeleton: List[str]
    today_action: str
    plan_update_status: str
    adjustments: List[str]
    next_email_payload: Dict[str, Any]
    risk_recent_history: List[str] = ()  # type: ignore[assignment]
    planner_rationale: str = ""

    def to_dict(self) -> Dict[str, Any]:
        result = {
            "classification_label": self.classification_label,
            "track": self.track,
            "phase": self.phase,
            "risk_flag": self.risk_flag,
            "weekly_skeleton": list(self.weekly_skeleton),
            "today_action": self.today_action,
            "plan_update_status": self.plan_update_status,
            "adjustments": list(self.adjustments),
            "next_email_payload": dict(self.next_email_payload),
            "risk_recent_history": list(self.risk_recent_history),
        }
        if self.planner_rationale:
            result["planner_rationale"] = self.planner_rationale
        return result

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "RuleEngineOutput":
        normalized = dict(payload)
        normalized["track"] = normalize_track_name(normalized.get("track"))
        normalized.setdefault("risk_recent_history", [])
        validate_rule_engine_output(normalized)
        return cls(
            classification_label=normalized["classification_label"],
            track=normalized["track"],
            phase=normalized["phase"],
            risk_flag=normalized["risk_flag"],
            weekly_skeleton=list(normalized["weekly_skeleton"]),
            today_action=normalized["today_action"],
            plan_update_status=normalized["plan_update_status"],
            adjustments=list(normalized["adjustments"]),
            next_email_payload=dict(normalized["next_email_payload"]),
            risk_recent_history=list(normalized["risk_recent_history"]),
            planner_rationale=str(normalized.get("planner_rationale", "")).strip(),
        )


def validate_rule_engine_output(payload: Dict[str, Any]) -> None:
    if not isinstance(payload, dict):
        raise RuleEngineContractError("payload must be a dict")

    _validate_required_fields_only(
        payload, _REQUIRED_TOP_LEVEL_FIELDS, "rule_engine_output",
        optional_fields=_OPTIONAL_TOP_LEVEL_FIELDS,
    )
    _require_non_empty_string("classification_label", payload["classification_label"])
    _require_non_empty_string("today_action", payload["today_action"])

    track = normalize_track_name(payload["track"])
    if not is_valid_track(track):
        raise RuleEngineContractError(f"track must be one of {sorted(TRACKS)}")
    if not is_valid_phase(payload["phase"]):
        raise RuleEngineContractError(f"phase must be one of {sorted(PHASES)}")
    if not is_valid_risk_flag(payload["risk_flag"]):
        raise RuleEngineContractError(f"risk_flag must be one of {sorted(RISK_FLAGS)}")
    if not is_valid_plan_update_status(payload["plan_update_status"]):
        raise RuleEngineContractError(
            "plan_update_status must be one of "
            f"{sorted(PLAN_UPDATE_STATUSES)}"
        )

    _require_string_list("weekly_skeleton", payload["weekly_skeleton"])
    _require_string_list("adjustments", payload["adjustments"])

    if "risk_recent_history" in payload:
        _require_string_list("risk_recent_history", payload["risk_recent_history"])

    next_email_payload = payload["next_email_payload"]
    if not isinstance(next_email_payload, dict):
        raise RuleEngineContractError("next_email_payload must be a dict")
    _validate_required_fields_only(
        next_email_payload,
        _REQUIRED_NEXT_EMAIL_PAYLOAD_FIELDS,
        "next_email_payload",
    )
    _require_non_empty_string("next_email_payload.subject_hint", next_email_payload["subject_hint"])
    _require_non_empty_string("next_email_payload.summary", next_email_payload["summary"])
    _require_non_empty_string(
        "next_email_payload.plan_focus_line",
        next_email_payload["plan_focus_line"],
    )
    _require_non_empty_string(
        "next_email_payload.technique_cue",
        next_email_payload["technique_cue"],
    )
    _require_non_empty_string(
        "next_email_payload.recovery_target",
        next_email_payload["recovery_target"],
    )
    _require_non_empty_string("next_email_payload.safety_note", next_email_payload["safety_note"])
    _require_string_list("next_email_payload.sessions", next_email_payload["sessions"])
    _require_non_empty_string_list(
        "next_email_payload.if_then_rules",
        next_email_payload["if_then_rules"],
    )

    disclaimer_short = next_email_payload["disclaimer_short"]
    if not isinstance(disclaimer_short, str):
        raise RuleEngineContractError("next_email_payload.disclaimer_short must be a string")
    if payload["risk_flag"] == "red_b" and not disclaimer_short.strip():
        raise RuleEngineContractError(
            "next_email_payload.disclaimer_short must be non-empty when risk_flag=red_b"
        )


def validate_event_date(checkin: Dict[str, Any], today_date: date) -> str:
    if not isinstance(today_date, date):
        raise RuleEngineDateValidationError("today_date must be a datetime.date")
    if not isinstance(checkin, dict):
        raise RuleEngineDateValidationError("checkin must be a dict")

    raw_event_date = checkin.get("event_date")
    if raw_event_date is None:
        return "invalid_missing"

    event_date_str = str(raw_event_date).strip()
    if not event_date_str:
        return "invalid_missing"

    parsed = _parse_event_date(event_date_str)
    if parsed is None:
        return "invalid_format"
    if parsed < today_date:
        return "invalid_past"
    return "valid"


def apply_event_date_validation_guard(
    *,
    validation_status: str,
    candidate_phase: str,
    prior_phase: str,
    candidate_plan_update_status: str = "updated",
) -> Tuple[str, str]:
    if not is_valid_event_date_status(validation_status):
        raise RuleEngineDateValidationError(
            "validation_status must be one of "
            f"{sorted(EVENT_DATE_VALIDATION_STATUSES)}"
        )
    if candidate_phase not in PHASES:
        raise RuleEngineDateValidationError(f"candidate_phase must be one of {sorted(PHASES)}")
    if prior_phase not in PHASES:
        raise RuleEngineDateValidationError(f"prior_phase must be one of {sorted(PHASES)}")

    if validation_status == "valid":
        return candidate_phase, candidate_plan_update_status
    return prior_phase, "unchanged_clarification_needed"


def _optional_bool(source: Dict[str, Any], key: str) -> Optional[bool]:
    if key not in source:
        return None
    value = source.get(key)
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    raise RuleEngineIntentError(f"{key} must be a bool or null")


def resolve_effective_performance_intent(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
) -> bool:
    if not isinstance(profile, dict):
        raise RuleEngineIntentError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineIntentError("checkin must be a dict")

    this_week = _optional_bool(checkin, "performance_intent_this_week")
    if this_week is not None:
        return this_week

    profile_default = _optional_bool(profile, "performance_intent_default")
    if profile_default is not None:
        return profile_default
    return False


def _normalized_risk_candidate(value: Any) -> str:
    return str(value or "").strip().lower()


def _latest_weekly_signal(rule_state: Dict[str, Any]) -> Dict[str, Any]:
    weekly = rule_state.get("weekly_signals_last_4", [])
    if not isinstance(weekly, list) or not weekly:
        return {}
    last = weekly[-1]
    return last if isinstance(last, dict) else {}


def _is_deterministic_worsening(checkin: Dict[str, Any], rule_state: Dict[str, Any]) -> bool:
    previous = _latest_weekly_signal(rule_state)
    if not previous:
        return False

    current_pain = _coerce_float(checkin.get("pain_score"), default=0.0)
    previous_pain = _coerce_float(previous.get("pain_score"), default=0.0)
    if current_pain - previous_pain >= 2:
        return True
    if 0.0 <= previous_pain <= 3.0 and current_pain >= 4.0:
        return True

    previous_affects_form = _coerce_bool(previous.get("pain_affects_form"))
    current_affects_form = _coerce_bool(checkin.get("pain_affects_form")) or _coerce_bool(
        checkin.get("pain_affects_gait")
    )
    return (not previous_affects_form) and current_affects_form


def _is_red_b(profile: Dict[str, Any], checkin: Dict[str, Any], rule_state: Dict[str, Any]) -> bool:
    if any(
        (
            _coerce_bool(checkin.get("pain_sharp")),
            _coerce_bool(checkin.get("pain_sudden_onset")),
            _coerce_bool(checkin.get("swelling_present")),
            _coerce_bool(checkin.get("numbness_or_tingling")),
            _coerce_bool(checkin.get("pain_affects_form")) or _coerce_bool(checkin.get("pain_affects_gait")),
            _coerce_bool(checkin.get("night_pain")),
            _coerce_bool(checkin.get("pain_worsening"))
            or _coerce_bool(checkin.get("pain_worse_session_to_session"))
            or _is_deterministic_worsening(checkin, rule_state),
        )
    ):
        return True

    return _coerce_bool(checkin.get("clinician_recommended_stop")) or _coerce_bool(
        profile.get("clinician_recommended_stop")
    )


def _is_red_a(checkin: Dict[str, Any]) -> bool:
    pain_score = _coerce_float(checkin.get("pain_score"), default=0.0)
    return (
        pain_score >= 4
        and not _coerce_bool(checkin.get("pain_sharp"))
        and not _coerce_bool(checkin.get("pain_affects_form"))
        and not _coerce_bool(checkin.get("pain_affects_gait"))
        and not _coerce_bool(checkin.get("pain_worsening"))
        and not _coerce_bool(checkin.get("pain_worse_session_to_session"))
    )


def _is_yellow(profile: Dict[str, Any], checkin: Dict[str, Any]) -> bool:
    recurring_niggles = str(profile.get("injury_baseline", "")).strip().lower() == "recurring_niggles"
    energy_score = _coerce_float(checkin.get("energy_score"), default=10.0)
    stress_score = _coerce_float(checkin.get("stress_score"), default=0.0)
    sleep_score = _coerce_float(checkin.get("sleep_score"), default=10.0)
    weekly_threshold_hit = (
        energy_score <= 4
        or stress_score >= 8
        or sleep_score <= 4
        or (stress_score >= 7 and energy_score <= 5)
    )
    return recurring_niggles or weekly_threshold_hit


def derive_risk(profile: Dict[str, Any], checkin: Dict[str, Any], rule_state: Dict[str, Any]) -> str:
    if not isinstance(profile, dict):
        raise RuleEngineRiskError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineRiskError("checkin must be a dict")
    if not isinstance(rule_state, dict):
        raise RuleEngineRiskError("rule_state must be a dict")

    risk_candidate = _normalized_risk_candidate(
        checkin.get("risk_candidate", profile.get("risk_candidate"))
    )
    if is_valid_risk_flag(risk_candidate):
        return risk_candidate
    if _is_red_b(profile, checkin, rule_state):
        return "red_b"
    if _is_red_a(checkin):
        return "red_a"
    if _is_yellow(profile, checkin):
        return "yellow"
    return "green"


def _event_expected(profile: Dict[str, Any], checkin: Dict[str, Any]) -> bool:
    if _parse_event_date(checkin.get("event_date")) is not None:
        return True

    has_upcoming_event = checkin.get("has_upcoming_event")
    if isinstance(has_upcoming_event, bool):
        return has_upcoming_event

    goal_category = normalize_goal_category(profile)
    if goal_category.startswith("event_"):
        return True

    if _parse_event_date(profile.get("event_date")) is not None:
        return True
    return False


def _prior_phase_from_rule_state(rule_state: Dict[str, Any]) -> str:
    history = rule_state.get("phase_risk_time_last_6", [])
    if not isinstance(history, list) or not history:
        return "base"
    for item in reversed(history):
        if not isinstance(item, dict):
            continue
        phase = _normalize_phase(item.get("phase"), fallback="base")
        if phase in PHASES:
            return phase
    return "base"


def derive_calendar_phase(
    checkin: Dict[str, Any],
    today_date: date,
    *,
    effective_performance_intent: bool = False,
) -> str:
    if not isinstance(checkin, dict):
        raise RuleEnginePhaseError("checkin must be a dict")
    if not isinstance(today_date, date):
        raise RuleEnginePhaseError("today_date must be a datetime.date")

    parsed_event_date = _parse_event_date(checkin.get("event_date"))
    if parsed_event_date is not None:
        days_until_event = (parsed_event_date - today_date).days
        if days_until_event <= 21:
            return "peak_taper"
        if days_until_event <= 84:
            return "build"
        return "base"
    return "build" if effective_performance_intent else "base"


def _resolve_hard_return_context(checkin: Dict[str, Any]) -> bool:
    return (
        _coerce_bool(checkin.get("returning_from_break"))
        or str(checkin.get("recent_illness", "") or "").strip().lower() == "significant"
        or ((_coerce_non_negative_int(checkin.get("break_days")) or -1) >= 10)
    )


def _resolve_soft_return_context(profile: Dict[str, Any], checkin: Dict[str, Any]) -> bool:
    if _resolve_hard_return_context(checkin):
        return True
    for key in ("newly_returning", "return_to_training", "return_context", "hard_return_context"):
        if _coerce_bool(checkin.get(key)) or _coerce_bool(profile.get(key)):
            return True
    return False


def _resolve_cap_phase(
    *,
    risk_flag: str,
    soft_return_context: bool,
    experience_level: str,
) -> Optional[str]:
    if risk_flag == "red_b":
        return "base"
    if risk_flag in {"red_a", "yellow"} or soft_return_context:
        return "build"
    if experience_level == "new":
        return "base"
    return None


def _apply_phase_cap(phase: str, cap_phase: Optional[str]) -> str:
    if cap_phase is None or phase not in _PHASE_ORDER or cap_phase not in _PHASE_ORDER:
        return phase
    if _PHASE_ORDER[phase] > _PHASE_ORDER[cap_phase]:
        return cap_phase
    return phase


def derive_phase(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    today_date: date,
    rule_state: Dict[str, Any],
    *,
    risk_flag: str,
    effective_performance_intent: bool,
) -> str:
    if not isinstance(profile, dict):
        raise RuleEnginePhaseError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEnginePhaseError("checkin must be a dict")
    if not isinstance(today_date, date):
        raise RuleEnginePhaseError("today_date must be a datetime.date")
    if not isinstance(rule_state, dict):
        raise RuleEnginePhaseError("rule_state must be a dict")
    if not isinstance(effective_performance_intent, bool):
        raise RuleEnginePhaseError("effective_performance_intent must be a bool")

    normalized_risk = str(risk_flag or "").strip().lower() or "green"
    if normalized_risk not in RISK_FLAGS:
        raise RuleEnginePhaseError(f"risk_flag must be one of {sorted(RISK_FLAGS)}")

    if _resolve_hard_return_context(checkin):
        return "return_to_training"

    if _event_expected(profile, checkin):
        if validate_event_date(checkin, today_date) == "valid":
            phase = derive_calendar_phase(
                checkin=checkin,
                today_date=today_date,
                effective_performance_intent=effective_performance_intent,
            )
        else:
            phase = _prior_phase_from_rule_state(rule_state)
    else:
        phase = "build" if effective_performance_intent else "base"

    experience_level = str(
        checkin.get("experience_level", profile.get("experience_level", ""))
    ).strip().lower()
    if experience_level == "beginner":
        experience_level = "new"

    return _normalize_phase(
        _apply_phase_cap(
            phase,
            _resolve_cap_phase(
                risk_flag=normalized_risk,
                soft_return_context=_resolve_soft_return_context(profile, checkin),
                experience_level=experience_level,
            ),
        ),
        fallback="base",
    )


def _has_main_sport(profile: Dict[str, Any], checkin: Dict[str, Any]) -> bool:
    return bool(
        _normalize_sport(checkin.get("main_sport_current"))
        or _normalize_sport(profile.get("main_sport_current"))
    )


def _is_return_context(profile: Dict[str, Any], checkin: Dict[str, Any], phase: str) -> bool:
    if str(phase).strip().lower() == "return_to_training":
        return True
    if _resolve_hard_return_context(checkin):
        return True
    for key in (
        "return_to_training",
        "newly_returning",
        "returning_from_break",
        "return_context",
        "hard_return_context",
    ):
        if _coerce_bool(checkin.get(key)) or _coerce_bool(profile.get(key)):
            return True
    return False


def select_track(profile: Dict[str, Any], phase: str, risk_flag: str) -> str:
    if not isinstance(profile, dict):
        raise RuleEngineTrackError("profile must be a dict")

    normalized_phase = str(phase or "").strip().lower()
    normalized_risk = str(risk_flag or "").strip().lower()
    if not normalized_phase:
        raise RuleEngineTrackError("phase must be a non-empty string")
    if not normalized_risk:
        raise RuleEngineTrackError("risk_flag must be a non-empty string")

    checkin_proxy: Dict[str, Any] = {}
    if _is_return_context(profile, checkin_proxy, normalized_phase) or normalized_risk in _RED_TIER_FLAGS:
        return "return_or_risk_managed"
    if not _has_main_sport(profile, checkin_proxy):
        if str(profile.get("time_bucket", "")).strip().lower() == _LOW_TIME_BUCKET:
            return "general_low_time"
        return "general_moderate_time"
    return _MAIN_SPORT_PHASE_TO_TRACK.get(normalized_phase, "main_base")


def quality_archetype_for_experience(experience_level: str) -> Dict[str, Any]:
    normalized = str(experience_level or "").strip().lower()
    if normalized == "beginner":
        normalized = "new"
    if normalized == "new":
        return {
            "experience_level": "new",
            "template": "strides_hills_or_short_tempo",
            "vo2_allowed": False,
            "max_quality_sessions_per_week": 1,
        }
    if normalized == "advanced":
        return {
            "experience_level": "advanced",
            "template": "event_specific_intervals",
            "vo2_allowed": True,
            "max_quality_sessions_per_week": 2,
        }
    return {
        "experience_level": "intermediate",
        "template": "tempo_threshold_intervals",
        "vo2_allowed": True,
        "max_quality_sessions_per_week": 1,
    }


def select_quality_archetype(
    profile: Dict[str, Any],
    risk_flag: str,
    schedule_variability: str,
) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise RuleEngineArchetypeError("profile must be a dict")

    normalized_risk = str(risk_flag or "").strip().lower()
    variability = str(schedule_variability or profile.get("schedule_variability", "")).strip().lower()
    base = quality_archetype_for_experience(profile.get("experience_level", "intermediate"))
    if normalized_risk in _RED_TIER_FLAGS:
        return {
            "experience_level": base["experience_level"],
            "template": "safety_only_no_quality",
            "vo2_allowed": False,
            "max_quality_sessions_per_week": 0,
            "intensity_mode": "none",
        }

    result = dict(base)
    if normalized_risk == "yellow" or variability == "high":
        result["intensity_mode"] = "reduced"
        result["vo2_allowed"] = False
        result["max_quality_sessions_per_week"] = min(1, int(result["max_quality_sessions_per_week"]))
        if variability == "high":
            result["template"] = "conservative_quality_variant"
    else:
        result["intensity_mode"] = "normal"
    return result


def _sports_map_from_checkin(checkin: Dict[str, Any]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    activities = checkin.get("sports_last_week", [])
    if not isinstance(activities, list):
        return result
    for entry in activities:
        if not isinstance(entry, dict):
            continue
        sport = _normalize_sport(entry.get("sport"))
        minutes = max(0, _coerce_int(entry.get("minutes"), default=0))
        if sport:
            result[sport] = result.get(sport, 0) + minutes
    return result


def _sports_map_from_history(rule_state: Dict[str, Any]) -> Dict[str, int]:
    weekly = rule_state.get("weekly_signals_last_4", [])
    if not isinstance(weekly, list) or not weekly:
        return {}
    latest = weekly[-1]
    if not isinstance(latest, dict):
        return {}
    sports = latest.get("sports_minutes_by_sport", {})
    if not isinstance(sports, dict):
        return {}
    result: Dict[str, int] = {}
    for sport, minutes in sports.items():
        normalized = _normalize_sport(sport)
        if normalized:
            result[normalized] = max(0, _coerce_int(minutes, default=0))
    return result


def _two_week_sports_totals(checkin: Dict[str, Any], rule_state: Dict[str, Any]) -> Dict[str, int]:
    totals: Dict[str, int] = {}
    for source in (_sports_map_from_history(rule_state), _sports_map_from_checkin(checkin)):
        for sport, minutes in source.items():
            totals[sport] = totals.get(sport, 0) + max(0, minutes)
    return totals


def _dominant_alternate_sport(current_main_sport: str, totals: Dict[str, int]) -> Tuple[str, int, int]:
    total_minutes = sum(max(0, value) for value in totals.values())
    best_sport = ""
    best_minutes = 0
    for sport, minutes in totals.items():
        if sport != current_main_sport and minutes > best_minutes:
            best_sport = sport
            best_minutes = minutes
    return best_sport, best_minutes, total_minutes


def should_switch_main_sport(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    rule_state: Dict[str, Any],
) -> bool:
    if not isinstance(profile, dict):
        raise RuleEngineSwitchingError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineSwitchingError("checkin must be a dict")
    if not isinstance(rule_state, dict):
        raise RuleEngineSwitchingError("rule_state must be a dict")

    if _coerce_bool(checkin.get("explicit_main_sport_switch_request")):
        return True

    current_main = _normalize_sport(checkin.get("main_sport_current", profile.get("main_sport_current")))
    alternate, alternate_minutes, total_minutes = _dominant_alternate_sport(
        current_main,
        _two_week_sports_totals(checkin, rule_state),
    )
    return bool(alternate) and total_minutes >= 120 and (alternate_minutes / total_minutes) >= 0.60


def resolve_main_sport_after_guardrails(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    rule_state: Dict[str, Any],
    risk_flag: str,
) -> Optional[str]:
    if not isinstance(profile, dict):
        raise RuleEngineSwitchingError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineSwitchingError("checkin must be a dict")
    if not isinstance(rule_state, dict):
        raise RuleEngineSwitchingError("rule_state must be a dict")

    current_main = _normalize_sport(checkin.get("main_sport_current", profile.get("main_sport_current")))
    explicit_request = _coerce_bool(checkin.get("explicit_main_sport_switch_request"))
    requested_main = _normalize_sport(checkin.get("requested_main_sport"))

    candidate = current_main
    if explicit_request and requested_main:
        candidate = requested_main
    elif should_switch_main_sport(profile, checkin, rule_state):
        dominant_alt, _, _ = _dominant_alternate_sport(
            current_main,
            _two_week_sports_totals(checkin, rule_state),
        )
        if dominant_alt:
            candidate = dominant_alt

    transition_weeks_remaining = max(
        0,
        _coerce_int(rule_state.get("main_sport_transition_weeks_remaining"), default=0),
    )
    freeze_active = transition_weeks_remaining > 0
    risk_is_red_b = str(risk_flag or "").strip().lower() == "red_b"
    if freeze_active and candidate != current_main and not explicit_request and not risk_is_red_b:
        return current_main or None
    return candidate or None


def apply_switch_transition_limits(
    plan_constraints: Dict[str, Any],
    rule_state: Dict[str, Any],
    checkin: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(plan_constraints, dict):
        raise RuleEngineSwitchingError("plan_constraints must be a dict")
    if not isinstance(rule_state, dict):
        raise RuleEngineSwitchingError("rule_state must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineSwitchingError("checkin must be a dict")

    output = dict(plan_constraints)
    transition_weeks_remaining = max(
        0,
        _coerce_int(rule_state.get("main_sport_transition_weeks_remaining"), default=0),
    )
    if transition_weeks_remaining <= 0:
        return output

    output["max_quality_sessions_per_week"] = min(
        _coerce_int(output.get("max_quality_sessions_per_week"), default=99),
        1,
    )
    output["max_weekly_volume_increase_pct"] = min(
        _coerce_int(output.get("max_weekly_volume_increase_pct"), default=100),
        10,
    )
    return output


def _latest_risk_flags(rule_state: Dict[str, Any], current_risk_flag: str) -> List[str]:
    history = rule_state.get("phase_risk_time_last_6", [])
    flags: List[str] = []
    if isinstance(history, list):
        for item in history[-3:]:
            if isinstance(item, dict):
                flags.append(str(item.get("risk_flag", "")).strip().lower())
    flags.append(str(current_risk_flag or "").strip().lower())
    return flags[-4:]


def is_sustained_yellow(rule_state: Dict[str, Any], current_risk_flag: str) -> bool:
    if not isinstance(rule_state, dict):
        raise RuleEngineDeloadError("rule_state must be a dict")
    flags = _latest_risk_flags(rule_state, current_risk_flag)
    return (len(flags) >= 2 and flags[-1] == "yellow" and flags[-2] == "yellow") or (
        sum(1 for flag in flags if flag == "yellow") >= 3
    )


def should_trigger_main_sport_deload(
    phase: str,
    rule_state: Dict[str, Any],
    current_risk_flag: str,
) -> bool:
    if not isinstance(rule_state, dict):
        raise RuleEngineDeloadError("rule_state must be a dict")
    if str(phase or "").strip().lower() == "peak_taper":
        return False
    if is_sustained_yellow(rule_state, current_risk_flag):
        return True
    return max(0, _coerce_int(rule_state.get("weeks_since_deload"), default=0)) >= 4


def apply_main_sport_deload_adjustments(
    skeleton: List[str],
    *,
    reduce_volume_pct: int = 20,
) -> List[str]:
    if not isinstance(skeleton, list):
        raise RuleEngineDeloadError("skeleton must be a list")
    if not isinstance(reduce_volume_pct, int):
        raise RuleEngineDeloadError("reduce_volume_pct must be an int")

    capped_pct = max(15, min(25, reduce_volume_pct))
    adjusted = [str(item) for item in skeleton]
    removed_quality = False
    for idx, session in enumerate(adjusted):
        if session.strip().lower() in HARD_SESSION_TAGS:
            adjusted.pop(idx)
            removed_quality = True
            break
    adjusted.append(f"deload_volume_reduce_{capped_pct}pct")
    if removed_quality:
        adjusted.append("deload_quality_session_removed")
    return adjusted


def _schedule_variability(profile: Dict[str, Any], checkin: Dict[str, Any]) -> str:
    return str(checkin.get("schedule_variability", profile.get("schedule_variability", "medium"))).strip().lower()


def _days_available(checkin: Dict[str, Any]) -> int:
    return max(0, _coerce_int(checkin.get("days_available"), default=0))


def _quality_token_from_archetype(archetype: Dict[str, Any], risk_flag: str) -> str:
    if risk_flag in _RED_TIER_FLAGS:
        return "easy_aerobic"
    intensity_mode = str(archetype.get("intensity_mode", "normal")).strip().lower()
    template = str(archetype.get("template", "tempo_threshold_intervals")).strip().lower()
    if intensity_mode == "reduced":
        return "reduced_intensity_or_easy"
    if template == "event_specific_intervals":
        return "intervals"
    if template == "strides_hills_or_short_tempo":
        return "hills_hard"
    return "tempo"


def _general_template(
    time_bucket: str,
    *,
    allow_intensity: bool,
    variability: str,
    days_available: int,
) -> List[str]:
    if time_bucket == "2_3h":
        return ["easy_aerobic", "strength", "skills"]
    if time_bucket == "7_10h":
        skeleton = ["easy_aerobic", "easy_aerobic", "easy_aerobic", "strength", "skills"]
        skeleton.append("quality" if allow_intensity else "easy_aerobic")
        return skeleton
    if time_bucket == "10h_plus":
        skeleton = [
            "easy_aerobic",
            "easy_aerobic",
            "easy_aerobic",
            "strength",
            "skills",
            "quality" if allow_intensity else "easy_aerobic",
            "recovery",
        ]
        add_ons = ["easy_aerobic"]
        second_allowed = variability != "high" and (days_available == 0 or days_available >= len(skeleton) + 2)
        if second_allowed:
            add_ons.append("skills")
        if len(add_ons) < 2 and variability == "high":
            add_ons.append("recovery")
        return skeleton + add_ons[:2]
    return ["easy_aerobic", "easy_aerobic", "strength", "quality" if allow_intensity else "skills"]


def _main_template(
    profile: Dict[str, Any],
    time_bucket: str,
    risk_flag: str,
    variability: str,
) -> List[str]:
    quality_token = _quality_token_from_archetype(
        select_quality_archetype(profile, risk_flag, variability),
        risk_flag,
    )
    if time_bucket == "2_3h":
        return ["easy_aerobic", quality_token if risk_flag == "green" else "easy_aerobic", "strength"]
    if time_bucket == "7_10h":
        return ["easy_aerobic", "easy_aerobic", "easy_aerobic", "easy_aerobic", quality_token, "strength"]
    if time_bucket == "10h_plus":
        skeleton = [
            "easy_aerobic",
            "easy_aerobic",
            "easy_aerobic",
            "easy_aerobic",
            "strength",
            quality_token,
        ]
        experience = str(profile.get("experience_level", "intermediate")).strip().lower()
        if experience in {"intermediate", "advanced"} and risk_flag == "green" and variability != "high":
            skeleton.append(quality_token)
        else:
            skeleton.append("skills")
        skeleton.append("easy_aerobic")
        skeleton.append("skills" if variability != "high" else "recovery")
        return skeleton
    return ["easy_aerobic", "easy_aerobic", quality_token, "strength"]


def apply_risk_overrides(
    sessions: List[str],
    risk_flag: str,
    track: str,
) -> Tuple[List[str], List[str]]:
    if not isinstance(sessions, list):
        raise RuleEngineSkeletonError("sessions must be a list")

    normalized_risk = str(risk_flag or "").strip().lower() or "green"
    if normalized_risk not in RISK_FLAGS:
        raise RuleEngineSkeletonError(f"risk_flag must be one of {sorted(RISK_FLAGS)}")

    adjusted = [str(session).strip().lower() for session in sessions if str(session).strip()]
    adjustments: List[str] = []
    if normalized_risk == "green":
        return adjusted, adjustments
    if normalized_risk == "yellow":
        replaced = ["reduced_intensity_or_easy" if token in HARD_SESSION_TAGS else token for token in adjusted]
        if replaced != adjusted:
            adjustments.append("reduce_intensity")
        return replaced, adjustments

    red_adjusted = []
    removed_hard = False
    for token in adjusted:
        if token in HARD_SESSION_TAGS:
            red_adjusted.append("easy_aerobic")
            removed_hard = True
        else:
            red_adjusted.append(token)
    if removed_hard:
        adjustments.append("remove_all_intensity")
    if track in _MAIN_TRACKS or track == "return_or_risk_managed":
        adjustments.append("low_impact_swap")
    if normalized_risk == "red_a":
        adjustments.append("volume_reduce_30pct")
        return red_adjusted, adjustments
    adjustments.extend(["volume_reduce_50pct", "clinician_stop_recommended"])
    return red_adjusted, adjustments


def detect_infeasible_week(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    candidate_sessions: List[str],
) -> bool:
    if not isinstance(profile, dict):
        raise RuleEngineSkeletonError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineSkeletonError("checkin must be a dict")
    if not isinstance(candidate_sessions, list):
        raise RuleEngineSkeletonError("candidate_sessions must be a list")
    if _days_available(checkin) <= 1:
        return True

    non_viable = {
        "volume_reduce_30pct",
        "volume_reduce_50pct",
        "clinician_stop_recommended",
        "deload_volume_reduce_20pct",
        "deload_quality_session_removed",
    }
    viable = [
        str(token).strip().lower()
        for token in candidate_sessions
        if str(token).strip() and str(token).strip().lower() not in non_viable
    ]
    return len(viable) == 0


def build_weekly_skeleton(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    track: str,
    phase: str,
    risk_flag: str,
    effective_performance_intent: bool,
    rule_state: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise RuleEngineSkeletonError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineSkeletonError("checkin must be a dict")
    if not isinstance(rule_state, dict):
        raise RuleEngineSkeletonError("rule_state must be a dict")
    if not isinstance(effective_performance_intent, bool):
        raise RuleEngineSkeletonError("effective_performance_intent must be a bool")

    normalized_track = str(track or "").strip().lower()
    normalized_phase = str(phase or "").strip().lower()
    normalized_risk = str(risk_flag or "").strip().lower() or "green"
    if normalized_risk not in RISK_FLAGS:
        raise RuleEngineSkeletonError(f"risk_flag must be one of {sorted(RISK_FLAGS)}")

    time_bucket = str(checkin.get("time_bucket", profile.get("time_bucket", "4_6h"))).strip().lower() or "4_6h"
    variability = _schedule_variability(profile, checkin)
    days_available = _days_available(checkin)
    if normalized_track in _GENERAL_TRACKS:
        base_sessions = _general_template(
            time_bucket,
            allow_intensity=normalized_risk == "green" and effective_performance_intent,
            variability=variability,
            days_available=days_available,
        )
    elif normalized_track in _MAIN_TRACKS or normalized_track == "return_or_risk_managed":
        base_sessions = _main_template(profile, time_bucket, normalized_risk, variability)
    else:
        raise RuleEngineSkeletonError("track must be a recognized canonical value")

    adjusted_sessions, adjustments = apply_risk_overrides(base_sessions, normalized_risk, normalized_track)
    infeasible = detect_infeasible_week(profile, checkin, adjusted_sessions)
    final_sessions = adjusted_sessions
    plan_update_status = "updated"
    if infeasible:
        final_sessions = []
        plan_update_status = "unchanged_infeasible_week"
        adjustments = list(adjustments) + ["fallback_optional_short_mobility_recovery_touch"]
    return {
        "track": normalized_track,
        "phase": normalized_phase,
        "risk_flag": normalized_risk,
        "time_bucket": time_bucket,
        "weekly_skeleton": final_sessions,
        "adjustments": adjustments,
        "plan_update_status": plan_update_status,
        "infeasible": infeasible,
    }


def _main_anchor_label(track: str, weekly_skeleton: List[str]) -> str:
    for token in weekly_skeleton:
        normalized = str(token).strip().lower()
        if normalized in {"easy_aerobic", "recovery"}:
            if track in _MAIN_TRACKS or track == "return_or_risk_managed":
                return "long easy main-sport session"
            return "long easy aerobic session"
    if track in _MAIN_TRACKS or track == "return_or_risk_managed":
        return "long easy main-sport session"
    return "long easy aerobic session"


def _secondary_anchor_label(weekly_skeleton: List[str]) -> str:
    for token in weekly_skeleton:
        normalized = str(token).strip().lower()
        if normalized in {"strength", "mobility"}:
            return "strength session"
    return "short mobility session"


def route_today_action(
    checkin: Dict[str, Any],
    risk_flag: str,
    track: str,
    weekly_skeleton: List[str],
) -> Dict[str, Any]:
    if not isinstance(checkin, dict):
        raise RuleEngineSkeletonError("checkin must be a dict")
    if not isinstance(weekly_skeleton, list):
        raise RuleEngineSkeletonError("weekly_skeleton must be a list")

    normalized_risk = str(risk_flag or "").strip().lower() or "green"
    if normalized_risk not in RISK_FLAGS:
        raise RuleEngineSkeletonError(f"risk_flag must be one of {sorted(RISK_FLAGS)}")

    pain_score = _coerce_float(checkin.get("pain_score"), default=0.0)
    raw_energy_score = checkin.get("energy_score")
    energy_score: Optional[float]
    if raw_energy_score is None or (isinstance(raw_energy_score, str) and not raw_energy_score.strip()):
        energy_score = None
    else:
        energy_score = _coerce_float(raw_energy_score, default=0.0)
    missed_sessions = max(0, _coerce_int(checkin.get("missed_sessions_count"), default=0))
    chaotic_week = _coerce_bool(checkin.get("week_chaotic"))
    infeasible = _days_available(checkin) <= 1 or len(weekly_skeleton) == 0
    anchor_sessions = [_main_anchor_label(track, weekly_skeleton), _secondary_anchor_label(weekly_skeleton)]

    if infeasible:
        return {
            "today_action": "optional_short_mobility_or_recovery_only",
            "adjustments": [
                "keep_existing_plan_unchanged",
                "fallback_optional_short_mobility_recovery_touch",
            ],
            "routing_context": {
                "winning_signal": "chaos",
                "anchor_sessions": anchor_sessions,
                "infeasible": True,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    if normalized_risk == "red_b":
        return {
            "today_action": "stop_training_intensity_low_impact_only_if_pain_free",
            "adjustments": [
                "stop_training_intensity_immediately",
                "consult_clinician",
                "apply_adjustment_window_3_7_days",
            ],
            "routing_context": {
                "winning_signal": "pain",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": True,
            },
        }

    if normalized_risk == "red_a":
        return {
            "today_action": "stop_intensity_easy_cross_train_and_update_coach",
            "adjustments": [
                "stop_intensity",
                "easy_cross_train_only",
                "update_coach_within_24h",
                "apply_adjustment_window_3_7_days",
            ],
            "routing_context": {
                "winning_signal": "pain",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": True,
            },
        }

    if 1.0 <= pain_score <= 3.0:
        return {
            "today_action": "easy_only_monitor_pain",
            "adjustments": ["easy_only", "no_intensity", "monitor_pain"],
            "routing_context": {
                "winning_signal": "pain",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    if energy_score is not None and energy_score <= 4.0:
        return {
            "today_action": "minimum_effective_dose_session",
            "adjustments": ["minimum_effective_dose"],
            "routing_context": {
                "winning_signal": "energy",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    if energy_score is not None and 5.0 <= energy_score <= 7.0:
        return {
            "today_action": "do_planned_but_conservative",
            "adjustments": ["planned_but_conservative"],
            "routing_context": {
                "winning_signal": "energy",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    if missed_sessions >= 2:
        return {
            "today_action": "rebuild_week_easy_volume_first_delay_intensity",
            "adjustments": ["rebuild_week_easy_volume_first", "delay_intensity", "no_make_up_intensity"],
            "routing_context": {
                "winning_signal": "missed_sessions",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    if missed_sessions == 1:
        return {
            "today_action": "resume_plan_no_make_up_intensity",
            "adjustments": ["resume_plan", "no_make_up_intensity"],
            "routing_context": {
                "winning_signal": "missed_sessions",
                "anchor_sessions": [],
                "infeasible": False,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    if chaotic_week:
        return {
            "today_action": "prioritize_big_2_anchors",
            "adjustments": ["prioritize_big_2_anchors"],
            "routing_context": {
                "winning_signal": "chaos",
                "anchor_sessions": anchor_sessions,
                "infeasible": False,
                "safety_focus": track == "return_or_risk_managed",
            },
        }

    return {
        "today_action": "optional_slight_upgrade_if_green",
        "adjustments": [],
        "routing_context": {
            "winning_signal": "default",
            "anchor_sessions": [],
            "infeasible": False,
            "safety_focus": track == "return_or_risk_managed",
        },
    }


def build_decision_envelope(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    phase: str,
    risk_flag: str,
    track: str,
    effective_performance_intent: bool,
    rule_state: Dict[str, Any],
    *,
    fallback_skeleton: Optional[List[str]] = None,
    adjustments: Optional[List[str]] = None,
    plan_update_status: str = "updated",
    today_action: str = "",
    routing_context: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise RuleEngineContractError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineContractError("checkin must be a dict")
    if not isinstance(rule_state, dict):
        raise RuleEngineContractError("rule_state must be a dict")

    skeleton = [str(item).strip().lower() for item in (fallback_skeleton or []) if str(item).strip()]
    normalized_risk = str(risk_flag or "").strip().lower() or "green"
    normalized_track = normalize_track_name(track)
    hard_session_budget = sum(1 for token in skeleton if token in HARD_SESSION_TAGS)
    if normalized_risk in _RED_TIER_FLAGS:
        hard_session_budget = 0
    elif normalized_risk == "yellow":
        hard_session_budget = min(1, hard_session_budget)

    if "volume_reduce_50pct" in (adjustments or []):
        volume_adjustment_pct = -50
    elif "volume_reduce_30pct" in (adjustments or []):
        volume_adjustment_pct = -30
    elif any(token.startswith("deload_volume_reduce_") for token in (adjustments or []) + skeleton):
        volume_adjustment_pct = -20
    else:
        volume_adjustment_pct = 0

    suppress_peak_language = normalized_track == "return_or_risk_managed"
    required_safety_note = None
    if normalized_risk == "red_b":
        required_safety_note = "Please stop training and consult a clinician/physio."

    disallowed_patterns = ["back_to_back_hard_days", "make_up_intensity"]
    if normalized_risk in _RED_TIER_FLAGS:
        disallowed_patterns.append("all_intensity")

    priority_sessions = skeleton[:2]
    if routing_context and routing_context.get("anchor_sessions"):
        priority_sessions = [str(item) for item in routing_context.get("anchor_sessions", [])]

    return {
        "classification_label": "deterministic_re3_transition",
        "phase": phase,
        "risk_flag": normalized_risk,
        "track": normalized_track,
        "plan_update_status": plan_update_status,
        "today_action": today_action,
        "adjustments": _dedupe_preserving_order([str(item) for item in (adjustments or [])]),
        "hard_limits": {
            "max_hard_sessions_per_week": hard_session_budget,
            "allow_back_to_back_hard_days": False,
            "volume_adjustment_pct": volume_adjustment_pct,
            "intensity_allowed": normalized_risk not in _RED_TIER_FLAGS and effective_performance_intent,
            "max_sessions_per_week": min(
                len(skeleton),
                max(len(skeleton), _days_available(checkin) or len(skeleton)),
            ) if skeleton else max(1, _days_available(checkin)),
        },
        "weekly_targets": {
            "session_mix": list(skeleton),
            "track_objective": (
                "protect consistency and reduce load"
                if suppress_peak_language
                else "progress with controlled load"
            ),
            "priority_sessions": priority_sessions,
            "disallowed_patterns": _dedupe_preserving_order(disallowed_patterns),
        },
        "messaging_guardrails": {
            "suppress_peak_language": suppress_peak_language,
            "tone": "safety_consistency" if suppress_peak_language else "structured_progress",
            "required_safety_note": required_safety_note,
        },
        "fallback_skeleton": list(skeleton),
        "routing_context": dict(routing_context or {}),
    }


def compose_email_payload(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    final_plan: Dict[str, Any],
    decision_envelope: Dict[str, Any],
) -> Dict[str, Any]:
    if not isinstance(profile, dict):
        raise RuleEngineContractError("profile must be a dict")
    if not isinstance(checkin, dict):
        raise RuleEngineContractError("checkin must be a dict")
    if not isinstance(final_plan, dict):
        raise RuleEngineContractError("final_plan must be a dict")
    if not isinstance(decision_envelope, dict):
        raise RuleEngineContractError("decision_envelope must be a dict")

    risk_flag = str(decision_envelope.get("risk_flag", "")).strip().lower()
    track = str(decision_envelope.get("track", "")).strip().lower()
    plan_update_status = str(decision_envelope.get("plan_update_status", "")).strip().lower()
    messaging_guardrails = decision_envelope.get("messaging_guardrails", {})
    routing_context = final_plan.get("routing_context", {})
    safety_focus = bool(track == "return_or_risk_managed" or messaging_guardrails.get("suppress_peak_language"))
    winning_signal = str(routing_context.get("winning_signal", "default")).strip().lower()
    weekly_skeleton = [str(item) for item in final_plan.get("weekly_skeleton", [])]
    anchor_sessions = [str(item) for item in routing_context.get("anchor_sessions", []) if str(item).strip()]

    if plan_update_status == "unchanged_infeasible_week":
        sessions = ["Optional short mobility/recovery touch only."]
    elif winning_signal == "chaos" and anchor_sessions:
        sessions = [f"Priority: {anchor}" for anchor in anchor_sessions]
        sessions.append("Optional filler only if time remains: easy recovery session.")
    else:
        sessions = [f"session_{idx + 1}: {token}" for idx, token in enumerate(weekly_skeleton)]

    if not sessions:
        sessions = ["Optional short mobility/recovery touch only."]

    if risk_flag == "red_b":
        subject_hint = "This week: stop intensity and get assessed"
        summary = "Pain is the highest-priority signal. Stop training intensity and get clinical input."
        plan_focus_line = "Protect health first. Training progression is paused."
        recovery_target = "Rest, reduce load, and seek clinical guidance before resuming training."
        if_then_rules = [
            "If pain is present at rest or walking, stop training completely.",
            "If symptoms persist or worsen, contact a clinician/physio immediately.",
        ]
    elif risk_flag == "red_a":
        subject_hint = "This week: back off and monitor symptoms"
        summary = "Modify training now: no intensity, low-impact only, and reassess within 24 hours."
        plan_focus_line = "Keep movement easy and symptom-led."
        recovery_target = "Prioritize low-impact movement, sleep, and symptom monitoring."
        if_then_rules = [
            "If pain worsens or alters form, stop training and escalate to a clinician.",
            "If symptoms settle, resume only easy work first.",
        ]
    elif winning_signal == "energy":
        subject_hint = "This week: conserve energy and keep the dose minimal"
        summary = "Energy is the limiting signal, so today stays conservative."
        plan_focus_line = "Protect consistency with the minimum effective dose."
        recovery_target = "Focus on sleep, food, and downshifting overall stress."
        if_then_rules = [
            "If energy drops further, cut the session short rather than forcing completion.",
            "If you rebound tomorrow, resume with caution rather than making up work.",
        ]
    elif winning_signal == "missed_sessions":
        subject_hint = "This week: reset without making up intensity"
        summary = "Missed sessions do not get made up. Rebuild the week around easy work first."
        plan_focus_line = "Resume momentum without chasing missed training."
        recovery_target = "Keep recovery steady while re-establishing rhythm."
        if_then_rules = [
            "If time opens up later, add easy volume only.",
            "Do not stack hard sessions to compensate for missed days.",
        ]
    elif winning_signal == "chaos":
        subject_hint = "This week: protect the two anchors"
        summary = "Schedule reality wins. Keep the week alive by protecting the two anchor sessions."
        plan_focus_line = "Anchor the week with one easy aerobic session and one strength/mobility touch."
        recovery_target = "Keep recovery simple: sleep, hydration, and low-friction routines."
        if_then_rules = [
            "If the week gets tighter, keep only the anchors.",
            "Any extra session should stay easy and optional.",
        ]
    elif safety_focus:
        subject_hint = "This week: stay safe and keep it steady"
        summary = "This is a risk-managed week: consistency and symptom control matter more than progression."
        plan_focus_line = "Use safety and consistency as the primary filter."
        recovery_target = "Prioritize recovery basics before adding any load."
        if_then_rules = [
            "If symptoms rise, remove intensity immediately.",
            "If the week destabilizes, keep only the easiest anchor sessions.",
        ]
    else:
        subject_hint = "This week: execute with control"
        summary = "Training can continue, but keep execution controlled and responsive to the week."
        plan_focus_line = "Hit the key sessions without forcing extra load."
        recovery_target = "Support the work with steady sleep and simple recovery habits."
        if_then_rules = [
            "If pain or fatigue rises meaningfully, downgrade the session to easy.",
            "Do not make up missed intensity later in the week.",
        ]

    safety_note = str(
        messaging_guardrails.get("required_safety_note")
        or "No hard sessions when risk is red-tier."
    ).strip()
    disclaimer_short = ""
    if risk_flag == "red_b":
        disclaimer_short = "Please stop training and consult a clinician/physio."

    technique_cue = "Keep effort smooth, relaxed, and technically tidy."
    if str(profile.get("main_sport_current", "")).strip().lower() == "run":
        technique_cue = "Keep cadence light and posture tall."

    payload = {
        "subject_hint": subject_hint,
        "summary": summary,
        "sessions": sessions,
        "plan_focus_line": plan_focus_line,
        "technique_cue": technique_cue,
        "recovery_target": recovery_target,
        "if_then_rules": if_then_rules,
        "disclaimer_short": disclaimer_short,
        "safety_note": safety_note,
    }
    validate_rule_engine_output(
        {
            "classification_label": "compatibility_check",
            "track": decision_envelope.get("track", "general_low_time"),
            "phase": decision_envelope.get("phase", "base"),
            "risk_flag": risk_flag or "green",
            "weekly_skeleton": weekly_skeleton,
            "today_action": final_plan.get("today_action", "proceed_as_planned"),
            "plan_update_status": decision_envelope.get("plan_update_status", "updated"),
            "adjustments": final_plan.get("adjustments", []),
            "next_email_payload": payload,
        }
    )
    return payload


def _count_trailing_matches(phases: List[str], target_phase: str) -> int:
    count = 0
    for phase in reversed(phases):
        if phase != target_phase:
            break
        count += 1
    return count


def detect_inconsistent_training(
    phase_history: List[str],
    current_phase: str,
    risk_flag: str,
) -> bool:
    if not isinstance(phase_history, list):
        raise RuleEngineStabilizationError("phase_history must be a list")

    normalized_history = [_normalize_phase(phase, fallback="") for phase in phase_history]
    normalized_current = _normalize_phase(current_phase, fallback="")
    normalized_risk = str(risk_flag or "").strip().lower()
    if not normalized_history or normalized_risk in _RED_TIER_FLAGS or normalized_current not in _PROGRESSION_PHASES:
        return False
    last_phase = normalized_history[-1]
    if last_phase not in _PROGRESSION_PHASES or normalized_current == last_phase:
        return False
    return abs(_PHASE_ORDER[normalized_current] - _PHASE_ORDER[last_phase]) >= 1


def apply_phase_upgrade_hysteresis(
    phase_history: List[str],
    current_phase: str,
    risk_flag: str,
    *,
    prior_upgrade_streak: int = 0,
) -> str:
    if not isinstance(phase_history, list):
        raise RuleEngineStabilizationError("phase_history must be a list")

    normalized_history = [_normalize_phase(phase, fallback="") for phase in phase_history]
    normalized_current = _normalize_phase(current_phase, fallback="")
    normalized_risk = str(risk_flag or "").strip().lower()
    if normalized_current not in _PROGRESSION_PHASES:
        return normalized_current
    if not normalized_history:
        return normalized_current

    last_phase = normalized_history[-1]
    if last_phase not in _PROGRESSION_PHASES or normalized_risk in _RED_TIER_FLAGS:
        return normalized_current
    if _PHASE_ORDER[normalized_current] <= _PHASE_ORDER[last_phase]:
        return normalized_current
    if max(0, _coerce_int(prior_upgrade_streak, default=0)) + 1 >= _REQUIRED_CONSECUTIVE_UPGRADE_CHECKINS:
        return normalized_current
    return last_phase
