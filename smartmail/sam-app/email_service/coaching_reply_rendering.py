"""Reply rendering helpers for coaching responses."""

from typing import Any, Dict, Optional

from response_generation_contract import ResponseBrief
from sectioned_memory_contract import (
    VALID_STORAGE_BUCKETS,
    format_unix_timestamp_for_prompt,
)


def render_rule_engine_payload_reply(
    next_email_payload: Dict[str, Any],
    *,
    include_plan_summary: Optional[str] = None,
) -> str:
    subject_hint = str(next_email_payload.get("subject_hint", "")).strip()
    summary = str(next_email_payload.get("summary", "")).strip()
    sessions = [
        str(item).strip()
        for item in next_email_payload.get("sessions", [])
        if str(item).strip()
    ]
    plan_focus_line = str(next_email_payload.get("plan_focus_line", "")).strip()
    technique_cue = str(next_email_payload.get("technique_cue", "")).strip()
    recovery_target = str(next_email_payload.get("recovery_target", "")).strip()
    if_then_rules = [
        str(item).strip()
        for item in next_email_payload.get("if_then_rules", [])
        if str(item).strip()
    ]
    disclaimer_short = str(next_email_payload.get("disclaimer_short", "")).strip()
    safety_note = str(next_email_payload.get("safety_note", "")).strip()

    lines = []
    if subject_hint:
        lines.append(subject_hint)
    if summary:
        lines.append(summary)
    if include_plan_summary:
        lines.append(include_plan_summary)
    if sessions:
        lines.append("Sessions:")
        lines.extend(f"- {session}" for session in sessions)
    if plan_focus_line:
        lines.append(f"Plan focus: {plan_focus_line}")
    if technique_cue:
        lines.append(f"Technique cue: {technique_cue}")
    if recovery_target:
        lines.append(f"Recovery target: {recovery_target}")
    if if_then_rules:
        lines.append("If-then rules:")
        lines.extend(f"- {rule}" for rule in if_then_rules)
    if safety_note:
        lines.append(f"Safety note: {safety_note}")
    if disclaimer_short:
        lines.append(disclaimer_short)
    return "\n\n".join(lines)


def build_memory_context_block(memory_context: Dict[str, Any]) -> str:
    if not isinstance(memory_context, dict):
        return ""

    lines = []
    continuity_summary = memory_context.get("continuity_summary")
    if isinstance(continuity_summary, dict):
        summary_text = str(continuity_summary.get("summary", "")).strip()
        last_recommendation = str(continuity_summary.get("last_recommendation", "")).strip()
        updated_at = continuity_summary.get("updated_at")
        open_loops = [
            str(item).strip()
            for item in continuity_summary.get("open_loops", [])
            if str(item).strip()
        ]
        if summary_text:
            lines.append(f"Continuity summary: {summary_text}")
        if last_recommendation:
            lines.append(f"Last recommendation: {last_recommendation}")
        if isinstance(updated_at, int):
            lines.append(
                f"Continuity updated: {format_unix_timestamp_for_prompt(updated_at)}"
            )
        if open_loops:
            lines.append("Open loops:")
            lines.extend(f"- {item}" for item in open_loops)

    sectioned = memory_context.get("sectioned_memory")
    if isinstance(sectioned, dict) and sectioned:
        lines.append("Athlete memory (sectioned):")
        for bucket in VALID_STORAGE_BUCKETS:
            active = (sectioned.get(bucket) or {}).get("active") or []
            if not active:
                continue
            label = str(bucket).replace("_", " ")
            lines.append(f"{label}:")
            for fact in active:
                if not isinstance(fact, dict):
                    continue
                mid = fact.get("memory_id")
                section = str(fact.get("section", "")).strip()
                summary = str(fact.get("summary", "")).strip()
                last_confirmed_at = fact.get("last_confirmed_at")
                if not summary:
                    continue
                recency_suffix = ""
                if isinstance(last_confirmed_at, int):
                    recency_suffix = (
                        f" [last confirmed {format_unix_timestamp_for_prompt(last_confirmed_at)}]"
                    )
                lines.append(
                    f"- [{mid}] {section}: {summary}{recency_suffix}"
                )
    return "\n".join(lines)


def build_llm_reply_body(
    *,
    inbound_body: str,
    response_brief: ResponseBrief,
) -> str:
    llm_body = inbound_body
    plan_summary = str(response_brief.validated_plan.get("plan_summary", "")).strip()
    if plan_summary:
        llm_body = f"{llm_body}\n\nCurrent plan context:\n{plan_summary}"

    memory_context_block = build_memory_context_block(response_brief.memory_context)
    if memory_context_block:
        llm_body = f"{llm_body}\n\nAthlete memory context:\n{memory_context_block}"

    decision_lines = []
    decision_context = response_brief.decision_context
    for label, field_name in (
        ("Track", "track"),
        ("Phase", "phase"),
        ("Risk flag", "risk_flag"),
        ("Today action", "today_action"),
    ):
        value = str(decision_context.get(field_name, "")).strip()
        if value:
            decision_lines.append(f"{label}: {value}")
    if "clarification_needed" in decision_context:
        decision_lines.append(
            f"Clarification needed: {bool(decision_context.get('clarification_needed'))}"
        )
    if decision_lines:
        llm_body = (
            f"{llm_body}\n\nDecision context:\n" + "\n".join(decision_lines)
        )

    return llm_body
