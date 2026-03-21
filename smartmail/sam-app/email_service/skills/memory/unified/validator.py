"""Validation for the unified memory refresh LLM output (AM3)."""

from typing import Any, Dict, List

from athlete_memory_contract import (
    BACKBONE_SLOT_KEYS,
    MAX_CONTEXT_NOTES,
    MAX_OPEN_LOOPS,
    AthleteMemoryContractError,
)
from skills.memory.unified.errors import MemoryRefreshError


def validate_unified_memory_response(data: Any) -> Dict[str, Any]:
    """Validates and normalizes the raw LLM output for unified memory refresh.

    Returns a dict with keys: backbone, context_notes, continuity.
    Raises MemoryRefreshError on invalid output.
    """
    if not isinstance(data, dict):
        raise MemoryRefreshError("unified memory refresh output must be a dict")

    # --- backbone ---
    backbone_raw = data.get("backbone")
    if not isinstance(backbone_raw, dict):
        raise MemoryRefreshError("backbone must be a dict")

    backbone: Dict[str, Any] = {}
    for key in BACKBONE_SLOT_KEYS:
        value = backbone_raw.get(key)
        if value is None:
            backbone[key] = None
        elif isinstance(value, str):
            stripped = value.strip()
            backbone[key] = stripped if stripped else None
        else:
            raise MemoryRefreshError(f"backbone.{key} must be a string or null")

    # --- context_notes ---
    context_notes_raw = data.get("context_notes")
    if not isinstance(context_notes_raw, list):
        raise MemoryRefreshError("context_notes must be a list")

    context_notes: List[Dict[str, str]] = []
    for idx, item in enumerate(context_notes_raw[:MAX_CONTEXT_NOTES]):
        if not isinstance(item, dict):
            raise MemoryRefreshError(f"context_notes[{idx}] must be a dict")
        label = item.get("label")
        summary = item.get("summary")
        if not isinstance(label, str) or not label.strip():
            raise MemoryRefreshError(f"context_notes[{idx}].label must be a non-empty string")
        if not isinstance(summary, str) or not summary.strip():
            raise MemoryRefreshError(f"context_notes[{idx}].summary must be a non-empty string")
        context_notes.append({"label": label.strip(), "summary": summary.strip()})

    # --- continuity ---
    continuity_raw = data.get("continuity")
    if not isinstance(continuity_raw, dict):
        raise MemoryRefreshError("continuity must be a dict")

    summary = continuity_raw.get("summary")
    if not isinstance(summary, str) or not summary.strip():
        raise MemoryRefreshError("continuity.summary must be a non-empty string")

    last_recommendation = continuity_raw.get("last_recommendation")
    if not isinstance(last_recommendation, str) or not last_recommendation.strip():
        raise MemoryRefreshError("continuity.last_recommendation must be a non-empty string")

    open_loops_raw = continuity_raw.get("open_loops")
    if not isinstance(open_loops_raw, list):
        raise MemoryRefreshError("continuity.open_loops must be a list")

    open_loops: List[str] = []
    for idx, item in enumerate(open_loops_raw[:MAX_OPEN_LOOPS]):
        if isinstance(item, str) and item.strip():
            open_loops.append(item.strip())

    continuity = {
        "summary": summary.strip(),
        "last_recommendation": last_recommendation.strip(),
        "open_loops": open_loops,
    }

    return {
        "backbone": backbone,
        "context_notes": context_notes,
        "continuity": continuity,
    }
