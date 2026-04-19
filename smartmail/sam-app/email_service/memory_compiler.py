"""Deterministic prompt compiler for sectioned memory (no LLM)."""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from sectioned_memory_contract import (
    BUCKET_CONSTRAINTS,
    BUCKET_CONTEXT_NOTES,
    BUCKET_GOALS,
    BUCKET_PREFERENCES,
    BUCKET_SCHEDULE_ANCHORS,
    SECTION_CONSTRAINT,
    SECTION_CONTEXT,
    SECTION_GOAL,
    SECTION_PREFERENCE,
    SECTION_SCHEDULE_ANCHOR,
    STATUS_ACTIVE,
    empty_sectioned_memory,
)

_SCHEDULE_SUBTYPE_ORDER = {
    "hard_blocker": 0,
    "recurring_anchor": 1,
    "soft_preference": 2,
    "other": 3,
}
_PREFERENCE_SUBTYPE_ORDER = {
    "communication": 0,
    "planning_style": 1,
    "other": 2,
}
_CONTEXT_SUBTYPE_ORDER = {
    "training_baseline": 0,
    "life_context": 1,
    "equipment": 2,
    "other": 3,
}

MAX_SCHEDULE_IN_PROMPT = 4
MAX_PREFERENCE_IN_PROMPT = 2
MAX_CONTEXT_IN_PROMPT = 3


def _subtype_rank(section: str, subtype: str) -> int:
    if section == SECTION_SCHEDULE_ANCHOR:
        return _SCHEDULE_SUBTYPE_ORDER.get(subtype, 99)
    if section == SECTION_PREFERENCE:
        return _PREFERENCE_SUBTYPE_ORDER.get(subtype, 99)
    if section == SECTION_CONTEXT:
        return _CONTEXT_SUBTYPE_ORDER.get(subtype, 99)
    return 99


def _sort_bounded_facts(facts: List[Dict[str, Any]], section: str) -> List[Dict[str, Any]]:
    def key(f: Dict[str, Any]) -> Tuple[int, int, int, str]:
        st = str(f.get("subtype") or "")
        return (
            _subtype_rank(section, st),
            -int(f.get("last_confirmed_at") or 0),
            -int(f.get("updated_at") or 0),
            str(f.get("memory_id") or ""),
        )

    return sorted(facts, key=key)


def _take_active(bucket: str, memory: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw = memory.get(bucket) or {}
    active = raw.get("active") or []
    out: List[Dict[str, Any]] = []
    for f in active:
        if isinstance(f, dict) and f.get("status") == STATUS_ACTIVE:
            out.append(dict(f))
    return out


def compile_prompt_memory(
    sectioned_memory: Dict[str, Any],
    continuity: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Select bounded, deterministic facts for the response-generation prompt."""
    if not isinstance(sectioned_memory, dict):
        sectioned_memory = empty_sectioned_memory()

    goals = _take_active(BUCKET_GOALS, sectioned_memory)
    constraints = _take_active(BUCKET_CONSTRAINTS, sectioned_memory)
    schedule_raw = _take_active(BUCKET_SCHEDULE_ANCHORS, sectioned_memory)
    pref_raw = _take_active(BUCKET_PREFERENCES, sectioned_memory)
    ctx_raw = _take_active(BUCKET_CONTEXT_NOTES, sectioned_memory)

    priority_facts = goals + constraints

    schedule_sorted = _sort_bounded_facts(schedule_raw, SECTION_SCHEDULE_ANCHOR)
    pref_sorted = _sort_bounded_facts(pref_raw, SECTION_PREFERENCE)
    ctx_sorted = _sort_bounded_facts(ctx_raw, SECTION_CONTEXT)

    # Per-section compiler caps. Goals/constraints are never trimmed here (storage caps apply).
    # Safety ordering for future global budgets: trim context → preferences → schedule.
    schedule_sel = schedule_sorted[:MAX_SCHEDULE_IN_PROMPT]
    pref_sel = pref_sorted[:MAX_PREFERENCE_IN_PROMPT]
    ctx_sel = ctx_sorted[:MAX_CONTEXT_IN_PROMPT]

    continuity_focus: Optional[str] = None
    if isinstance(continuity, dict):
        s = continuity.get("summary")
        if isinstance(s, str) and s.strip():
            continuity_focus = s.strip()

    return {
        "priority_facts": priority_facts,
        "structure_facts": schedule_sel,
        "preference_facts": pref_sel,
        "context_facts": ctx_sel,
        "continuity_focus": continuity_focus,
    }
