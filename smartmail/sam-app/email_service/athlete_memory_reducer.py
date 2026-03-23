"""AM2 candidate-operation memory reducer.

Applies validated LLM candidate operations to the current durable fact state.
All persistence decisions are deterministic — the LLM interprets, code persists.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, List

from athlete_memory_contract import (
    ADMISSION_THRESHOLD,
    ContinuitySummary,
    DurableFact,
    HIGH_IMPORTANCE_TYPES,
    LOW_VALUE_FACT_TYPES,
    MAX_ACTIVE_FACTS,
    normalize_fact_key,
)

logger = logging.getLogger(__name__)


class CandidateReducerError(ValueError):
    """Raised when candidate application fails validation."""


def apply_candidate_refresh(
    validated_llm_output: Dict[str, Any],
    current_facts: List[Dict[str, Any]],
    now_epoch: int,
) -> Dict[str, Any]:
    """Applies validated candidate operations to current durable facts.

    Returns a dict with keys ``memory_notes`` and ``continuity_summary``
    ready for DynamoDB persistence.

    Raises CandidateReducerError if any candidate references a non-existent
    target_id (entire batch is rejected).
    """
    # Build lookup from current active facts
    facts_by_id: Dict[str, Dict[str, Any]] = {}
    for fact_dict in current_facts:
        mid = fact_dict.get("memory_note_id")
        if mid:
            facts_by_id[mid] = dict(fact_dict)  # shallow copy

    candidates = validated_llm_output["candidates"]

    for candidate in candidates:
        action = candidate["action"]
        target_id = candidate.get("target_id")

        if action == "upsert" and not target_id:
            # --- New fact creation ---
            fact_type = candidate["fact_type"]
            fact_key = normalize_fact_key(fact_type, candidate["fact_key"])
            importance = candidate["importance"]
            # Enforce importance floor for high-importance types
            if fact_type in HIGH_IMPORTANCE_TYPES:
                importance = "high"

            # Admission gate: reject low-value new facts when budget is tight
            if (
                fact_type in LOW_VALUE_FACT_TYPES
                and importance != "high"
                and len(facts_by_id) >= ADMISSION_THRESHOLD
            ):
                logger.info(
                    "admission_gate: rejected new %s/%s fact %r (active=%d, threshold=%d)",
                    fact_type, importance, fact_key, len(facts_by_id), ADMISSION_THRESHOLD,
                )
                continue

            new_id = str(uuid.uuid4())
            facts_by_id[new_id] = {
                "memory_note_id": new_id,
                "fact_type": fact_type,
                "fact_key": fact_key,
                "summary": candidate["summary"],
                "importance": importance,
                "created_at": now_epoch,
                "updated_at": now_epoch,
                "last_confirmed_at": now_epoch,
            }

        elif action == "upsert" and target_id:
            # --- Update existing fact ---
            if target_id not in facts_by_id:
                raise CandidateReducerError(
                    f"upsert target_id {target_id!r} not found in current active facts"
                )
            existing = facts_by_id[target_id]
            existing["summary"] = candidate["summary"]
            existing["updated_at"] = now_epoch
            existing["last_confirmed_at"] = now_epoch
            if "importance" in candidate:
                new_importance = candidate["importance"]
                # Enforce importance floor
                if existing["fact_type"] in HIGH_IMPORTANCE_TYPES:
                    new_importance = "high"
                existing["importance"] = new_importance

        elif action == "confirm":
            # --- Confirm existing fact ---
            if target_id not in facts_by_id:
                raise CandidateReducerError(
                    f"confirm target_id {target_id!r} not found in current active facts"
                )
            facts_by_id[target_id]["last_confirmed_at"] = now_epoch

        elif action == "retire":
            # --- Delete from active list ---
            if target_id not in facts_by_id:
                raise CandidateReducerError(
                    f"retire target_id {target_id!r} not found in current active facts"
                )
            del facts_by_id[target_id]

    # Collect active facts
    active_facts = list(facts_by_id.values())

    # --- Canonical key uniqueness backstop ---
    seen_keys: Dict[str, int] = {}  # canonical_key -> index of best (most recent updated_at)
    for i, fact in enumerate(active_facts):
        key = fact["fact_key"]
        if key in seen_keys:
            prev_idx = seen_keys[key]
            prev_fact = active_facts[prev_idx]
            # Keep the one with the most recent updated_at
            if fact["updated_at"] >= prev_fact["updated_at"]:
                seen_keys[key] = i
        else:
            seen_keys[key] = i
    if len(seen_keys) < len(active_facts):
        keep_indices = set(seen_keys.values())
        active_facts = [f for i, f in enumerate(active_facts) if i in keep_indices]
        logger.warning(
            "canonical_key_uniqueness_backstop: removed duplicate active facts, "
            "active_count=%d", len(active_facts)
        )

    # --- Budget enforcement ---
    # Fact-type eviction tiers: other/preference evicted before schedule
    _FACT_TYPE_EVICTION_ORDER = {"other": 0, "preference": 1, "schedule": 2, "constraint": 3, "goal": 3}

    if len(active_facts) > MAX_ACTIVE_FACTS:
        # Sort: medium importance first, then least-valuable fact_type first, then oldest confirmed first
        def _eviction_sort_key(f: Dict[str, Any]) -> tuple:
            importance_order = 0 if f["importance"] == "medium" else 1
            type_order = _FACT_TYPE_EVICTION_ORDER.get(f.get("fact_type", "other"), 0)
            return (importance_order, type_order, f["last_confirmed_at"])

        active_facts.sort(key=_eviction_sort_key)

        # Evict from the front (least valuable first), but never evict high-importance
        evicted: List[Dict[str, Any]] = []
        kept: List[Dict[str, Any]] = []
        for fact in active_facts:
            if fact["importance"] != "high" and len(active_facts) - len(evicted) > MAX_ACTIVE_FACTS:
                evicted.append(fact)
            else:
                kept.append(fact)

        if evicted:
            logger.info(
                "budget_enforcement: evicted %d medium-importance facts, active_count=%d",
                len(evicted), len(kept),
            )

        if len(kept) > MAX_ACTIVE_FACTS:
            logger.warning(
                "budget_overflow: %d active facts (all high-importance), budget=%d",
                len(kept), MAX_ACTIVE_FACTS,
            )

        active_facts = kept

    # --- Continuity (unchanged from AM3) ---
    continuity_raw = validated_llm_output["continuity"]
    continuity = ContinuitySummary(
        summary=continuity_raw["summary"],
        last_recommendation=continuity_raw["last_recommendation"],
        open_loops=list(continuity_raw["open_loops"]),
        updated_at=now_epoch,
    )

    return {
        "memory_notes": [DurableFact.from_dict(f, index=i).to_dict() for i, f in enumerate(active_facts)],
        "continuity_summary": continuity.to_dict(),
    }
