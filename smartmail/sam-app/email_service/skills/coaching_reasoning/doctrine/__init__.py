"""Coaching doctrine loader — selective assembly for strategist prompts."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, Optional

from .manifest import (
    CORE_UNIVERSAL_FILES,
    GENERAL_FILES,
    LEGACY_UNIVERSAL_FILES,
    OPTIONAL_UNIVERSAL_ORDER,
    RUNNING_OPTIONAL_ORDER,
    SPORT_ALIASES,
)

_DIR = Path(__file__).parent
_CACHE: dict[str, str] = {}
_META_CACHE: dict[str, dict[str, Any]] = {}

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n", re.DOTALL)

VALID_CATEGORIES = frozenset({"safety_protocol", "anti_pattern", "guidance", "resource"})
VALID_SCOPES = frozenset({"always_on", "purpose", "situation", "backstop", "enricher"})
VALID_COST_TIERS = frozenset({"low", "medium", "high"})

_DEFAULT_META: dict[str, Any] = {
    "priority": 50,
    "category": "guidance",
    "scope": "purpose",
    "purposes": [],
    "sports": [],
    "situations": [],
    "cost_tier": "medium",
}


def _parse_frontmatter_list(value: str) -> list[str]:
    value = value.strip()
    if not (value.startswith("[") and value.endswith("]")):
        return []
    inner = value[1:-1].strip()
    if not inner:
        return []
    items = []
    for item in inner.split(","):
        cleaned = item.strip().strip("'\"")
        if cleaned:
            items.append(cleaned)
    return items


def _parse_frontmatter(text: str) -> tuple[dict[str, Any], str]:
    """Extract YAML frontmatter metadata and return (metadata, body).

    Falls back to defaults if no frontmatter is present.
    """
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return dict(_DEFAULT_META), text

    meta: dict[str, Any] = dict(_DEFAULT_META)
    for line in m.group(1).splitlines():
        line = line.strip()
        if not line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        if key == "priority":
            try:
                meta["priority"] = int(value)
            except ValueError:
                pass
        elif key == "category" and value in VALID_CATEGORIES:
            meta["category"] = value
        elif key == "scope" and value in VALID_SCOPES:
            meta["scope"] = value
        elif key in {"purposes", "sports", "situations"}:
            parsed = _parse_frontmatter_list(value)
            if parsed:
                meta[key] = parsed
            elif value == "[]":
                meta[key] = []
        elif key == "cost_tier" and value in VALID_COST_TIERS:
            meta["cost_tier"] = value

    body = text[m.end():]
    return meta, body


def _load(relative_path: str) -> str:
    if relative_path not in _CACHE:
        raw = (_DIR / relative_path).read_text().strip()
        meta, body = _parse_frontmatter(raw)
        _CACHE[relative_path] = body.strip()
        _META_CACHE[relative_path] = meta
    return _CACHE[relative_path]


def get_doctrine_metadata(relative_path: str) -> dict[str, Any]:
    """Return parsed frontmatter metadata for a doctrine file.

    Loads and caches the file if not already cached.
    """
    if relative_path not in _META_CACHE:
        _load(relative_path)
    return _META_CACHE[relative_path]


def _resolve_sport(sport: Optional[str]) -> Optional[str]:
    """Resolve athlete's sport string to a canonical sport key."""
    normalized = (sport or "").strip().lower()
    if not normalized:
        return None
    for keyword, canonical in SPORT_ALIASES.items():
        if keyword in normalized:
            return canonical
    return None


def _resolve_sport_from_brief(brief: dict[str, Any]) -> Optional[str]:
    athlete_ctx = brief.get("athlete_context")
    if isinstance(athlete_ctx, dict):
        return _resolve_sport(athlete_ctx.get("primary_sport"))
    return None


def _signal_blob(brief: dict[str, Any]) -> str:
    parts: list[str] = []
    parts.append(str(brief.get("reply_mode") or ""))

    athlete_ctx = brief.get("athlete_context")
    if isinstance(athlete_ctx, dict):
        parts.append(str(athlete_ctx.get("constraints_summary") or ""))

    delivery = brief.get("delivery_context")
    if isinstance(delivery, dict):
        parts.append(str(delivery.get("inbound_body") or ""))

    decision = brief.get("decision_context")
    if isinstance(decision, dict):
        parts.append(str(decision.get("risk_flag") or ""))
        if decision.get("clarification_needed"):
            parts.append("clarification_needed")
        rh = decision.get("risk_recent_history")
        if isinstance(rh, list):
            parts.extend(str(x) for x in rh)
        elif rh is not None:
            parts.append(str(rh))

    return " ".join(parts).lower()


