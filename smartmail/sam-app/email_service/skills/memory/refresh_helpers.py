"""Shared continuity cleanup helpers for sectioned memory refresh (extracted from legacy unified runner)."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sectioned_memory_contract import format_unix_timestamp_for_prompt

_TEXT_STOPWORDS = {
    "a", "an", "and", "are", "as", "at", "be", "been", "for", "from", "has",
    "have", "in", "is", "it", "its", "of", "on", "or", "that", "the", "their",
    "this", "to", "was", "were", "with",
}

_REQUEST_CUE_PATTERNS = [
    re.compile(r"\?", re.IGNORECASE),
    re.compile(r"\bcan you\b", re.IGNORECASE),
    re.compile(r"\bcould you\b", re.IGNORECASE),
    re.compile(r"\bplease\b", re.IGNORECASE),
    re.compile(r"\bwhat\b", re.IGNORECASE),
    re.compile(r"\bwhich\b", re.IGNORECASE),
    re.compile(r"\bwhen\b", re.IGNORECASE),
    re.compile(r"\bwhere\b", re.IGNORECASE),
    re.compile(r"\bconfirm\b", re.IGNORECASE),
    re.compile(r"\bsend\b", re.IGNORECASE),
    re.compile(r"\bshare\b", re.IGNORECASE),
    re.compile(r"\btell me\b", re.IGNORECASE),
    re.compile(r"\blet me know\b", re.IGNORECASE),
    re.compile(r"\breply with\b", re.IGNORECASE),
]


def normalize_text_tokens(text: Any) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) >= 3 and token not in _TEXT_STOPWORDS
    }


def fact_reference_tokens(fact: Dict[str, Any]) -> set[str]:
    tokens = normalize_text_tokens(fact.get("summary"))
    tokens.update(normalize_text_tokens(str(fact.get("fact_key", "")).replace(":", " ")))
    return tokens


def materially_references_fact(text: str, fact: Dict[str, Any]) -> bool:
    candidate_tokens = normalize_text_tokens(text)
    fact_tokens = fact_reference_tokens(fact)
    if not candidate_tokens or not fact_tokens:
        return False
    overlap = candidate_tokens & fact_tokens
    if len(overlap) >= 3:
        return True
    smaller = min(len(candidate_tokens), len(fact_tokens))
    negation_markers = {"no", "not", "old", "prior", "retire", "retired", "replace", "replaced", "former"}
    if len(overlap) >= 2 and candidate_tokens & negation_markers:
        return True
    if smaller >= 2 and len(overlap) == smaller:
        return True
    return False


def continuity_segments(continuity: Optional[Dict[str, Any]]) -> List[str]:
    if not isinstance(continuity, dict):
        return []
    segments: List[str] = []
    for field in ("summary", "last_recommendation"):
        value = continuity.get(field)
        if isinstance(value, str) and value.strip():
            segments.append(value.strip())
    for item in continuity.get("open_loops") or []:
        if isinstance(item, str) and item.strip():
            segments.append(item.strip())
    return segments


def contains_request_cues(text: str) -> bool:
    return any(pattern.search(text) for pattern in _REQUEST_CUE_PATTERNS)


def loop_answered_by_athlete(loop: str, inbound_email: str) -> bool:
    loop_tokens = normalize_text_tokens(loop)
    inbound_tokens = normalize_text_tokens(inbound_email)
    overlap = loop_tokens & inbound_tokens
    if len(overlap) >= 3:
        return True
    if len(overlap) >= 2 and any(
        token in loop_tokens for token in {"date", "dates", "day", "days", "time", "times", "travel"}
    ):
        return True
    return False


def prune_resolved_open_loops(
    *,
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
    next_open_loops: List[str],
) -> List[str]:
    if not isinstance(current_continuity, dict):
        return next_open_loops

    inbound_email = interaction_context.get("inbound_email")
    coach_reply = interaction_context.get("coach_reply")
    if not isinstance(inbound_email, str) or not inbound_email.strip():
        return next_open_loops

    coach_reasked = False
    resolved_prior_loops: List[str] = []
    for prior_loop in current_continuity.get("open_loops") or []:
        if not isinstance(prior_loop, str) or not prior_loop.strip():
            continue
        if not loop_answered_by_athlete(prior_loop, inbound_email):
            continue

        coach_reasked = (
            isinstance(coach_reply, str)
            and materially_references_fact(coach_reply, {"summary": prior_loop, "fact_key": ""})
            and contains_request_cues(coach_reply)
        )
        if not coach_reasked:
            resolved_prior_loops.append(prior_loop)

    if not resolved_prior_loops:
        return next_open_loops

    return [
        loop
        for loop in next_open_loops
        if not any(
            materially_references_fact(loop, {"summary": prior_loop, "fact_key": ""})
            for prior_loop in resolved_prior_loops
        )
    ]


_GENERIC_FALLBACK_SEGMENTS = {
    "current coaching context updated.",
    "use the updated current schedule and constraints going forward.",
}


def _is_generic_fallback(segment: str) -> bool:
    return segment.strip().lower().rstrip(".") + "." in _GENERIC_FALLBACK_SEGMENTS


def stale_continuity_carryover_detected(
    *,
    current_continuity: Optional[Dict[str, Any]],
    interaction_context: Dict[str, Any],
    validated: Dict[str, Any],
) -> bool:
    prior_segments = continuity_segments(current_continuity)
    if not prior_segments:
        return False

    latest_context_tokens = normalize_text_tokens(interaction_context.get("inbound_email"))
    latest_context_tokens.update(normalize_text_tokens(interaction_context.get("coach_reply")))

    for segment in prior_segments:
        segment_tokens = normalize_text_tokens(segment)
        if not segment_tokens:
            continue
        # Generic fallback strings are never meaningful carryover — skip them
        # to avoid a self-perpetuating trap where the fallback itself triggers
        # staleness detection on every subsequent turn.
        if _is_generic_fallback(segment):
            continue
        if latest_context_tokens & segment_tokens:
            continue

        for next_segment in continuity_segments(validated.get("continuity")):
            overlap = normalize_text_tokens(next_segment) & segment_tokens
            if len(overlap) >= 3:
                return True
    return False


def drop_segments_referencing_facts(text: str, facts: List[Dict[str, Any]]) -> str:
    if not isinstance(text, str) or not text.strip() or not facts:
        return text
    segments = [segment.strip(" ,;") for segment in re.split(r"[;()]", text) if segment.strip(" ,;")]
    kept_segments = [
        segment
        for segment in segments
        if not any(materially_references_fact(segment, fact) for fact in facts)
    ]
    if not kept_segments:
        return ""
    return "; ".join(kept_segments)


def format_continuity_for_prompt(continuity: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if continuity is None or not isinstance(continuity, dict):
        return None
    formatted: Dict[str, Any] = {}
    for field in ("summary", "last_recommendation"):
        value = continuity.get(field)
        if isinstance(value, str) and value.strip():
            formatted[field] = value.strip()
    open_loops = continuity.get("open_loops")
    if isinstance(open_loops, list):
        formatted["open_loops"] = [
            str(item).strip() for item in open_loops if isinstance(item, str) and str(item).strip()
        ]
    updated_at = continuity.get("updated_at")
    if updated_at is not None:
        try:
            formatted["updated_at_readable"] = format_unix_timestamp_for_prompt(int(updated_at))
        except Exception:
            pass
    return formatted if formatted else None
