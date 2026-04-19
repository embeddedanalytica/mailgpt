"""Shared sectioned-memory dicts for unit tests."""

from __future__ import annotations

import uuid
from typing import Any, Dict, List

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
    validate_sectioned_memory,
)


def active_fact(
    *,
    memory_id: str,
    section: str,
    subtype: str,
    fact_key: str,
    summary: str,
    created_at: int = 1773273600,
    updated_at: int = 1773273600,
    last_confirmed_at: int = 1773273600,
) -> Dict[str, Any]:
    return {
        "memory_id": memory_id,
        "section": section,
        "subtype": subtype,
        "fact_key": fact_key,
        "summary": summary,
        "status": STATUS_ACTIVE,
        "supersedes": [],
        "created_at": created_at,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


def sectioned_from_flat_memory_notes(notes: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Build validated sectioned memory from legacy flat memory_note-shaped dicts."""
    m = empty_sectioned_memory()
    for i, note in enumerate(notes):
        ft = str(note.get("fact_type", "")).strip().lower()
        summary = str(note.get("summary", "")).strip()
        fk = str(note.get("fact_key", f"k{i}")).strip()
        raw_mid = note.get("memory_note_id")
        if isinstance(raw_mid, str) and raw_mid.strip():
            try:
                uuid.UUID(raw_mid)
                mid = raw_mid.strip()
            except ValueError:
                mid = str(uuid.uuid4())
        else:
            mid = str(uuid.uuid4())
        if ft == "goal":
            m[BUCKET_GOALS]["active"].append(
                active_fact(
                    memory_id=mid,
                    section=SECTION_GOAL,
                    subtype="primary",
                    fact_key=fk,
                    summary=summary,
                )
            )
        elif ft == "constraint":
            m[BUCKET_CONSTRAINTS]["active"].append(
                active_fact(
                    memory_id=mid,
                    section=SECTION_CONSTRAINT,
                    subtype="logistics",
                    fact_key=fk,
                    summary=summary,
                )
            )
        elif ft == "schedule":
            m[BUCKET_SCHEDULE_ANCHORS]["active"].append(
                active_fact(
                    memory_id=mid,
                    section=SECTION_SCHEDULE_ANCHOR,
                    subtype="recurring_anchor",
                    fact_key=fk,
                    summary=summary,
                )
            )
        elif ft == "preference":
            m[BUCKET_PREFERENCES]["active"].append(
                active_fact(
                    memory_id=mid,
                    section=SECTION_PREFERENCE,
                    subtype="other",
                    fact_key=fk,
                    summary=summary,
                )
            )
        else:
            m[BUCKET_CONTEXT_NOTES]["active"].append(
                active_fact(
                    memory_id=mid,
                    section=SECTION_CONTEXT,
                    subtype="other",
                    fact_key=fk,
                    summary=summary,
                )
            )
    return validate_sectioned_memory(m)