_SETBACK_PHRASES = (
    "setback",
    "pain",
    "ache",
    "sore",
    "flare",
    "niggle",
    "injured",
    "injury",
    "rebuild",
    "tendon",
    "strain",
    "sprain",
    "comeback",
    "quiet again",
    "flare-up",
    "backing off",
    "dialing back",
)
_SETBACK_HISTORY_TOKENS = frozenset({"yellow", "red"})

_ILLNESS_PHRASES = (
    "illness",
    "sick",
    "cold",
    "fever",
    "low energy",
    "fatigue",
    "exhausted",
    "rundown",
    "run down",
    "flu",
    "covid",
    "under the weather",
    "not feeling great",
    "wiped",
    "drained",
    "body feels off",
    "coming down with",
)

_TRAVEL_PHRASES = (
    "travel",
    "trip",
    "hotel",
    "limited equipment",
    "schedule disruption",
    "poor sleep",
    "jet lag",
    "timezone",
    "time zone",
    "away from home",
    "chaotic",
    "crazy week",
    "schedule blew up",
    "limited time",
    "conference",
    "late nights",
    "red-eye",
)

_INTENSITY_PHRASES = (
    "intensity",
    "tempo",
    "threshold",
    "strides",
    "workout return",
    "quality return",
    "intervals",
    "interval session",
    "pickup",
    "pickups",
    "quality",
    "progression run",
    "hard session",
    "faster work",
)

_PRESCRIPTION_PHRASES = (
    "next week",
    "plan the week",
    "week look like",
    "map the week",
    "session plan",
    "long run",
    "tempo",
    "threshold",
    "interval",
    "strides",
    "mileage",
    "weekly volume",
    "deload",
    "build week",
    "sessions per week",
    "prescribe",
    "progression",
    " volume",
    "easy day",
    "easy days",
    "easy run",
    "quality session",
)

_READING_PHRASES = ("book", "read", "resource")
_RECOMMEND_TRIGGER = "recommend"

_MILESTONE_PHRASES = (
    "personal best",
    "new pr",
    "new pb",
    "race result",
    "race went",
    "finished the race",
    "finished my race",
    "breakthrough",
    "huge win",
    "milestone",
)

_REFLECTION_PHRASES = (
    "what have you learned about me",
    "what have you learned",
    "what do you notice about me",
    "what are you noticing",
    "reflect",
    "reflection",
    "looking back",
    "what did we learn",
)

_RETURN_PROGRESS_PHRASES = (
    "bring back",
    "return to",
    "resume",
    "reintroduce",
    "add back",
    "progress again",
    "ramp back up",
)

_PLANNING_PHRASES = (
    "next week",
    "plan the week",
    "week look like",
    "map the week",
    "what should the week look like",
    "what should next week look like",
    "build the week",
    "structure the week",
    "session structure",
    "training composition",
)

_MUTATION_PHRASES = (
    "swap",
    "move",
    "shift",
    "reorder",
    "reschedule",
    "change",
    "adjust",
    "replace",
    "instead of",
    "push back",
    "pull forward",
    "make thursday easier",
    "make friday easier",
)

_PLAN_STRUCTURE_TOKENS = (
    "this week",
    "current plan",
    "planned",
    "already scheduled",
    "on the calendar",
)

_DIRECT_QUESTION_PREFIXES = (
    "can ",
    "could ",
    "should ",
    "would ",
    "what ",
    "when ",
    "how ",
    "do ",
    "is ",
    "are ",
)

_SIGNAL_STRENGTH_ORDER = {"none": 0, "weak": 1, "strong": 2}


def _has_setback_signals(blob: str, brief: dict[str, Any]) -> bool:
    if any(p in blob for p in _SETBACK_PHRASES):
        return True
    decision = brief.get("decision_context")
    if not isinstance(decision, dict):
        return False
    rh = decision.get("risk_recent_history")
    if not isinstance(rh, list):
        return False
    for entry in rh:
        token = str(entry).strip().lower()
        if token in _SETBACK_HISTORY_TOKENS:
            return True
    return False


def _has_illness_signals(blob: str) -> bool:
    return any(p in blob for p in _ILLNESS_PHRASES)


def _has_travel_signals(blob: str) -> bool:
    return any(p in blob for p in _TRAVEL_PHRASES)


def _has_intensity_signals(blob: str) -> bool:
    if any(p in blob for p in _INTENSITY_PHRASES):
        return True
    return "steady" in blob and any(
        token in blob
        for token in ("session", "work", "workout", "run", "next week", "plan")
    )


