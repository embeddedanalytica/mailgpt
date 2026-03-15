"""Validation for short-term memory refresh outputs."""

import logging
from typing import Any, Dict

from athlete_memory_contract import MAX_OPEN_LOOPS, ContinuitySummary
from skills.memory.refresh.errors import MemoryRefreshError

logger = logging.getLogger(__name__)


def validate_short_term_memory_response(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise MemoryRefreshError("short-term memory response must be a JSON object")

    allowed_keys = {"continuity_summary"}
    unknown_keys = sorted(set(data.keys()) - allowed_keys)
    if unknown_keys:
        raise MemoryRefreshError(
            "short-term memory response contains unknown keys: " + ", ".join(unknown_keys)
        )

    if "continuity_summary" not in data:
        raise MemoryRefreshError("short-term memory response is missing keys: continuity_summary")

    continuity_summary_raw = data.get("continuity_summary")
    if not isinstance(continuity_summary_raw, dict):
        raise MemoryRefreshError("continuity_summary must be a dict")

    open_loops_raw = continuity_summary_raw.get("open_loops")
    if isinstance(open_loops_raw, list) and len(open_loops_raw) > MAX_OPEN_LOOPS:
        logger.info(
            "Short-term memory refresh returned %s open_loops items; trimming to %s most relevant items",
            len(open_loops_raw),
            MAX_OPEN_LOOPS,
        )
        continuity_summary_raw = dict(continuity_summary_raw)
        continuity_summary_raw["open_loops"] = open_loops_raw[:MAX_OPEN_LOOPS]

    return {
        "continuity_summary": ContinuitySummary.from_dict(continuity_summary_raw).to_dict()
    }
