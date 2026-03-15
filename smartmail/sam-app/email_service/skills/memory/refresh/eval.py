"""Eval helpers for the memory refresh workflow."""

from typing import Any, Dict, List, Optional

from skills.memory.refresh.runner import run_memory_refresh


def run_refresh_eval_case(
    *,
    prior_memory_notes: List[Dict[str, Any]],
    prior_continuity_summary: Optional[Dict[str, Any]],
    latest_interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    refreshed = run_memory_refresh(
        prior_memory_notes=prior_memory_notes,
        prior_continuity_summary=prior_continuity_summary,
        latest_interaction_context=latest_interaction_context,
    )
    return {
        "memory_notes": refreshed["memory_notes"],
        "continuity_summary": refreshed["continuity_summary"],
    }