def _needs_common_failures_backstop(
    brief: dict[str, Any], blob: str, *, setback: bool, intensity: bool
) -> bool:
    decision = brief.get("decision_context")
    if isinstance(decision, dict):
        if decision.get("clarification_needed"):
            return True
        flag = str(decision.get("risk_flag") or "").strip().lower()
        if flag in {"yellow", "red"}:
            return True
    if setback or intensity:
        return True
    if "clarification" in blob:
        return True
    return False


def _has_prescription_signals(blob: str) -> bool:
    return any(p in blob for p in _PRESCRIPTION_PHRASES)


def _wants_running_reading_recommendations(blob: str) -> bool:
    if _RECOMMEND_TRIGGER not in blob:
        return False
    return any(p in blob for p in _READING_PHRASES)


def _extract_inbound_body(brief: dict[str, Any]) -> str:
    delivery = brief.get("delivery_context")
    if isinstance(delivery, dict):
        return str(delivery.get("inbound_body") or "").lower()
    return ""


def _extract_constraints_summary(brief: dict[str, Any]) -> str:
    athlete_ctx = brief.get("athlete_context")
    if isinstance(athlete_ctx, dict):
        return str(athlete_ctx.get("constraints_summary") or "").lower()
    return ""


def _extract_open_loops(brief: dict[str, Any]) -> str:
    memory_ctx = brief.get("memory_context")
    if not isinstance(memory_ctx, dict):
        return ""
    continuity = memory_ctx.get("continuity_summary")
    if not isinstance(continuity, dict):
        return ""
    open_loops = continuity.get("open_loops")
    if isinstance(open_loops, list):
        return " ".join(str(item) for item in open_loops).lower()
    return str(open_loops or "").lower()


def _contains_any(text: str, phrases: tuple[str, ...]) -> bool:
    return any(phrase in text for phrase in phrases)


def _count_phrase_matches(text: str, phrases: tuple[str, ...]) -> int:
    return sum(1 for phrase in phrases if phrase in text)


def _history_has_risk(brief: dict[str, Any]) -> bool:
    decision = brief.get("decision_context")
    if not isinstance(decision, dict):
        return False
    history = decision.get("risk_recent_history")
    if not isinstance(history, list):
        return False
    return any(str(item).strip().lower() in _SETBACK_HISTORY_TOKENS for item in history)


def _has_known_plan_structure(brief: dict[str, Any]) -> bool:
    validated_plan = brief.get("validated_plan")
    if isinstance(validated_plan, dict) and validated_plan:
        return True
    inbound = _extract_inbound_body(brief)
    return _contains_any(inbound, _PLAN_STRUCTURE_TOKENS)


def _has_real_planning_ask(brief: dict[str, Any], blob: str) -> bool:
    inbound = _extract_inbound_body(brief)
    if _contains_any(inbound, _PLANNING_PHRASES):
        return True
    return _count_phrase_matches(blob, _PRESCRIPTION_PHRASES) >= 2


def _has_real_mutation_ask(brief: dict[str, Any]) -> bool:
    inbound = _extract_inbound_body(brief)
    if not _contains_any(inbound, _MUTATION_PHRASES):
        return False
    return _has_known_plan_structure(brief)


def _has_direct_question(brief: dict[str, Any]) -> bool:
    inbound = _extract_inbound_body(brief).strip()
    if not inbound:
        return False
    if "?" in inbound:
        return True
    return any(inbound.startswith(prefix) for prefix in _DIRECT_QUESTION_PREFIXES)


def _strong_setback_signal(brief: dict[str, Any], blob: str) -> bool:
    decision = brief.get("decision_context")
    risk_flag = ""
    if isinstance(decision, dict):
        risk_flag = str(decision.get("risk_flag") or "").strip().lower()
    inbound = _extract_inbound_body(brief)
    return _contains_any(inbound, _SETBACK_PHRASES) or (
        risk_flag in {"yellow", "red"} and _history_has_risk(brief)
    )


def _derive_setback_strength(brief: dict[str, Any], blob: str) -> str:
    if _strong_setback_signal(brief, blob):
        return "strong"
    if _has_setback_signals(blob, brief):
        return "weak"
    return "none"


def _derive_illness_strength(brief: dict[str, Any]) -> str:
    inbound = _extract_inbound_body(brief)
    if _contains_any(inbound, _ILLNESS_PHRASES):
        return "strong"
    if _contains_any(_extract_constraints_summary(brief), _ILLNESS_PHRASES):
        return "weak"
    return "none"


