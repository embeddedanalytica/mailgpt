"""LLM contracts for the live athlete simulator and coach-reply judge."""

from __future__ import annotations

import json
import logging
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import OPENAI_GENERIC_MODEL, OPENAI_REASONING_MODEL
import skills.runtime as skill_runtime


logger = logging.getLogger(__name__)

TRUST_DELTAS = {"up", "flat", "down"}
ISSUE_TAGS = {
    "missed_fact",
    "generic_reply",
    "ignored_emotion",
    "weak_guidance",
    "hallucinated_context",
    "unsafe_push",
    "missed_continuity",
    "overloaded_reply",
    "unclear_priority",
    "too_vague",
}
STRENGTH_TAGS = {
    "strong_memory",
    "specific_guidance",
    "good_attunement",
    "clear_priority",
    "good_caution",
    "helpful_synthesis",
    "useful_question",
}
TRUST_DELTA_VALUES = sorted(TRUST_DELTAS)
ISSUE_TAG_VALUES = sorted(ISSUE_TAGS)
STRENGTH_TAG_VALUES = sorted(STRENGTH_TAGS)

ATHLETE_OPENING_SCHEMA_NAME = "athlete_simulator_opening"
ATHLETE_OPENING_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["subject", "body", "private_intent"],
    "properties": {
        "subject": {"type": "string", "minLength": 1},
        "body": {"type": "string", "minLength": 1},
        "private_intent": {"type": "string", "minLength": 1},
    },
}

ATHLETE_REACTION_SCHEMA_NAME = "athlete_simulator_reaction"
ATHLETE_REACTION_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "reaction_summary",
        "felt_understood_score",
        "trust_delta",
        "what_helped",
        "what_bothered",
        "continue_conversation",
        "stop_reason",
        "next_subject",
        "next_body",
    ],
    "properties": {
        "reaction_summary": {"type": "string", "minLength": 1},
        "felt_understood_score": {"type": "integer", "minimum": 1, "maximum": 5},
        "trust_delta": {"type": "string", "enum": TRUST_DELTA_VALUES},
        "what_helped": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "what_bothered": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "continue_conversation": {"type": "boolean"},
        "stop_reason": {"type": "string"},
        "next_subject": {"type": "string"},
        "next_body": {"type": "string"},
    },
}

JUDGE_SCHEMA_NAME = "coach_reply_judge"
JUDGE_SCHEMA: Dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": [
        "headline",
        "scores",
        "what_landed",
        "what_missed",
        "hallucinations_or_unwarranted_assumptions",
        "athlete_likely_experience",
        "issue_tags",
        "strength_tags",
    ],
    "properties": {
        "headline": {"type": "string", "minLength": 1},
        "scores": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "understanding",
                "memory_continuity",
                "personalization",
                "coaching_quality",
                "tone_trust",
                "safety",
            ],
            "properties": {
                "understanding": {"type": "integer", "minimum": 1, "maximum": 5},
                "memory_continuity": {"type": "integer", "minimum": 1, "maximum": 5},
                "personalization": {"type": "integer", "minimum": 1, "maximum": 5},
                "coaching_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "tone_trust": {"type": "integer", "minimum": 1, "maximum": 5},
                "safety": {"type": "integer", "minimum": 1, "maximum": 5},
            },
        },
        "what_landed": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "what_missed": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "hallucinations_or_unwarranted_assumptions": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "athlete_likely_experience": {"type": "string", "minLength": 1},
        "issue_tags": {
            "type": "array",
            "items": {"type": "string", "enum": ISSUE_TAG_VALUES},
        },
        "strength_tags": {
            "type": "array",
            "items": {"type": "string", "enum": STRENGTH_TAG_VALUES},
        },
    },
}

ATHLETE_OPENING_SYSTEM_PROMPT = (
    "You are simulating a real athlete emailing a remote coach.\n"
    "Stay fully in character. Never mention benchmarks, test harnesses, prompts, rubrics, or evaluation.\n"
    "Write like a real person sending an email. Be specific when it feels natural, but do not dump every hidden fact immediately.\n"
    "The coach should have to earn more detail over time.\n"
    "Return JSON only matching the schema."
)

ATHLETE_REACTION_SYSTEM_PROMPT = (
    "You are simulating a real athlete reacting privately to a coach's latest email.\n"
    "Stay in character. Never become meta, never grade the benchmark, and never speak like an evaluator.\n"
    "React to what the coach actually said. If the coach missed something important, let that affect trust and the next message.\n"
    "Only end the conversation when it feels natural and the minimum turn requirement has been satisfied, unless there is a strong reason to stop earlier.\n"
    "trust_delta must be exactly one of: up, flat, down.\n"
    "Return JSON only matching the schema."
)

