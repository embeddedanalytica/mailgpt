"""Typed contracts for the memory refresh orchestration workflow."""

from typing import Any, Dict, List, Optional, TypedDict


class MemoryRefreshInput(TypedDict):
    prior_memory_notes: List[Dict[str, Any]]
    prior_continuity_summary: Optional[Dict[str, Any]]
    latest_interaction_context: Dict[str, Any]


class MemoryRefreshOutput(TypedDict):
    memory_notes: List[Dict[str, Any]]
    continuity_summary: Dict[str, Any]