def _derive_travel_strength(brief: dict[str, Any]) -> str:
    inbound = _extract_inbound_body(brief)
    if _contains_any(inbound, _TRAVEL_PHRASES):
        return "strong"
    supporting = f"{_extract_constraints_summary(brief)} {_extract_open_loops(brief)}".strip()
    if _contains_any(supporting, _TRAVEL_PHRASES):
        return "weak"
    return "none"


def _derive_milestone_strength(brief: dict[str, Any]) -> str:
    if _contains_any(_extract_inbound_body(brief), _MILESTONE_PHRASES):
        return "strong"
    return "none"


def _derive_reflection_strength(brief: dict[str, Any]) -> str:
    if _contains_any(_extract_inbound_body(brief), _REFLECTION_PHRASES):
        return "strong"
    return "none"


def _derive_high_risk_strength(brief: dict[str, Any]) -> str:
    decision = brief.get("decision_context")
    if not isinstance(decision, dict):
        return "none"
    risk_flag = str(decision.get("risk_flag") or "").strip().lower()
    if risk_flag in {"yellow", "red"}:
        return "strong"
    if _history_has_risk(brief):
        return "weak"
    return "none"


def _derive_clarification_strength(brief: dict[str, Any]) -> str:
    if str(brief.get("reply_mode") or "").strip().lower() == "clarification":
        return "strong"
    decision = brief.get("decision_context")
    if isinstance(decision, dict) and decision.get("clarification_needed"):
        return "strong"
    return "none"


def _derive_intensity_return_strength(
    brief: dict[str, Any], blob: str, setback_strength: str
) -> str:
    inbound = _extract_inbound_body(brief)
    has_intensity = _has_intensity_signals(blob)
    if not has_intensity:
        return "none"
    if _contains_any(inbound, _RETURN_PROGRESS_PHRASES) or setback_strength != "none":
        return "strong"
    return "weak"


def _derive_prescription_strength(brief: dict[str, Any], blob: str) -> str:
    if _has_real_planning_ask(brief, blob) or _has_real_mutation_ask(brief):
        return "strong"
    if _has_prescription_signals(blob):
        return "weak"
    return "none"


def _is_recovering_trajectory(brief: dict[str, Any]) -> bool:
    decision = brief.get("decision_context")
    if not isinstance(decision, dict):
        return False
    risk_flag = str(decision.get("risk_flag") or "").strip().lower()
    history = decision.get("risk_recent_history")
    if risk_flag != "green" or not isinstance(history, list):
        return False
    return any(str(item).strip().lower() in _SETBACK_HISTORY_TOKENS for item in history)


def _derive_trajectory(brief: dict[str, Any]) -> str:
    decision = brief.get("decision_context")
    if isinstance(decision, dict):
        risk_flag = str(decision.get("risk_flag") or "").strip().lower()
        if risk_flag in {"yellow", "red"}:
            return "declining"
    if _is_recovering_trajectory(brief):
        return "recovering"
    return "stable"


def derive_situation_tags(brief: dict[str, Any]) -> dict[str, str]:
    """Derive situation tags with bounded signal strengths."""
    blob = _signal_blob(brief)
    setback_strength = _derive_setback_strength(brief, blob)
    tags = {
        "setback": setback_strength,
        "illness": _derive_illness_strength(brief),
        "travel": _derive_travel_strength(brief),
        "intensity_return": _derive_intensity_return_strength(brief, blob, setback_strength),
        "prescription": _derive_prescription_strength(brief, blob),
        "milestone": _derive_milestone_strength(brief),
        "reflection": _derive_reflection_strength(brief),
        "high_risk": _derive_high_risk_strength(brief),
        "clarification_needed": _derive_clarification_strength(brief),
    }
    return {tag: strength for tag, strength in tags.items() if strength != "none"}


def _strongest_signal(tags: dict[str, str], *names: str) -> bool:
    return any(tags.get(name) == "strong" for name in names)


def derive_turn_purpose(brief: dict[str, Any]) -> str:
    """Derive the primary operational purpose for the turn."""
    reply_mode = str(brief.get("reply_mode") or "").strip().lower()
    blob = _signal_blob(brief)
    tags = derive_situation_tags(brief)
    has_planning = _has_real_planning_ask(brief, blob)
    has_mutation = _has_real_mutation_ask(brief)

    if reply_mode == "clarification" or tags.get("clarification_needed") == "strong":
        return "clarification"
    if reply_mode == "intake":
        return "intake"
    if _strongest_signal(tags, "milestone", "reflection"):
        return "milestone_or_reflection"
    if tags.get("setback") and tags.get("intensity_return") == "strong" and not has_mutation:
        return "return_to_load"
    if _strongest_signal(tags, "setback", "illness", "travel") and not (has_planning or has_mutation):
        return "setback_management"
    if has_mutation and not has_planning:
        return "plan_mutation"
    if has_planning:
        return "planning"
    if _has_direct_question(brief):
        return "lightweight_answer"
    return "simple_acknowledgment"


