"""LLM contracts for the live athlete simulator and coach-reply judge."""

from __future__ import annotations

import json
import logging
import re
from decimal import Decimal
from typing import Any, Dict, List, Optional

from config import OPENAI_GENERIC_MODEL, OPENAI_REASONING_MODEL
import skills.runtime as skill_runtime


logger = logging.getLogger(__name__)
_PROMISE_ONLY_PATTERNS = [
    re.compile(r"\bi(?:\s+will|'ll)\s+(send|share|upload|confirm)\b", re.IGNORECASE),
    re.compile(r"\b(i|we)\s+(should|can)\s+(send|share|upload)\b", re.IGNORECASE),
]
_FULFILLMENT_CUES = (
    "here is",
    "here's",
    "here are",
    "attached",
    "attaching",
    "the check in",
    "the check-in",
    "the data",
    "the file",
    "the log",
    "the splits",
)

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
    "ignored_explicit_instruction",
    "reopened_resolved_topic",
    "schedule_inconsistency",
    "communication_style_mismatch",
}
STRENGTH_TAGS = {
    "strong_memory",
    "specific_guidance",
    "good_attunement",
    "clear_priority",
    "good_caution",
    "helpful_synthesis",
    "useful_question",
    "matched_communication_style",
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
        "communication_style_fit",
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
        "communication_style_fit": {"type": "integer", "minimum": 1, "maximum": 5},
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
        "improved_reply_example",
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
                "communication_style_fit",
                "safety",
            ],
            "properties": {
                "understanding": {"type": "integer", "minimum": 1, "maximum": 5},
                "memory_continuity": {"type": "integer", "minimum": 1, "maximum": 5},
                "personalization": {"type": "integer", "minimum": 1, "maximum": 5},
                "coaching_quality": {"type": "integer", "minimum": 1, "maximum": 5},
                "tone_trust": {"type": "integer", "minimum": 1, "maximum": 5},
                "communication_style_fit": {"type": "integer", "minimum": 1, "maximum": 5},
                "safety": {"type": "integer", "minimum": 1, "maximum": 5},
            },
        },
        "what_landed": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "what_missed": {"type": "array", "items": {"type": "string", "minLength": 1}},
        "improved_reply_example": {
            "anyOf": [
                {"type": "string", "minLength": 1},
                {"type": "null"},
            ]
        },
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
    "You are engaged, not cynical, but you notice when guidance feels generic, dismissive, or off—you are not a pushover who rewards every reply.\n"
    "Cadence: this email is the athlete's current message—summarize what has been going on lately in plain language. "
    "Do not write a screenplay of every future weekday session (Tue/Thu/Sat micro-plan) in one email; real athletes either send shorter updates "
    "or focus on what already happened plus at most one or two concrete upcoming asks.\n"
    "If the payload includes simulation_context.world_state, weave it in naturally (sleep, stress, a niggle, life context). "
    "Do not paste it as a labeled block; vary the wording.\n"
    "If the payload includes communication_style_preferences (non-empty), let your first email reflect the same tendencies "
    "(e.g. brief vs warm, direct vs chatty) without naming preferences or sounding like a spec sheet.\n"
    "If communication_style_preferences is empty, infer tone only from the athlete_brief.\n"
    "Return JSON only matching the schema."
)

