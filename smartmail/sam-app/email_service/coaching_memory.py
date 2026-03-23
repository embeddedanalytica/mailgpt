"""Memory-refresh orchestration helpers for coaching.

AM2: single post-reply candidate-operation refresh replaces the old full-state
replacement pipeline. The deterministic gate (should_attempt_memory_refresh) is
unchanged.
"""

import logging
import time
from typing import Any, Callable, Dict, List, Optional

from athlete_memory_reducer import apply_candidate_refresh, CandidateReducerError
from skills.memory.unified import run_candidate_memory_refresh
from skills.memory.unified.errors import MemoryRefreshError

logger = logging.getLogger(__name__)


def should_attempt_memory_refresh(
    *,
    reply_kind: str,
    parsed_updates: Dict[str, Any],
) -> bool:
    if reply_kind in {
        "safety_concern",
        "safety_risk_managed",
        "off_topic",
        "off_topic_redirect",
        "clarification_needed",
        "clarification",
    }:
        return False
    if reply_kind == "profile_incomplete":
        return bool(parsed_updates)
    return True


def build_memory_refresh_context(
    *,
    inbound_body: str,
    inbound_subject: Optional[str],
    parsed_updates: Dict[str, Any],
    manual_snapshot: Optional[Dict[str, Any]],
    selected_model_name: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    reply_text: Optional[str] = None,
) -> Dict[str, Any]:
    context: Dict[str, Any] = {
        "inbound_email": inbound_body,
        "inbound_subject": str(inbound_subject or "").strip(),
        "profile_updates_applied": sorted(parsed_updates.keys()),
        "manual_activity_detected": bool(manual_snapshot),
        "selected_model_name": str(selected_model_name or "").strip(),
        "rule_engine_decision": rule_engine_decision if isinstance(rule_engine_decision, dict) else None,
    }
    if reply_text is not None:
        context["coach_reply"] = reply_text
    return context


def maybe_post_reply_memory_refresh(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_subject: Optional[str],
    reply_text: str,
    reply_kind: str,
    parsed_updates: Dict[str, Any],
    manual_snapshot: Optional[Dict[str, Any]],
    selected_model_name: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    log: Callable[..., None],
    get_memory_notes_fn: Callable[[str], List[Dict[str, Any]]],
    get_continuity_summary_fn: Callable[[str], Optional[Dict[str, Any]]],
    replace_memory_fn: Callable[[str, List[Dict[str, Any]], Dict[str, Any]], bool],
) -> None:
    """Runs candidate-operation memory refresh after response generation.

    Fail-closed: on any error, logs and returns without propagating.
    """
    if not should_attempt_memory_refresh(reply_kind=reply_kind, parsed_updates=parsed_updates):
        log(result="memory_refresh_skipped_by_gate", reply_kind=reply_kind)
        return

    interaction_context = build_memory_refresh_context(
        inbound_body=inbound_body,
        inbound_subject=inbound_subject,
        parsed_updates=parsed_updates,
        manual_snapshot=manual_snapshot,
        selected_model_name=selected_model_name,
        rule_engine_decision=rule_engine_decision,
        reply_text=reply_text,
    )

    current_memory_notes = get_memory_notes_fn(athlete_id)
    current_continuity = get_continuity_summary_fn(athlete_id)

    try:
        validated = run_candidate_memory_refresh(
            current_memory_notes=current_memory_notes,
            current_continuity=current_continuity,
            interaction_context=interaction_context,
        )

        now_epoch = int(time.time())
        persisted = apply_candidate_refresh(validated, current_memory_notes, now_epoch)

        write_ok = replace_memory_fn(
            athlete_id,
            persisted["memory_notes"],
            persisted["continuity_summary"],
        )
        if not write_ok:
            raise MemoryRefreshError("memory persistence failed")

    except (MemoryRefreshError, CandidateReducerError):
        log(result="memory_refresh_failed")
        return
    except Exception:
        logger.exception("Unexpected error during candidate memory refresh")
        log(result="memory_refresh_failed")
        return

    log(
        result="memory_refresh_persisted",
        active_fact_count=len(persisted["memory_notes"]),
    )
