"""Validation for long-term memory refresh outputs."""

from typing import Any, Dict

from athlete_memory_reducer import (
    AthleteMemoryReducerError,
    validate_long_term_candidate_payload,
)
from skills.memory.refresh.errors import MemoryRefreshError


def validate_long_term_memory_response(data: Any) -> Dict[str, Any]:
    try:
        return validate_long_term_candidate_payload(data)
    except AthleteMemoryReducerError as exc:
        raise MemoryRefreshError(str(exc)) from exc