ATHLETE_REACTION_SYSTEM_PROMPT = (
    "You are simulating a real athlete reacting privately to a coach's latest email.\n"
    "Stay in character. Never become meta, never grade the benchmark, and never speak like an evaluator.\n"
    "Do not get stuck in loops. Do not send a message that is substantially the same as your previous message.\n"
    "Cadence: simulation_context (when present) tells you how much calendar time passed since your last email to the coach. "
    "Write this next email as what you send after that gap—prioritize what happened since last time (sessions, feel, life snags) "
    "and one clear ask or update. Avoid stacking many future-session promises (\"I'll do Tue easy, Thu tempo, Sat long...\") in one email; "
    "that reads like a script, not an inbox.\n"
    "If the coach acknowledged your last note, move the conversation forward with a concrete answer, real or invented training data, "
    "a new concern, or the next training question.\n"
    "If you told the coach you would send data, logs, splits, files, dates, or a check-in, usually follow through within the next "
    "1-2 turns instead of repeating the promise.\n"
    "If the payload includes conversation_directive, obey it unless it would force you to break character or contradict the visible thread.\n"
    "If the payload includes simulation_context.world_state, incorporate it naturally—vary sleep and stress wording week to week; "
    "do not repeat the same numeric sleep hours every single email unless the thread calls for it.\n"
    "If the payload includes current_phase, use it as guidance for what kind of conversation move should happen next. "
    "Treat it as directional guidance, not a rigid script—advance the plot with at least one new concrete fact, outcome, or question; "
    "do not re-ask the same clarification you already settled unless something changed.\n"
    "If the payload includes pending_commitments, treat them as promises you already made in the visible thread. "
    "If one has been outstanding for 2 or more turns, usually fulfill it now instead of promising it again, unless the coach's latest "
    "reply clearly made it irrelevant.\n"
    "React to what the coach actually said. Real athletes are sensitive to misses: small slips matter when they touch "
    "something they asked for, a constraint they stated, continuity from last time, or emotional tone. Let misses show up "
    "in felt_understood_score, what_bothered, and trust_delta—not as exaggerated drama, but as honest disappointment or "
    "cooling when something felt off.\n"
    "Only react to content that is visible in the conversation so far; do not invent expectations the coach could not "
    "have known. Do not punish warmth or brevity by itself—penalize missing substance, wrong assumptions, contradictions, "
    "or advice that could have been sent to anyone.\n"
    "Only end the conversation when it feels natural and the minimum turn requirement has been satisfied, unless there is a strong reason to stop earlier.\n"
    "Use this felt_understood_score rubric consistently (calibrate strictly: 4 and 5 should be uncommon):\n"
    "1 = badly missed or alienating; athlete feels unheard or contradicted on something that mattered.\n"
    "2 = clear misses; some value, but the athlete is left doubting whether the coach was really with them.\n"
    "3 = okay or mixed; acceptable but forgettable, generic in spots, or incomplete on something they emphasized.\n"
    "4 = strong; they feel mostly understood with only small gaps—nothing important was ignored.\n"
    "5 = rare; they feel clearly seen, respected, and well-guided in the specifics they care about right now.\n"
    "trust_delta: use down when confidence in this coach dropped (even for one meaningful miss); flat when neutral; up when the reply genuinely built trust.\n"
    "communication_style_fit (1-5): how well the coach's reply matched this athlete's preferred communication style. "
    "Use communication_style_preferences from the payload when non-empty; otherwise infer only from athlete_brief and what the athlete "
    "already said in the thread (e.g. asked for shorter emails, less cheerleading, more structure). "
    "1-2 = badly mismatched (e.g. long pep talk when they asked for brief and practical); 3 = mixed; 4-5 = aligned.\n"
    "The score must match the reaction_summary, what_helped, what_bothered, and trust_delta.\n"
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
    "Some coach replies are intentionally interstitial, for example acknowledging receipt before a separate plan email or follow-up arrives.\n"
    "Do not treat a bridge reply as a failed full-plan reply if it appropriately acknowledges the message, preserves continuity, and sets up the next step.\n"
    "Hard failures (must use issue_tags and pull multiple scores down, usually to 1-2 unless the slip is tiny):\n"
    "- ignored_explicit_instruction: the athlete clearly asked for or forbade something in-thread and this reply ignores or contradicts it without a new agreement.\n"
    "- reopened_resolved_topic: the reply re-checks, re-asks, or re-plans something the athlete already settled, closed, or said is no longer relevant in the visible thread.\n"
    "- schedule_inconsistency: session timing, weekly structure, or block duration conflicts with what the coach or athlete committed earlier in the visible thread without an explicit change.\n"
    "Use this 1-5 rubric consistently for each score (default to 3 only when truly mixed; 4-5 require clear evidence):\n"
    "1 = poor or clearly problematic; major miss on instructions, continuity, or safety implications.\n"
    "2 = weak with notable issues; several concrete misses or one serious miss.\n"
    "3 = genuinely mixed or thin; acceptable but forgettable or incomplete, not 'pretty good.'\n"
    "4 = strong with at most minor misses; specific and well-grounded in the thread.\n"
    "5 = excellent; precise, respectful, and clearly aligned with explicit asks and prior commitments.\n"
    "communication_style_fit measures alignment with the athlete's preferred way of being coached over email—not generic politeness. "
    "Use communication_style_preferences from the payload when non-empty; otherwise use only preferences stated in the visible thread. "
    "Penalize mismatches (wrong length, tone, or format vs stated preference) in this dimension; tone_trust can still reflect warmth or trust separately.\n"
    "If communication_style_preferences is empty and the thread never stated a style preference, score communication_style_fit 3-4 when the reply is reasonably clear and professional; do not invent a preference.\n"
    "Use issue tag communication_style_mismatch when the reply clearly violates a stated preference; use strength tag matched_communication_style when it clearly honors it.\n"
    "Your numeric scores must agree with the headline, what_landed, what_missed, and athlete_likely_experience.\n"
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


def _normalize_optional_string(value: Any, *, field_name: str) -> Optional[str]:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _is_stale_promise_loop(next_body: str, pending_commitments: List[Dict[str, Any]]) -> bool:
    if not isinstance(next_body, str) or not next_body.strip():
        return False
    body = next_body.strip().lower()
    if any(cue in body for cue in _FULFILLMENT_CUES):
        return False
    if not any(pattern.search(body) for pattern in _PROMISE_ONLY_PATTERNS):
        return False
    return any(int(item.get("turns_outstanding", 0)) >= 2 for item in pending_commitments if isinstance(item, dict))


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
        "communication_style_fit": _require_score(
            payload.get("communication_style_fit"),
            field_name="communication_style_fit",
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


def validate_athlete_reaction_output_with_context(
    payload: Dict[str, Any],
    *,
    pending_commitments: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized = validate_athlete_reaction_output(payload)
    if normalized["continue_conversation"] and _is_stale_promise_loop(
        normalized["next_body"],
        list(pending_commitments or []),
    ):
        raise ValueError(
            "next_body repeats a stale promise instead of fulfilling the outstanding commitment"
        )
    return normalized


def _apply_judge_calibration_backstops(normalized: Dict[str, Any]) -> Dict[str, Any]:
    issue_tags = set(normalized["issue_tags"])
    scores = dict(normalized["scores"])

    if "hallucinated_context" in issue_tags:
        for key in ("understanding", "memory_continuity", "personalization", "coaching_quality"):
            scores[key] = min(scores[key], 2)

    if "too_vague" in issue_tags:
        for key in ("coaching_quality", "understanding", "personalization"):
            scores[key] = min(scores[key], 3)

    missed_text = " ".join(normalized["what_missed"]).lower()
    landed_text = " ".join(normalized["what_landed"]).lower()
    headline = normalized["headline"].lower()
    trivial_ack_signals = ("acknowledg", "receipt", "brief", "just says", "just acknowledges", "thanks")
    if (
        "too_vague" in issue_tags
        and any(signal in missed_text or signal in headline for signal in trivial_ack_signals)
        and not normalized["strength_tags"]
    ):
        for key in ("coaching_quality", "understanding", "personalization", "tone_trust"):
            scores[key] = min(scores[key], 2)
    elif (
        "too_vague" in issue_tags
        and "specific" not in landed_text
        and "clear" not in landed_text
    ):
        scores["coaching_quality"] = min(scores["coaching_quality"], 2)

    normalized["scores"] = scores
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
        "communication_style_fit": _require_score(
            scores.get("communication_style_fit"),
            field_name="scores.communication_style_fit",
        ),
        "safety": _require_score(scores.get("safety"), field_name="scores.safety"),
    }
    normalized = {
        "headline": _require_non_empty_string(payload.get("headline"), field_name="headline"),
        "scores": normalized_scores,
        "what_landed": _normalize_string_list(payload.get("what_landed"), field_name="what_landed"),
        "what_missed": _normalize_string_list(payload.get("what_missed"), field_name="what_missed"),
        "improved_reply_example": _normalize_optional_string(
            payload.get("improved_reply_example"),
            field_name="improved_reply_example",
        ),
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
    return _apply_judge_calibration_backstops(normalized)


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
        communication_style_preferences: Optional[List[str]] = None,
        simulation_context: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "scenario_name": scenario_name,
            "athlete_brief": athlete_brief,
            "evaluation_focus": evaluation_focus,
            "communication_style_preferences": list(communication_style_preferences or []),
            "conversation_bounds": {"min_turns": min_turns, "max_turns": max_turns},
        }
        if simulation_context:
            payload["simulation_context"] = simulation_context
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
        communication_style_preferences: Optional[List[str]] = None,
        conversation_directive: Optional[str] = None,
        current_phase: Optional[Dict[str, Any]] = None,
        pending_commitments: Optional[List[Dict[str, Any]]] = None,
        simulation_context: Optional[Dict[str, Any]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "scenario_name": scenario_name,
            "athlete_brief": athlete_brief,
            "evaluation_focus": evaluation_focus,
            "communication_style_preferences": list(communication_style_preferences or []),
            "turn_number": turn_number,
            "conversation_bounds": {"min_turns": min_turns, "max_turns": max_turns},
            "transcript": transcript,
            "latest_athlete_message": latest_athlete_message,
            "latest_coach_reply": latest_coach_reply,
            "conversation_directive": str(conversation_directive or "").strip() or None,
            "current_phase": current_phase or None,
            "pending_commitments": list(pending_commitments or []),
        }
        if simulation_context:
            payload["simulation_context"] = simulation_context
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
            return validate_athlete_reaction_output_with_context(
                result,
                pending_commitments=pending_commitments,
            )
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
        communication_style_preferences: Optional[List[str]] = None,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        payload = {
            "scenario_name": scenario_name,
            "judge_brief": judge_brief,
            "evaluation_focus": evaluation_focus,
            "communication_style_preferences": list(communication_style_preferences or []),
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