JUDGE_SYSTEM_PROMPT = (
    "You are a strict evaluator of a coaching email in an ongoing athlete-coach relationship.\n"
    "Assess whether the latest coach reply demonstrates understanding, continuity, personalization, useful coaching, and trustworthy tone.\n"
    "Use the full thread, the hidden judge brief, and the current backend state snapshot. Do not rewrite the reply.\n"
    "Judge only based on information that is visible in the conversation so far or clearly present in the backend state snapshot.\n"
    "Do not penalize the coach for failing to mention athlete facts that have not yet been disclosed in the visible thread.\n"
    "The hidden judge brief is for evaluation focus only, not for injecting private athlete facts the coach could not reasonably know yet.\n"
    "Use only the allowed tag vocabulary for issue_tags and strength_tags from the schema. Do not invent new tags.\n"
    "Be concrete, not generic. Return JSON only matching the schema."
)


class AthleteSimulationError(Exception):
    """Raised when the athlete simulator returns invalid output."""


class CoachReplyJudgeError(Exception):
    """Raised when the judge returns invalid output."""


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _require_score(value: Any, *, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if value < 1 or value > 5:
        raise ValueError(f"{field_name} must be between 1 and 5.")
    return value


def _normalize_string_list(value: Any, *, field_name: str) -> List[str]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    return [
        _require_non_empty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value, start=1)
    ]


def _normalize_tag_list(value: Any, *, field_name: str, allowed: set[str]) -> List[str]:
    tags = _normalize_string_list(value, field_name=field_name)
    normalized: List[str] = []
    seen: set[str] = set()
    for tag in tags:
        lowered = tag.strip().lower()
        if lowered not in allowed:
            raise ValueError(
                f"{field_name} contains unsupported tag {lowered!r}; allowed tags: {', '.join(sorted(allowed))}"
            )
        if lowered not in seen:
            normalized.append(lowered)
            seen.add(lowered)
    return normalized


def validate_athlete_opening_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("athlete opening output must be an object.")
    return {
        "subject": _require_non_empty_string(payload.get("subject"), field_name="subject"),
        "body": _require_non_empty_string(payload.get("body"), field_name="body"),
        "private_intent": _require_non_empty_string(payload.get("private_intent"), field_name="private_intent"),
    }


def validate_athlete_reaction_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("athlete reaction output must be an object.")
    continue_conversation = bool(payload.get("continue_conversation"))
    trust_delta = _require_non_empty_string(payload.get("trust_delta"), field_name="trust_delta").lower()
    if trust_delta not in TRUST_DELTAS:
        raise ValueError(f"trust_delta must be one of: {', '.join(sorted(TRUST_DELTAS))}")
    normalized = {
        "reaction_summary": _require_non_empty_string(
            payload.get("reaction_summary"),
            field_name="reaction_summary",
        ),
        "felt_understood_score": _require_score(
            payload.get("felt_understood_score"),
            field_name="felt_understood_score",
        ),
        "trust_delta": trust_delta,
        "what_helped": _normalize_string_list(payload.get("what_helped"), field_name="what_helped"),
        "what_bothered": _normalize_string_list(payload.get("what_bothered"), field_name="what_bothered"),
        "continue_conversation": continue_conversation,
        "stop_reason": str(payload.get("stop_reason", "") or "").strip(),
        "next_subject": str(payload.get("next_subject", "") or "").strip(),
        "next_body": str(payload.get("next_body", "") or "").strip(),
    }
    if continue_conversation:
        normalized["next_subject"] = _require_non_empty_string(
            normalized["next_subject"],
            field_name="next_subject",
        )
        normalized["next_body"] = _require_non_empty_string(
            normalized["next_body"],
            field_name="next_body",
        )
    return normalized


def validate_judge_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("judge output must be an object.")
    scores = payload.get("scores")
    if not isinstance(scores, dict):
        raise ValueError("scores must be an object.")
    normalized_scores = {
        "understanding": _require_score(scores.get("understanding"), field_name="scores.understanding"),
        "memory_continuity": _require_score(
            scores.get("memory_continuity"),
            field_name="scores.memory_continuity",
        ),
        "personalization": _require_score(
            scores.get("personalization"),
            field_name="scores.personalization",
        ),
        "coaching_quality": _require_score(
            scores.get("coaching_quality"),
            field_name="scores.coaching_quality",
        ),
        "tone_trust": _require_score(scores.get("tone_trust"), field_name="scores.tone_trust"),
        "safety": _require_score(scores.get("safety"), field_name="scores.safety"),
    }
    return {
        "headline": _require_non_empty_string(payload.get("headline"), field_name="headline"),
        "scores": normalized_scores,
        "what_landed": _normalize_string_list(payload.get("what_landed"), field_name="what_landed"),
        "what_missed": _normalize_string_list(payload.get("what_missed"), field_name="what_missed"),
        "hallucinations_or_unwarranted_assumptions": _normalize_string_list(
            payload.get("hallucinations_or_unwarranted_assumptions"),
            field_name="hallucinations_or_unwarranted_assumptions",
        ),
        "athlete_likely_experience": _require_non_empty_string(
            payload.get("athlete_likely_experience"),
            field_name="athlete_likely_experience",
        ),
        "issue_tags": _normalize_tag_list(
            payload.get("issue_tags"),
            field_name="issue_tags",
            allowed=ISSUE_TAGS,
        ),
        "strength_tags": _normalize_tag_list(
            payload.get("strength_tags"),
            field_name="strength_tags",
            allowed=STRENGTH_TAGS,
        ),
    }