_PURPOSE_MICRO_AVOID: dict[str, list[str]] = {
    "simple_acknowledgment": [
        "do not offer unsolicited plan changes",
        "do not surface old injury history",
        "do not suggest progression",
    ],
    "lightweight_answer": [
        "do not expand scope beyond the question",
        "do not re-derive the full training plan",
    ],
    "planning": [
        "do not bury the week structure behind recap",
    ],
    "plan_mutation": [
        "do not rebuild the full week unless the current structure no longer works",
    ],
    "setback_management": [
        "do not convert caution language into aggressive prescription",
    ],
    "return_to_load": [
        "do not treat one good week as proof of full readiness",
        "do not progress multiple load levers at once",
    ],
    "milestone_or_reflection": [
        "do not pivot immediately to next-week planning",
        "do not undercut the moment with caveats",
    ],
    "clarification": [
        "do not answer past the missing information",
    ],
    "intake": [
        "do not coach forward before the profile is built",
    ],
}


def derive_control_hints(
    brief: dict[str, Any], *, purpose: Optional[str] = None, situation_tags: Optional[dict[str, str]] = None
) -> dict[str, Any]:
    """Return deterministic, bounded control hints for strategist use."""
    purpose = purpose or derive_turn_purpose(brief)
    situation_tags = situation_tags or derive_situation_tags(brief)
    trajectory = _derive_trajectory(brief)

    posture = "logistics_delivery"
    response_shape = "structure_then_detail"

    if purpose in {"simple_acknowledgment", "lightweight_answer"}:
        posture = "answer_and_release"
        response_shape = "answer_first_then_stop"
    elif purpose in {"setback_management"}:
        posture = "conservative_hold"
        response_shape = "safety_then_next_step"
    elif purpose in {"return_to_load"}:
        posture = "cautious_progress"
        response_shape = "safety_then_next_step"
    elif purpose == "milestone_or_reflection":
        posture = "celebrate_then_pause"
        response_shape = "celebrate_then_synthesize"
    elif purpose in {"clarification", "intake"}:
        posture = "clarify_only"
        response_shape = "clarify_only"

    if purpose in {"planning", "plan_mutation"} and (
        situation_tags.get("high_risk") == "strong" or trajectory != "stable"
    ):
        posture = "cautious_progress"
        response_shape = "safety_then_next_step"

    return {
        "posture": posture,
        "trajectory": trajectory,
        "purpose_micro_avoid": list(_PURPOSE_MICRO_AVOID.get(purpose, [])),
        "response_shape": response_shape,
    }


CATEGORY_BUDGETS: dict[str, int] = {
    "safety_protocol": 3,
    "anti_pattern": 2,
    "guidance": 2,
    "resource": 1,
}

PURPOSE_COST_BUDGETS: dict[str, dict[str, int]] = {
    "simple_acknowledgment": {"low": 99, "medium": 0, "high": 0},
    "lightweight_answer": {"low": 99, "medium": 1, "high": 0},
    "planning": {"low": 99, "medium": 4, "high": 0},
    "plan_mutation": {"low": 99, "medium": 4, "high": 0},
    "setback_management": {"low": 99, "medium": 6, "high": 1},
    "return_to_load": {"low": 99, "medium": 6, "high": 1},
    "milestone_or_reflection": {"low": 99, "medium": 1, "high": 0},
    "clarification": {"low": 99, "medium": 1, "high": 0},
    "intake": {"low": 99, "medium": 0, "high": 0},
}


def _ordered_registered_doctrine_paths() -> list[str]:
    ordered = list(CORE_UNIVERSAL_FILES)
    ordered.extend(path for _, path in OPTIONAL_UNIVERSAL_ORDER)
    ordered.extend(path for _, path in RUNNING_OPTIONAL_ORDER)
    ordered.extend(GENERAL_FILES)
    ordered.extend(LEGACY_UNIVERSAL_FILES)
    seen: set[str] = set()
    result: list[str] = []
    for path in ordered:
        if path not in seen:
            seen.add(path)
            result.append(path)
    return result


def _metadata_matches_sport(meta: dict[str, Any], sport: Optional[str]) -> bool:
    sports = meta.get("sports", [])
    if not sports:
        return True
    return sport in sports


