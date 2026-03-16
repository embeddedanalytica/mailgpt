"""Memory-refresh orchestration helpers for coaching."""

from typing import Any, Callable, Dict, Optional

from athlete_memory_contract import filter_active_memory_notes
from skills.memory import MemoryRefreshError


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
    context = {
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


def maybe_pre_reply_memory_refresh(
    *,
    athlete_id: str,
    inbound_body: str,
    inbound_subject: Optional[str],
    reply_kind: str,
    parsed_updates: Dict[str, Any],
    manual_snapshot: Optional[Dict[str, Any]],
    selected_model_name: Optional[str],
    rule_engine_decision: Optional[Dict[str, Any]],
    log: Callable[..., None],
    run_memory_router_fn: Callable[..., Dict[str, Any]],
    get_memory_notes_fn: Callable[[str], list[Dict[str, Any]]],
    get_continuity_summary_fn: Callable[[str], Optional[Dict[str, Any]]],
    run_memory_refresh_fn: Callable[..., Dict[str, Any]],
    replace_memory_notes_fn: Callable[[str, list[Dict[str, Any]]], bool],
) -> None:
    if not should_attempt_memory_refresh(reply_kind=reply_kind, parsed_updates=parsed_updates):
        return

    interaction_context = build_memory_refresh_context(
        inbound_body=inbound_body,
        inbound_subject=inbound_subject,
        parsed_updates=parsed_updates,
        manual_snapshot=manual_snapshot,
        selected_model_name=selected_model_name,
        rule_engine_decision=rule_engine_decision,
    )

    prior_memory_notes = get_memory_notes_fn(athlete_id)
    prior_continuity_summary = get_continuity_summary_fn(athlete_id)
    routing = run_memory_router_fn(
        prior_memory_notes=filter_active_memory_notes(prior_memory_notes),
        prior_continuity_summary=prior_continuity_summary,
        latest_interaction_context=interaction_context,
    )
    route = routing.get("route")
    if route not in {"long_term", "both"}:
        log(
            result="memory_pre_refresh_skipped",
            memory_refresh_route=route,
            memory_refresh_resolution=routing.get("reason_resolution"),
        )
        return

    try:
        refreshed = run_memory_refresh_fn(
            prior_memory_notes=prior_memory_notes,
            prior_continuity_summary=prior_continuity_summary,
            latest_interaction_context=interaction_context,
            routing_decision={"route": "long_term"},
        )
        write_ok = replace_memory_notes_fn(
            athlete_id,
            refreshed["memory_notes"],
        )
        if not write_ok:
            raise MemoryRefreshError("memory note persistence failed")
    except MemoryRefreshError:
        log(
            result="memory_pre_refresh_failed",
            memory_refresh_route=route,
        )
        return

    log(
        result="memory_pre_refresh_persisted",
        memory_refresh_route=route,
        memory_note_count=len(filter_active_memory_notes(refreshed["memory_notes"])),
    )


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
    run_memory_router_fn: Callable[..., Dict[str, Any]],
    get_memory_notes_fn: Callable[[str], list[Dict[str, Any]]],
    get_continuity_summary_fn: Callable[[str], Optional[Dict[str, Any]]],
    run_memory_refresh_fn: Callable[..., Dict[str, Any]],
    replace_continuity_summary_fn: Callable[[str, Dict[str, Any]], bool],
) -> None:
    if not should_attempt_memory_refresh(reply_kind=reply_kind, parsed_updates=parsed_updates):
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

    prior_memory_notes = get_memory_notes_fn(athlete_id)
    prior_continuity_summary = get_continuity_summary_fn(athlete_id)
    routing = run_memory_router_fn(
        prior_memory_notes=filter_active_memory_notes(prior_memory_notes),
        prior_continuity_summary=prior_continuity_summary,
        latest_interaction_context=interaction_context,
    )
    route = routing.get("route")
    if route not in {"short_term", "both"}:
        log(
            result="memory_post_refresh_skipped",
            memory_refresh_route=route,
            memory_refresh_resolution=routing.get("reason_resolution"),
        )
        return

    try:
        refreshed = run_memory_refresh_fn(
            prior_memory_notes=prior_memory_notes,
            prior_continuity_summary=prior_continuity_summary,
            latest_interaction_context=interaction_context,
            routing_decision={"route": "short_term"},
        )
        write_ok = replace_continuity_summary_fn(
            athlete_id,
            refreshed["continuity_summary"],
        )
        if not write_ok:
            raise MemoryRefreshError("continuity_summary persistence failed")
    except MemoryRefreshError:
        log(
            result="memory_post_refresh_failed",
            memory_refresh_route=route,
        )
        return

    log(
        result="memory_post_refresh_persisted",
        memory_refresh_route=route,
        memory_note_count=len(filter_active_memory_notes(prior_memory_notes)),
    )
