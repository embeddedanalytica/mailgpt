"""Runner for the memory refresh orchestration workflow."""

from typing import Any, Dict, List, Optional

from athlete_memory_contract import ContinuitySummary, MemoryNote, filter_active_memory_notes
from skills.memory.long_term.runner import run_long_term_memory_refresh
from skills.memory.refresh.errors import MemoryRefreshError
from skills.memory.router.runner import run_memory_router
from skills.memory.short_term.runner import run_short_term_memory_refresh


def run_memory_refresh(
    *,
    prior_memory_notes: List[Dict[str, Any]],
    prior_continuity_summary: Optional[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
    routing_decision: Optional[Dict[str, Any]] = None,
    stored_memory_notes: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    normalized_memory_notes = [MemoryNote.from_dict(note).to_dict() for note in prior_memory_notes]
    active_memory_notes = filter_active_memory_notes(normalized_memory_notes)
    normalized_continuity_summary = None
    if prior_continuity_summary is not None:
        normalized_continuity_summary = ContinuitySummary.from_dict(
            prior_continuity_summary
        ).to_dict()

    routing = routing_decision or run_memory_router(
        prior_memory_notes=active_memory_notes,
        prior_continuity_summary=normalized_continuity_summary,
        latest_interaction_context=latest_interaction_context,
    )
    route = routing.get("route")

    memory_notes = normalized_memory_notes
    continuity_summary = normalized_continuity_summary

    if route in {"long_term", "both"}:
        long_term_result = run_long_term_memory_refresh(
            prior_memory_notes=active_memory_notes,
            latest_interaction_context=latest_interaction_context,
            stored_memory_notes=stored_memory_notes or normalized_memory_notes,
        )
        memory_notes = long_term_result["memory_notes"]

    if route in {"short_term", "both"}:
        continuity_summary = run_short_term_memory_refresh(
            prior_continuity_summary=normalized_continuity_summary,
            latest_interaction_context=latest_interaction_context,
        )["continuity_summary"]

    if continuity_summary is None and route in {"short_term", "both"}:
        raise MemoryRefreshError("memory refresh requires continuity_summary after routing")

    result = {
        "memory_notes": memory_notes,
        "continuity_summary": continuity_summary,
    }
    if route in {"long_term", "both"}:
        result["long_term_debug"] = {
            "raw_response_text": long_term_result.get("raw_response_text", ""),
            "raw_llm_data": long_term_result.get("raw_llm_data"),
            "validated_candidate_payload": long_term_result.get("validated_candidate_payload"),
        }
    return result