def _minimum_situation_strength_for_purpose(
    purpose: str, situation_name: str, trajectory: str
) -> str:
    if purpose in {"planning", "plan_mutation", "setback_management", "return_to_load"}:
        return "weak"
    if (
        purpose in {"simple_acknowledgment", "lightweight_answer"}
        and situation_name in {"setback", "illness", "travel", "intensity_return"}
        and trajectory != "stable"
    ):
        return "weak"
    return "strong"


def _meets_strength_threshold(strength: str, minimum: str) -> bool:
    return _SIGNAL_STRENGTH_ORDER[strength] >= _SIGNAL_STRENGTH_ORDER[minimum]


def _recommendation_intent_is_explicit(blob: str) -> bool:
    return _wants_running_reading_recommendations(blob) or (
        _RECOMMEND_TRIGGER in blob and any(term in blob for term in _READING_PHRASES)
    )


def _build_backstop_reason(
    brief: dict[str, Any], purpose: str, situation_tags: dict[str, str], blob: str
) -> Optional[str]:
    decision = brief.get("decision_context")
    reply_mode = str(brief.get("reply_mode") or "").strip().lower()
    if isinstance(decision, dict):
        risk_flag = str(decision.get("risk_flag") or "").strip().lower()
        if risk_flag in {"yellow", "red"}:
            return f"risk_flag={risk_flag}"
    active_tag_names = [tag for tag, strength in situation_tags.items() if strength != "none"]
    if len(active_tag_names) >= 2:
        return "multiple_active_situations"
    if purpose == "setback_management":
        return "setback_management"
    if purpose == "return_to_load" and "setback" in situation_tags:
        return "return_to_load_with_setback"
    if purpose in {"planning", "plan_mutation"} and {"setback", "prescription"} <= set(active_tag_names):
        return "planning_with_setback_and_prescription"
    if reply_mode == "clarification" and any(
        tag in situation_tags for tag in {"setback", "illness", "travel", "intensity_return"}
    ):
        return "clarification_with_risk_context"
    return None


def _evaluate_doctrine_candidate(
    path: str,
    *,
    brief: dict[str, Any],
    blob: str,
    sport: Optional[str],
    purpose: str,
    situation_tags: dict[str, str],
    recommendation_intent: bool,
) -> tuple[bool, str]:
    meta = get_doctrine_metadata(path)
    if not _metadata_matches_sport(meta, sport):
        return False, "sport mismatch"

    scope = meta["scope"]
    purposes = set(meta.get("purposes", []))
    situations = list(meta.get("situations", []))
    trajectory = _derive_trajectory(brief)

    if scope == "always_on":
        return True, "always_on"

    if scope == "purpose":
        if purpose in purposes:
            return True, f"purpose={purpose}"
        matched = [
            tag for tag in situations
            if tag in situation_tags and _meets_strength_threshold(
                situation_tags[tag],
                _minimum_situation_strength_for_purpose(purpose, tag, trajectory),
            )
        ]
        if matched:
            strongest = sorted(
                matched,
                key=lambda tag: (-_SIGNAL_STRENGTH_ORDER[situation_tags[tag]], tag),
            )[0]
            return True, f"situation={strongest}:{situation_tags[strongest]}"
        return False, "purpose mismatch"

    if scope == "situation":
        if purpose in purposes:
            return True, f"purpose={purpose}"
        matched = [
            tag for tag in situations
            if tag in situation_tags and _meets_strength_threshold(
                situation_tags[tag],
                _minimum_situation_strength_for_purpose(purpose, tag, trajectory),
            )
        ]
        if matched:
            strongest = sorted(
                matched,
                key=lambda tag: (-_SIGNAL_STRENGTH_ORDER[situation_tags[tag]], tag),
            )[0]
            return True, f"situation={strongest}:{situation_tags[strongest]}"
        blocked = [tag for tag in situations if tag in situation_tags]
        if blocked:
            strongest = sorted(
                blocked,
                key=lambda tag: (-_SIGNAL_STRENGTH_ORDER[situation_tags[tag]], tag),
            )[0]
            return False, f"signal too weak ({strongest}:{situation_tags[strongest]})"
        return False, "situation mismatch"

    if scope == "backstop":
        reason = _build_backstop_reason(brief, purpose, situation_tags, blob)
        if reason:
            return True, reason
        return False, "no backstop condition met"

    if scope == "enricher":
        if recommendation_intent:
            return True, "explicit recommendation intent"
        return False, "recommendation intent not explicit"

    return False, "scope unsupported"


