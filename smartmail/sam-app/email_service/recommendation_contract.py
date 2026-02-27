"""
Recommendation contract (v1) for athlete-state-informed coaching outputs.

This module is the source of truth for recommendation payload structure.
All producers and consumers should import and validate these dataclasses.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


CONTRACT_VERSION_V1 = "v1"
ALLOWED_EVIDENCE_WINDOWS = {7, 14, 28}
MAX_SUMMARY_LENGTH = 4000
MAX_RECOMMENDATION_LENGTH = 4000
MAX_REASON_LENGTH = 4000
MAX_RISK_FLAGS = 20
MAX_RISK_FLAG_LENGTH = 120
MAX_MODEL_NAME_LENGTH = 120
MAX_PROMPT_VERSION_LENGTH = 120
MAX_CORRELATION_ID_LENGTH = 200
MAX_FOCUS_AREA_LENGTH = 120


class RecommendationContractError(ValueError):
    """Raised when contract validation fails."""


def _require_non_empty_str(field_name: str, value: Any, *, max_len: Optional[int] = None) -> None:
    if not isinstance(value, str) or not value.strip():
        raise RecommendationContractError(f"{field_name} must be a non-empty string")
    if max_len is not None and len(value) > max_len:
        raise RecommendationContractError(f"{field_name} exceeds max length {max_len}")


def _require_optional_str(field_name: str, value: Any, *, max_len: Optional[int] = None) -> None:
    if value is None:
        return
    if not isinstance(value, str):
        raise RecommendationContractError(f"{field_name} must be a string or None")
    if max_len is not None and len(value) > max_len:
        raise RecommendationContractError(f"{field_name} exceeds max length {max_len}")


def _require_positive_int(field_name: str, value: Any) -> None:
    if not isinstance(value, int) or value < 1:
        raise RecommendationContractError(f"{field_name} must be an integer >= 1")


def _require_non_negative_int_or_none(field_name: str, value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, int) or value < 0:
        raise RecommendationContractError(f"{field_name} must be an integer >= 0 or None")


@dataclass(frozen=True)
class AthleteState:
    athlete_id: str
    email: str
    goal: Optional[str]
    current_plan_summary: Optional[str]
    current_plan_version: Optional[int]
    recent_activity_summary: str
    window_days: int
    generated_at_epoch: int
    last_recommendation_text: Optional[str]
    last_recommendation_epoch: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "athlete_id": self.athlete_id,
            "email": self.email,
            "goal": self.goal,
            "current_plan_summary": self.current_plan_summary,
            "current_plan_version": self.current_plan_version,
            "recent_activity_summary": self.recent_activity_summary,
            "window_days": self.window_days,
            "generated_at_epoch": self.generated_at_epoch,
            "last_recommendation_text": self.last_recommendation_text,
            "last_recommendation_epoch": self.last_recommendation_epoch,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AthleteState":
        state = cls(
            athlete_id=data.get("athlete_id"),
            email=data.get("email"),
            goal=data.get("goal"),
            current_plan_summary=data.get("current_plan_summary"),
            current_plan_version=data.get("current_plan_version"),
            recent_activity_summary=data.get("recent_activity_summary"),
            window_days=data.get("window_days"),
            generated_at_epoch=data.get("generated_at_epoch"),
            last_recommendation_text=data.get("last_recommendation_text"),
            last_recommendation_epoch=data.get("last_recommendation_epoch"),
        )
        validate_athlete_state(state)
        return state


@dataclass(frozen=True)
class Recommendation:
    recommendation_text: str
    why: str
    confidence: float
    risk_flags: List[str]
    next_check_in_days: int
    focus_area: Optional[str]
    evidence_window_days: int
    prompt_version: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "recommendation_text": self.recommendation_text,
            "why": self.why,
            "confidence": self.confidence,
            "risk_flags": list(self.risk_flags),
            "next_check_in_days": self.next_check_in_days,
            "focus_area": self.focus_area,
            "evidence_window_days": self.evidence_window_days,
            "prompt_version": self.prompt_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Recommendation":
        rec = cls(
            recommendation_text=data.get("recommendation_text"),
            why=data.get("why"),
            confidence=data.get("confidence"),
            risk_flags=data.get("risk_flags"),
            next_check_in_days=data.get("next_check_in_days"),
            focus_area=data.get("focus_area"),
            evidence_window_days=data.get("evidence_window_days"),
            prompt_version=data.get("prompt_version"),
        )
        validate_recommendation(rec)
        return rec


@dataclass(frozen=True)
class RecommendationContext:
    state: AthleteState
    recommendation: Recommendation
    model_name: str
    created_at_epoch: int
    correlation_id: str
    contract_version: str = CONTRACT_VERSION_V1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "state": self.state.to_dict(),
            "recommendation": self.recommendation.to_dict(),
            "model_name": self.model_name,
            "created_at_epoch": self.created_at_epoch,
            "correlation_id": self.correlation_id,
            "contract_version": self.contract_version,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "RecommendationContext":
        state = AthleteState.from_dict(data.get("state") or {})
        recommendation = Recommendation.from_dict(data.get("recommendation") or {})
        ctx = cls(
            state=state,
            recommendation=recommendation,
            model_name=data.get("model_name"),
            created_at_epoch=data.get("created_at_epoch"),
            correlation_id=data.get("correlation_id"),
            contract_version=data.get("contract_version", CONTRACT_VERSION_V1),
        )
        validate_recommendation_context(ctx)
        return ctx


def validate_athlete_state(state: AthleteState) -> None:
    _require_non_empty_str("athlete_id", state.athlete_id)
    _require_non_empty_str("email", state.email)
    _require_optional_str("goal", state.goal, max_len=MAX_SUMMARY_LENGTH)
    _require_optional_str(
        "current_plan_summary", state.current_plan_summary, max_len=MAX_SUMMARY_LENGTH
    )
    _require_non_negative_int_or_none("current_plan_version", state.current_plan_version)
    _require_non_empty_str(
        "recent_activity_summary", state.recent_activity_summary, max_len=MAX_SUMMARY_LENGTH
    )
    if state.window_days not in ALLOWED_EVIDENCE_WINDOWS:
        raise RecommendationContractError(
            f"window_days must be one of {sorted(ALLOWED_EVIDENCE_WINDOWS)}"
        )
    _require_positive_int("generated_at_epoch", state.generated_at_epoch)
    _require_optional_str(
        "last_recommendation_text",
        state.last_recommendation_text,
        max_len=MAX_RECOMMENDATION_LENGTH,
    )
    _require_non_negative_int_or_none(
        "last_recommendation_epoch", state.last_recommendation_epoch
    )


def validate_recommendation(recommendation: Recommendation) -> None:
    _require_non_empty_str(
        "recommendation_text",
        recommendation.recommendation_text,
        max_len=MAX_RECOMMENDATION_LENGTH,
    )
    _require_non_empty_str("why", recommendation.why, max_len=MAX_REASON_LENGTH)
    if not isinstance(recommendation.confidence, (int, float)):
        raise RecommendationContractError("confidence must be a number in range [0, 1]")
    confidence = float(recommendation.confidence)
    if confidence < 0.0 or confidence > 1.0:
        raise RecommendationContractError("confidence must be in range [0, 1]")
    if not isinstance(recommendation.risk_flags, list):
        raise RecommendationContractError("risk_flags must be a list")
    if len(recommendation.risk_flags) > MAX_RISK_FLAGS:
        raise RecommendationContractError(f"risk_flags exceeds max length {MAX_RISK_FLAGS}")
    for idx, risk_flag in enumerate(recommendation.risk_flags):
        _require_non_empty_str(f"risk_flags[{idx}]", risk_flag, max_len=MAX_RISK_FLAG_LENGTH)
    _require_positive_int("next_check_in_days", recommendation.next_check_in_days)
    _require_optional_str("focus_area", recommendation.focus_area, max_len=MAX_FOCUS_AREA_LENGTH)
    if recommendation.evidence_window_days not in ALLOWED_EVIDENCE_WINDOWS:
        raise RecommendationContractError(
            "evidence_window_days must be one of "
            f"{sorted(ALLOWED_EVIDENCE_WINDOWS)}"
        )
    _require_non_empty_str(
        "prompt_version",
        recommendation.prompt_version,
        max_len=MAX_PROMPT_VERSION_LENGTH,
    )


def validate_recommendation_context(context: RecommendationContext) -> None:
    if not isinstance(context.state, AthleteState):
        raise RecommendationContractError("state must be an AthleteState")
    if not isinstance(context.recommendation, Recommendation):
        raise RecommendationContractError("recommendation must be a Recommendation")
    validate_athlete_state(context.state)
    validate_recommendation(context.recommendation)
    _require_non_empty_str("model_name", context.model_name, max_len=MAX_MODEL_NAME_LENGTH)
    _require_positive_int("created_at_epoch", context.created_at_epoch)
    _require_non_empty_str(
        "correlation_id", context.correlation_id, max_len=MAX_CORRELATION_ID_LENGTH
    )
    if context.contract_version != CONTRACT_VERSION_V1:
        raise RecommendationContractError(
            f"contract_version must be {CONTRACT_VERSION_V1}"
        )
