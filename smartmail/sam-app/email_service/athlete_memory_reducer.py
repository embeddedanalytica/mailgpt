"""AM3 unified memory refresh reducer."""

from __future__ import annotations

from typing import Any, Dict

from athlete_memory_contract import (
    BACKBONE_SLOT_KEYS,
    MAX_CONTEXT_NOTES,
    ContinuitySummary,
    validate_backbone_slots,
    validate_context_note_list,
)


class AthleteMemoryReducerError(ValueError):
    """Raised when a memory-reduction operation fails validation."""


def apply_unified_refresh(
    validated_llm_output: Dict[str, Any],
    now_epoch: int,
) -> Dict[str, Any]:
    """Converts validated unified memory LLM output into persistence-ready data.

    Takes the output of ``validate_unified_memory_response()`` and adds
    timestamps, returning a dict with keys ``backbone``, ``context_notes``,
    and ``continuity_summary`` ready for DynamoDB persistence.
    """
    # --- backbone ---
    backbone_raw = validated_llm_output["backbone"]
    backbone_dict: Dict[str, Any] = {}
    for key in BACKBONE_SLOT_KEYS:
        summary = backbone_raw.get(key)
        if summary is None:
            backbone_dict[key] = {"summary": None, "updated_at": None}
        else:
            backbone_dict[key] = {"summary": summary, "updated_at": now_epoch}

    # Validate through the contract to ensure consistency.
    backbone = validate_backbone_slots(backbone_dict)

    # --- context notes ---
    context_notes_raw = validated_llm_output["context_notes"]
    context_notes_dicts = [
        {"label": note["label"], "summary": note["summary"], "updated_at": now_epoch}
        for note in context_notes_raw[:MAX_CONTEXT_NOTES]
    ]
    context_notes = validate_context_note_list(context_notes_dicts)

    # --- continuity ---
    continuity_raw = validated_llm_output["continuity"]
    continuity = ContinuitySummary(
        summary=continuity_raw["summary"],
        last_recommendation=continuity_raw["last_recommendation"],
        open_loops=list(continuity_raw["open_loops"]),
        updated_at=now_epoch,
    )

    return {
        "backbone": backbone.to_dict(),
        "context_notes": context_notes,
        "continuity_summary": continuity.to_dict(),
    }