def _select_optional_candidates(
    brief: dict[str, Any], blob: str, sport: Optional[str],
    setback: bool, intensity: bool, purpose: str,
) -> list[str]:
    """Purpose-aware selection of optional doctrine files (no budget applied)."""
    del setback, intensity
    situation_tags = derive_situation_tags(brief)
    recommendation_intent = _recommendation_intent_is_explicit(blob)
    candidates: list[str] = []
    for path in _ordered_registered_doctrine_paths():
        if path in CORE_UNIVERSAL_FILES or path in LEGACY_UNIVERSAL_FILES:
            continue
        load, _ = _evaluate_doctrine_candidate(
            path,
            brief=brief,
            blob=blob,
            sport=sport,
            purpose=purpose,
            situation_tags=situation_tags,
            recommendation_intent=recommendation_intent,
        )
        if load:
            if path == "general/recommendations.md" and sport == "running":
                continue
            candidates.append(path)
    return candidates


def _score_file(path: str, brief: dict[str, Any], blob: str) -> float:
    """Score a candidate file for priority tie-breaking within a category."""
    meta = get_doctrine_metadata(path)
    base = meta["priority"]
    boost = 0

    # Boost for direct signal match in inbound body
    delivery = brief.get("delivery_context")
    if isinstance(delivery, dict):
        body = str(delivery.get("inbound_body") or "").lower()
        if body and path in _SIGNAL_FILE_PHRASES and any(
            p in body for p in _SIGNAL_FILE_PHRASES[path]
        ):
            boost += 15

    # Boost for risk-flag alignment
    decision = brief.get("decision_context")
    if isinstance(decision, dict):
        flag = str(decision.get("risk_flag") or "").strip().lower()
        if flag in {"yellow", "red"} and meta["category"] == "safety_protocol":
            boost += 10

    return base + boost


# Maps doctrine paths to their trigger phrases for body-match boosting
_SIGNAL_FILE_PHRASES: dict[str, tuple[str, ...]] = {
    "universal/return_from_setback.md": _SETBACK_PHRASES,
    "universal/illness_and_low_energy.md": _ILLNESS_PHRASES,
    "universal/travel_and_disruption.md": _TRAVEL_PHRASES,
    "universal/intensity_reintroduction.md": _INTENSITY_PHRASES,
    "running/injury_return_patterns.md": _SETBACK_PHRASES,
    "running/common_prescription_errors.md": _PRESCRIPTION_PHRASES,
}


def _apply_category_budgets(candidates: list[str], brief: dict[str, Any], blob: str) -> list[str]:
    """Apply per-category budgets to candidate files, keeping highest-scored within each category."""
    # Group by category
    by_category: dict[str, list[str]] = {}
    for path in candidates:
        meta = get_doctrine_metadata(path)
        cat = meta["category"]
        by_category.setdefault(cat, []).append(path)

    # Apply budgets
    selected: list[str] = []
    for cat, paths in by_category.items():
        budget = CATEGORY_BUDGETS.get(cat, 2)
        if len(paths) <= budget:
            selected.extend(paths)
        else:
            scored = [(p, _score_file(p, brief, blob)) for p in paths]
            scored.sort(key=lambda x: x[1], reverse=True)
            selected.extend(p for p, _ in scored[:budget])

    # Preserve manifest order (not priority order)
    candidate_set = set(selected)
    return [p for p in candidates if p in candidate_set]


def _is_must_keep_candidate(path: str, purpose: str, brief: dict[str, Any]) -> bool:
    meta = get_doctrine_metadata(path)
    if purpose in set(meta.get("purposes", [])):
        return True
    if meta["scope"] != "backstop":
        return False
    decision = brief.get("decision_context")
    if not isinstance(decision, dict):
        return False
    risk_flag = str(decision.get("risk_flag") or "").strip().lower()
    return risk_flag in {"yellow", "red"} or purpose in {"setback_management", "return_to_load"}