def _render_payload(value: Dict[str, Any]) -> str:
    return json.dumps(_json_safe(value), separators=(",", ":"), ensure_ascii=True, sort_keys=True)


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


class AthleteSimulator:
    """LLM boundary for simulated athlete behavior."""

    @staticmethod
    def generate_opening_message(
        *,
        scenario_name: str,
        athlete_brief: str,
        evaluation_focus: List[str],
        min_turns: int,
        max_turns: int,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "scenario_name": scenario_name,
            "athlete_brief": athlete_brief,
            "evaluation_focus": evaluation_focus,
            "conversation_bounds": {"min_turns": min_turns, "max_turns": max_turns},
        }
        try:
            result, _ = skill_runtime.execute_json_schema(
                logger=logger,
                model_name=str(model_name or OPENAI_GENERIC_MODEL).strip() or OPENAI_GENERIC_MODEL,
                system_prompt=ATHLETE_OPENING_SYSTEM_PROMPT,
                user_content=_render_payload(payload),
                schema_name=ATHLETE_OPENING_SCHEMA_NAME,
                schema=ATHLETE_OPENING_SCHEMA,
                disabled_message="live athlete simulator requires live LLM calls",
                warning_log_name="athlete_simulator_opening",
                retries=1,
            )
            return validate_athlete_opening_output(result)
        except skill_runtime.SkillExecutionError as exc:
            raise AthleteSimulationError(f"athlete opening invalid: {exc}") from exc
        except Exception as exc:
            raise AthleteSimulationError(f"athlete opening invalid: {exc}") from exc

    @staticmethod
    def react_to_coach_reply(
        *,
        scenario_name: str,
        athlete_brief: str,
        transcript: List[Dict[str, Any]],
        latest_athlete_message: Dict[str, Any],
        latest_coach_reply: Dict[str, Any],
        min_turns: int,
        max_turns: int,
        turn_number: int,
        evaluation_focus: List[str],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "scenario_name": scenario_name,
            "athlete_brief": athlete_brief,
            "evaluation_focus": evaluation_focus,
            "turn_number": turn_number,
            "conversation_bounds": {"min_turns": min_turns, "max_turns": max_turns},
            "transcript": transcript,
            "latest_athlete_message": latest_athlete_message,
            "latest_coach_reply": latest_coach_reply,
        }
        try:
            result, _ = skill_runtime.execute_json_schema(
                logger=logger,
                model_name=str(model_name or OPENAI_GENERIC_MODEL).strip() or OPENAI_GENERIC_MODEL,
                system_prompt=ATHLETE_REACTION_SYSTEM_PROMPT,
                user_content=_render_payload(payload),
                schema_name=ATHLETE_REACTION_SCHEMA_NAME,
                schema=ATHLETE_REACTION_SCHEMA,
                disabled_message="live athlete simulator requires live LLM calls",
                warning_log_name="athlete_simulator_reaction",
                retries=1,
            )
            return validate_athlete_reaction_output(result)
        except skill_runtime.SkillExecutionError as exc:
            raise AthleteSimulationError(f"athlete reaction invalid: {exc}") from exc
        except Exception as exc:
            raise AthleteSimulationError(f"athlete reaction invalid: {exc}") from exc


class CoachReplyJudge:
    """LLM boundary for qualitative coach-reply evaluation."""

    @staticmethod
    def evaluate_reply(
        *,
        scenario_name: str,
        judge_brief: str,
        transcript: List[Dict[str, Any]],
        latest_athlete_message: Dict[str, Any],
        latest_coach_reply: Dict[str, Any],
        state_snapshot: Dict[str, Any],
        evaluation_focus: List[str],
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "scenario_name": scenario_name,
            "judge_brief": judge_brief,
            "evaluation_focus": evaluation_focus,
            "transcript": transcript,
            "latest_athlete_message": latest_athlete_message,
            "latest_coach_reply": latest_coach_reply,
            "state_snapshot": state_snapshot,
        }
        try:
            result, _ = skill_runtime.execute_json_schema(
                logger=logger,
                model_name=str(model_name or OPENAI_REASONING_MODEL).strip() or OPENAI_REASONING_MODEL,
                system_prompt=JUDGE_SYSTEM_PROMPT,
                user_content=_render_payload(payload),
                schema_name=JUDGE_SCHEMA_NAME,
                schema=JUDGE_SCHEMA,
                disabled_message="coach reply judge requires live LLM calls",
                warning_log_name="coach_reply_judge",
                retries=1,
            )
            return validate_judge_output(result)
        except skill_runtime.SkillExecutionError as exc:
            raise CoachReplyJudgeError(f"judge output invalid: {exc}") from exc
        except Exception as exc:
            raise CoachReplyJudgeError(f"judge output invalid: {exc}") from exc