def _apply_cost_budgets(
    candidates: list[str], brief: dict[str, Any], blob: str, purpose: str
) -> tuple[list[str], dict[str, str]]:
    budgets = PURPOSE_COST_BUDGETS.get(purpose, PURPOSE_COST_BUDGETS["planning"])
    dropped: dict[str, str] = {}
    selected: list[str] = []

    by_tier: dict[str, list[str]] = {"low": [], "medium": [], "high": []}
    for path in candidates:
        tier = get_doctrine_metadata(path)["cost_tier"]
        by_tier.setdefault(tier, []).append(path)

    for tier, paths in by_tier.items():
        budget = budgets.get(tier, 0)
        must_keep = [path for path in paths if _is_must_keep_candidate(path, purpose, brief)]
        optional = [path for path in paths if path not in must_keep]
        selected.extend(must_keep)

        remaining = max(0, budget - len(must_keep))
        if remaining:
            scored = [(path, _score_file(path, brief, blob)) for path in optional]
            scored.sort(key=lambda item: item[1], reverse=True)
            kept_optional = [path for path, _ in scored[:remaining]]
            selected.extend(kept_optional)
            dropped_optional = [path for path, _ in scored[remaining:]]
        else:
            dropped_optional = optional

        for path in dropped_optional:
            dropped[path] = f"cost_tier={tier} budget exceeded for purpose={purpose}"

    selected_set = set(selected)
    ordered_selected = [path for path in candidates if path in selected_set]
    return ordered_selected, dropped


def select_doctrine_files(brief: dict[str, Any]) -> list[str]:
    """Deterministic doctrine paths for this response brief (ordered, deduped)."""
    blob = _signal_blob(brief)
    sport = _resolve_sport_from_brief(brief)
    setback = _has_setback_signals(blob, brief)
    intensity = _has_intensity_signals(blob)
    purpose = derive_turn_purpose(brief)

    core: list[str] = list(CORE_UNIVERSAL_FILES)
    candidates = _select_optional_candidates(brief, blob, sport, setback, intensity, purpose)
    budgeted, _ = _apply_cost_budgets(candidates, brief, blob, purpose)

    combined = core + budgeted
    seen: set[str] = set()
    ordered: list[str] = []
    for p in combined:
        if p not in seen:
            seen.add(p)
            ordered.append(p)
    return ordered


def build_doctrine_selection_trace(brief: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic doctrine trace used for observability and tests."""
    blob = _signal_blob(brief)
    sport = _resolve_sport_from_brief(brief)
    purpose = derive_turn_purpose(brief)
    situation_tags = derive_situation_tags(brief)
    control_hints = derive_control_hints(brief, purpose=purpose, situation_tags=situation_tags)
    recommendation_intent = _recommendation_intent_is_explicit(blob)
    unbudgeted_candidates = _select_optional_candidates(
        brief,
        blob,
        sport,
        setback="setback" in situation_tags,
        intensity="intensity_return" in situation_tags,
        purpose=purpose,
    )
    budgeted_candidates, dropped_files = _apply_cost_budgets(
        unbudgeted_candidates,
        brief,
        blob,
        purpose,
    )
    loaded_files = list(CORE_UNIVERSAL_FILES) + budgeted_candidates
    loaded_reasons: dict[str, str] = {}
    skipped_candidates: list[tuple[str, str, int]] = []

    for path in _ordered_registered_doctrine_paths():
        if path in LEGACY_UNIVERSAL_FILES:
            continue
        meta = get_doctrine_metadata(path)
        if not _metadata_matches_sport(meta, sport):
            continue
        load, reason = _evaluate_doctrine_candidate(
            path,
            brief=brief,
            blob=blob,
            sport=sport,
            purpose=purpose,
            situation_tags=situation_tags,
            recommendation_intent=recommendation_intent,
        )
        if path in loaded_files:
            loaded_reasons[path] = reason
        elif meta["scope"] != "always_on":
            skipped_candidates.append((path, reason, int(meta["priority"])))

    skipped_candidates.sort(key=lambda item: (-item[2], item[0]))
    top_skipped = {
        path: reason
        for path, reason, _ in skipped_candidates[:3]
    }

    return {
        "turn_purpose": purpose,
        "situation_tags": [
            {"tag": tag, "strength": strength}
            for tag, strength in sorted(
                situation_tags.items(),
                key=lambda item: (-_SIGNAL_STRENGTH_ORDER[item[1]], item[0]),
            )
        ],
        "posture": control_hints["posture"],
        "trajectory": control_hints["trajectory"],
        "purpose_micro_avoid": control_hints["purpose_micro_avoid"],
        "response_shape": control_hints["response_shape"],
        "loaded_files": loaded_files,
        "loaded_file_reasons": loaded_reasons,
        "dropped_files": dropped_files,
        "skipped_files": top_skipped,
    }


def build_doctrine_context_for_brief(brief: dict[str, Any]) -> str:
    """Assemble doctrine text for the strategist using selective loading."""
    paths = select_doctrine_files(brief)
    sections = [_load(p) for p in paths]
    return "\n\n".join(sections)


def list_loaded_files(brief: dict[str, Any]) -> list[str]:
    """Doctrine paths that would load for this brief (same order as context)."""
    return select_doctrine_files(brief)
