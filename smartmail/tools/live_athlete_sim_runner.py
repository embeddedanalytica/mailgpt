#!/usr/bin/env python3
"""Run a live athlete simulator bench against the local coaching workflow."""

from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from datetime import datetime, timedelta, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List, Optional


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
E2E_PATH = REPO_ROOT / "sam-app" / "e2e"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))
if str(E2E_PATH) not in sys.path:
    sys.path.insert(0, str(E2E_PATH))

from athlete_agent_bench_fixture import (  # noqa: E402
    DEFAULT_BENCH_PATH,
    load_athlete_agent_bench_scenarios,
)
from athlete_simulation import (  # noqa: E402
    AthleteSimulationError,
    AthleteSimulator,
    CoachReplyJudge,
    CoachReplyJudgeError,
)
from config import OPENAI_GENERIC_MODEL, OPENAI_REASONING_MODEL  # noqa: E402
import coaching as _coaching_module  # noqa: E402
from live_coaching_harness import LiveCoachingHarness  # noqa: E402


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "live-athlete-sim"
OK = "ok"
ERROR = "error"
DEFAULT_SYNTHETIC_DAYS_PER_TURN = 7
REPETITION_SIMILARITY_THRESHOLD = 0.6
ANTI_REPETITION_OVERRIDE = (
    "ANTI-REPETITION OVERRIDE:\n"
    "Your recent messages are too similar. Change direction now.\n"
    "- If you promised data, send it now\n"
    "- If you already confirmed something, stop reconfirming it\n"
    "- If the exchange has stalled, introduce a concrete update, complication, or next-step question"
)
_COMMITMENT_PATTERNS = [
    re.compile(r"\bi(?:\s+will|'ll)\s+(send|share|upload|confirm)\s+([^.!?\n]+)", flags=re.IGNORECASE),
]
_COMMITMENT_FULFILLMENT_CUES = (
    "here is",
    "here's",
    "here are",
    "attaching",
    "attached",
    "my week looked like",
    "my check in",
    "my check-in",
    "the check in",
    "the check-in",
    "the splits",
    "the data",
    "the file",
    "the log",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a live athlete simulator bench against the local coaching workflow."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Path to athlete simulator benchmark markdown fixture.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario id filter; may be repeated.",
    )
    parser.add_argument(
        "--runs-per-scenario",
        type=int,
        default=1,
        help="Number of independent runs per scenario.",
    )
    parser.add_argument(
        "--min-turns",
        type=int,
        default=100,
        help="Default minimum turns when not provided by a scenario.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Default maximum turns when not provided by a scenario.",
    )
    parser.add_argument(
        "--athlete-model",
        help="Optional model override for the athlete simulator.",
    )
    parser.add_argument(
        "--judge-model",
        help="Optional model override for the reply judge.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for artifacts.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent scenarios to run.",
    )
    parser.add_argument(
        "--synthetic-start-date",
        help=(
            "Synthetic UTC start datetime for inbound athlete messages. "
            "Accepts ISO-8601 like 2026-03-25T15:00:00+00:00. "
            "Defaults to current UTC time."
        ),
    )
    parser.add_argument(
        "--synthetic-days-per-turn",
        type=int,
        default=7,
        help="How many synthetic calendar days to advance between athlete turns.",
    )
    return parser


def require_prerequisites(
    bench_path: Path,
    *,
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    max_parallel: int,
    synthetic_days_per_turn: int,
) -> None:
    missing: list[str] = []
    if not bench_path.exists():
        missing.append(f"athlete simulator benchmark fixture not found: {bench_path}")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        missing.append("OPENAI_API_KEY is required for live athlete simulator runs.")
    if missing:
        raise RuntimeError("\n".join(missing))
    if runs_per_scenario < 1:
        raise RuntimeError("--runs-per-scenario must be at least 1.")
    if min_turns < 1:
        raise RuntimeError("--min-turns must be at least 1.")
    if max_turns < 1:
        raise RuntimeError("--max-turns must be at least 1.")
    if min_turns > max_turns:
        raise RuntimeError("--min-turns cannot be greater than --max-turns.")
    if max_parallel < 1:
        raise RuntimeError("--max-parallel must be at least 1.")
    if synthetic_days_per_turn < 0:
        raise RuntimeError("--synthetic-days-per-turn cannot be negative.")
    os.environ["ENABLE_LIVE_LLM_CALLS"] = "true"
    os.environ["ENABLE_SESSION_CHECKIN_EXTRACTION"] = "true"


def make_output_dir(output_dir: str | None) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser().resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = DEFAULT_OUTPUT_ROOT / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def select_scenarios(
    scenarios: List[Dict[str, Any]],
    selected_tokens: List[str],
) -> List[Dict[str, Any]]:
    if not selected_tokens:
        return list(scenarios)
    wanted = {token.strip().lower() for token in selected_tokens if token.strip()}
    return [
        scenario
        for scenario in scenarios
        if scenario["id"].strip().lower() in wanted or scenario["name"].strip().lower() in wanted
    ]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _resolve_synthetic_start_datetime(raw_value: Optional[str]) -> datetime:
    if not raw_value:
        return datetime.now(timezone.utc)
    try:
        parsed = datetime.fromisoformat(str(raw_value).strip())
    except ValueError as exc:
        raise RuntimeError(
            "--synthetic-start-date must be a valid ISO-8601 datetime"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _format_rfc2822_utc(value: datetime) -> str:
    return value.astimezone(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")


def _append_jsonl(path: Path, payload: Dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(_json_safe(payload), ensure_ascii=False) + "\n")


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        if value == value.to_integral_value():
            return int(value)
        return float(value)
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_json_safe(item) for item in value]
    if isinstance(value, tuple):
        return [_json_safe(item) for item in value]
    return value


def _subject_from_body(body: str) -> str:
    collapsed = " ".join(str(body or "").split())
    if not collapsed:
        return "Coaching question"
    first_sentence = collapsed.split(".")[0].strip()
    if len(first_sentence) <= 72:
        return first_sentence
    return first_sentence[:69].rstrip() + "..."


def _average(values: Iterable[float]) -> float:
    sequence = list(values)
    if not sequence:
        return 0.0
    return round(sum(sequence) / len(sequence), 3)


def _sorted_counter(counter: Counter[str]) -> Dict[str, int]:
    return {key: counter[key] for key in sorted(counter)}


def _top_counter_entries(counter: Counter[str], *, limit: int = 3) -> List[str]:
    return [f"{key}:{value}" for key, value in counter.most_common(limit)]


def _normalize_similarity_text(text: str) -> str:
    lowered = str(text or "").lower()
    lowered = re.sub(r"[^a-z0-9\s]", " ", lowered)
    return " ".join(lowered.split())


def _word_overlap_similarity(left: str, right: str) -> float:
    left_tokens = set(_normalize_similarity_text(left).split())
    right_tokens = set(_normalize_similarity_text(right).split())
    if not left_tokens or not right_tokens:
        return 0.0
    baseline = min(len(left_tokens), len(right_tokens))
    if baseline == 0:
        return 0.0
    return len(left_tokens & right_tokens) / baseline


def _athlete_message_bodies(transcript: List[Dict[str, Any]]) -> List[str]:
    return [
        str(item.get("body", "")).strip()
        for item in transcript
        if item.get("role") == "athlete" and str(item.get("body", "")).strip()
    ]


def _max_consecutive_similar_athlete_messages(transcript: List[Dict[str, Any]]) -> int:
    athlete_bodies = _athlete_message_bodies(transcript)
    if not athlete_bodies:
        return 0
    max_run = 1
    current_run = 1
    for previous, current in zip(athlete_bodies, athlete_bodies[1:]):
        if _word_overlap_similarity(previous, current) >= REPETITION_SIMILARITY_THRESHOLD:
            current_run += 1
            max_run = max(max_run, current_run)
        else:
            current_run = 1
    return max_run


def _detect_repetition(transcript: List[Dict[str, Any]]) -> Optional[str]:
    athlete_bodies = _athlete_message_bodies(transcript)
    if len(athlete_bodies) < 3:
        return None
    last_three = athlete_bodies[-3:]
    similarities = [
        _word_overlap_similarity(last_three[0], last_three[1]),
        _word_overlap_similarity(last_three[1], last_three[2]),
        _word_overlap_similarity(last_three[0], last_three[2]),
    ]
    if min(similarities) >= REPETITION_SIMILARITY_THRESHOLD:
        return ANTI_REPETITION_OVERRIDE
    return None


def _resolve_current_phase(scenario: Dict[str, Any], turn_number: int) -> Optional[Dict[str, Any]]:
    for phase in scenario.get("conversation_phases", []) or []:
        if phase["start_turn"] <= turn_number <= phase["end_turn"]:
            return {
                "label": phase["label"],
                "objective": phase["objective"],
                "suggested_reveals": list(phase.get("suggested_reveals", [])),
                "suggested_actions": list(phase.get("suggested_actions", [])),
                "start_turn": phase["start_turn"],
                "end_turn": phase["end_turn"],
            }
    return None


def _phase_coverage(transcript: List[Dict[str, Any]]) -> List[str]:
    labels: List[str] = []
    seen: set[str] = set()
    for item in transcript:
        phase = item.get("current_phase")
        if not isinstance(phase, dict):
            continue
        label = str(phase.get("label", "")).strip()
        if not label:
            continue
        normalized = label.lower()
        if normalized in seen:
            continue
        seen.add(normalized)
        labels.append(label)
    return labels


def _normalize_commitment_text(text: str) -> str:
    return _normalize_similarity_text(text)


def _extract_commitments_from_message(body: str, *, turn_number: int) -> List[Dict[str, Any]]:
    message = str(body or "").strip()
    if not message:
        return []
    commitments: List[Dict[str, Any]] = []
    seen: set[str] = set()
    clauses = [part.strip() for part in re.split(r"[.!?\n]+|\band\b", message, flags=re.IGNORECASE) if part.strip()]
    for clause in clauses:
        for pattern in _COMMITMENT_PATTERNS:
            for match in pattern.finditer(clause):
                verb = str(match.group(1) or "").strip().lower()
                target = str(match.group(2) or "").strip(" .,:;")
                if not target:
                    continue
                normalized = _normalize_commitment_text(f"{verb} {target}".strip())
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                commitments.append(
                    {
                        "what": normalized,
                        "normalized_what": normalized,
                        "promised_turn": turn_number,
                    }
                )
    return commitments


def _message_fulfills_commitment(body: str, commitment: Dict[str, Any]) -> bool:
    normalized_body = _normalize_commitment_text(body)
    if not normalized_body:
        return False
    if not any(cue in normalized_body for cue in _COMMITMENT_FULFILLMENT_CUES):
        return False
    commitment_text = str(commitment.get("normalized_what", "")).strip()
    if not commitment_text:
        return False
    commitment_tokens = set(commitment_text.split())
    body_tokens = set(normalized_body.split())
    if not commitment_tokens or not body_tokens:
        return False
    return len(commitment_tokens & body_tokens) >= max(1, min(2, len(commitment_tokens)))


def _update_pending_commitments(
    pending_commitments: List[Dict[str, Any]],
    *,
    athlete_message_body: str,
    turn_number: int,
) -> tuple[List[Dict[str, Any]], int, int, int]:
    fulfilled = 0
    max_age_observed = max(
        (max(0, turn_number - int(commitment.get("promised_turn", turn_number))) for commitment in pending_commitments),
        default=0,
    )
    remaining: List[Dict[str, Any]] = []
    for commitment in pending_commitments:
        if _message_fulfills_commitment(athlete_message_body, commitment):
            fulfilled += 1
            continue
        remaining.append(dict(commitment))
    new_commitments = _extract_commitments_from_message(athlete_message_body, turn_number=turn_number)
    created = len(new_commitments)
    remaining.extend(new_commitments)
    return remaining, created, fulfilled, max_age_observed


def _render_pending_commitments(
    pending_commitments: List[Dict[str, Any]],
    *,
    turn_number: int,
) -> List[Dict[str, Any]]:
    rendered: List[Dict[str, Any]] = []
    for commitment in pending_commitments:
        rendered.append(
            {
                "what": commitment["what"],
                "promised_turn": commitment["promised_turn"],
                "turns_outstanding": max(0, turn_number - int(commitment["promised_turn"])),
            }
        )
    return rendered


def _build_run_narrative(
    *,
    turn_count: int,
    stop_reason: str,
    avg_felt_understood: float,
    avg_athlete_communication_style_fit: float,
    avg_scores: Dict[str, float],
    issue_counts: Counter[str],
    strength_counts: Counter[str],
    repetition_alert_count: int,
    max_consecutive_similar_athlete_messages: int,
    open_commitments_created: int,
    open_commitments_fulfilled: int,
    max_commitment_age_turns: int,
) -> str:
    score_bits = ", ".join(f"{key}={value:.2f}" for key, value in avg_scores.items())
    issues = ", ".join(_top_counter_entries(issue_counts)) or "none"
    strengths = ", ".join(_top_counter_entries(strength_counts)) or "none"
    return (
        f"Conversation ended after {turn_count} turns via {stop_reason}. "
        f"Athlete felt-understood average was {avg_felt_understood:.2f}; "
        f"athlete-reported communication-style fit average was {avg_athlete_communication_style_fit:.2f}. "
        f"Judge averages: {score_bits}. Top issues: {issues}. Top strengths: {strengths}. "
        f"Repetition alerts: {repetition_alert_count}; max consecutive similar athlete messages: "
        f"{max_consecutive_similar_athlete_messages}. "
        f"Commitments created: {open_commitments_created}; fulfilled: {open_commitments_fulfilled}; "
        f"max age: {max_commitment_age_turns} turns."
    )


def _resolved_turn_bounds(
    scenario: Dict[str, Any],
    *,
    default_min_turns: int,
    default_max_turns: int,
) -> tuple[int, int]:
    min_turns = int(scenario.get("min_turns") or default_min_turns)
    max_turns = int(scenario.get("max_turns") or default_max_turns)
    if min_turns < 1 or max_turns < 1:
        raise ValueError("turn bounds must be >= 1")
    if min_turns > max_turns:
        raise ValueError(f"{scenario['id']} min_turns cannot exceed max_turns")
    return min_turns, max_turns


def run_single_attempt(
    *,
    scenario: Dict[str, Any],
    attempt: int,
    athlete_model: Optional[str],
    judge_model: Optional[str],
    output_dir: Path,
    default_min_turns: int,
    default_max_turns: int,
    synthetic_start_datetime: Optional[datetime] = None,
    synthetic_days_per_turn: int = DEFAULT_SYNTHETIC_DAYS_PER_TURN,
    harness_factory=LiveCoachingHarness,
    athlete_client: Any = AthleteSimulator,
    judge_client: Any = CoachReplyJudge,
) -> Dict[str, Any]:
    synthetic_start_datetime = synthetic_start_datetime or datetime.now(timezone.utc)
    started_at = _utc_now_iso()
    timer_start = perf_counter()
    min_turns, max_turns = _resolved_turn_bounds(
        scenario,
        default_min_turns=default_min_turns,
        default_max_turns=default_max_turns,
    )
    communication_style_preferences = list(scenario.get("communication_style_preferences", []))
    run_id = f"{scenario['id'].lower()}-attempt{attempt}-{int(time.time())}-{secrets.token_hex(4)}"
    transcript_path = output_dir / f"{run_id}.jsonl"
    summary_path = output_dir / f"{run_id}.summary.json"
    email_address = f"live-athlete-sim-{scenario['id'].lower()}-{attempt}-{secrets.token_hex(4)}@example.com"
    harness = harness_factory()
    athlete_id: Optional[str] = None
    transcript: List[Dict[str, Any]] = []
    judge_results: List[Dict[str, Any]] = []
    athlete_reactions: List[Dict[str, Any]] = []
    issue_counts: Counter[str] = Counter()
    strength_counts: Counter[str] = Counter()
    repetition_alert_count = 0
    pending_commitments: List[Dict[str, Any]] = []
    open_commitments_created = 0
    open_commitments_fulfilled = 0
    max_commitment_age_turns = 0
    stop_reason = "max_turns_reached"

    base = {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "attempt": attempt,
        "run_id": run_id,
        "started_at": started_at,
        "athlete_model": str(athlete_model or OPENAI_GENERIC_MODEL),
        "judge_model": str(judge_model or OPENAI_REASONING_MODEL),
        "transcript_path": str(transcript_path),
        "summary_path": str(summary_path),
        "communication_style_preferences": communication_style_preferences,
        "status": OK,
        "error": None,
    }

    try:
        harness.prepare_verified_athlete(email_address)
        next_message: Optional[Dict[str, str]] = None
        if scenario.get("opening_message"):
            opening_body = str(scenario["opening_message"]).strip()
            next_message = {
                "subject": _subject_from_body(opening_body),
                "body": opening_body,
                "private_intent": "scenario_opening_message",
            }
        else:
            next_message = athlete_client.generate_opening_message(
                scenario_name=scenario["name"],
                athlete_brief=scenario["athlete_brief"],
                evaluation_focus=list(scenario.get("evaluation_focus", [])),
                min_turns=min_turns,
                max_turns=max_turns,
                communication_style_preferences=communication_style_preferences,
                model_name=athlete_model,
            )

        turn_count = 0
        for turn_number in range(1, max_turns + 1):
            if next_message is None:
                break
            turn_count = turn_number
            synthetic_received_at = synthetic_start_datetime + timedelta(
                days=synthetic_days_per_turn * (turn_number - 1)
            )
            synthetic_date_received = _format_rfc2822_utc(synthetic_received_at)
            athlete_turn = {
                "role": "athlete",
                "turn": turn_number,
                "subject": str(next_message["subject"]).strip(),
                "body": str(next_message["body"]).strip(),
                "date_received": synthetic_date_received,
                "current_phase": _resolve_current_phase(scenario, turn_number),
            }
            transcript.append(athlete_turn)
            pending_commitments, created_now, fulfilled_now, max_age_now = _update_pending_commitments(
                pending_commitments,
                athlete_message_body=athlete_turn["body"],
                turn_number=turn_number,
            )
            open_commitments_created += created_now
            open_commitments_fulfilled += fulfilled_now
            max_commitment_age_turns = max(max_commitment_age_turns, max_age_now)
            rendered_pending_commitments = _render_pending_commitments(
                pending_commitments,
                turn_number=turn_number,
            )
            max_commitment_age_turns = max(
                max_commitment_age_turns,
                max((item["turns_outstanding"] for item in rendered_pending_commitments), default=0),
            )
            _append_jsonl(
                transcript_path,
                {
                    "phase": "athlete_turn",
                    "turn": turn_number,
                    "subject": athlete_turn["subject"],
                    "body": athlete_turn["body"],
                    "date_received": synthetic_date_received,
                    "current_phase": athlete_turn["current_phase"],
                    "pending_commitments": rendered_pending_commitments,
                },
            )

            try:
                harness_result = harness.send_inbound_email(
                    email_address,
                    subject=athlete_turn["subject"],
                    body=athlete_turn["body"],
                    date_received=synthetic_date_received,
                )
            except TypeError as exc:
                if "unexpected keyword argument 'date_received'" not in str(exc):
                    raise
                harness_result = harness.send_inbound_email(
                    email_address,
                    subject=athlete_turn["subject"],
                    body=athlete_turn["body"],
                )
            athlete_id = harness_result.athlete_id

            # ---- Handle suppressed replies (strategist suppress or response-gen failure) ----
            if harness_result.suppressed:
                print(f"  [suppressed] T{turn_number} — coach chose not to reply ({harness_result.lambda_body})")
                _append_jsonl(
                    transcript_path,
                    {
                        "phase": "coach_suppressed",
                        "turn": turn_number,
                        "lambda_body": harness_result.lambda_body,
                    },
                )
                # Add a placeholder to the transcript so the athlete agent knows the coach was silent
                coach_reply = {
                    "role": "coach",
                    "turn": turn_number,
                    "suppressed": True,
                    "text": "(Coach chose not to reply this turn.)",
                    "lambda_body": harness_result.lambda_body,
                }
                transcript.append(coach_reply)

                # Let the athlete react to the silence
                conversation_directive = _detect_repetition(transcript)
                if conversation_directive:
                    repetition_alert_count += 1
                reaction = athlete_client.react_to_coach_reply(
                    scenario_name=scenario["name"],
                    athlete_brief=scenario["athlete_brief"],
                    transcript=transcript,
                    latest_athlete_message=athlete_turn,
                    latest_coach_reply=coach_reply,
                    min_turns=min_turns,
                    max_turns=max_turns,
                    turn_number=turn_number,
                    evaluation_focus=list(scenario.get("evaluation_focus", [])),
                    communication_style_preferences=communication_style_preferences,
                    conversation_directive=conversation_directive,
                    current_phase=athlete_turn["current_phase"],
                    pending_commitments=rendered_pending_commitments,
                    model_name=athlete_model,
                )
                if turn_number < min_turns and not reaction["continue_conversation"]:
                    if not reaction["next_subject"] or not reaction["next_body"]:
                        raise AthleteSimulationError(
                            f"athlete attempted to stop before min_turns={min_turns} without providing a follow-up"
                        )
                    reaction = dict(reaction)
                    reaction["continue_conversation"] = True
                    reaction["stop_reason"] = f"forced_continue_before_min_turns:{reaction['stop_reason'] or 'empty'}"
                    reaction["forced_continue_before_min_turns"] = True
                athlete_reactions.append(reaction)
                _append_jsonl(
                    transcript_path,
                    {
                        "phase": "athlete_reaction",
                        "turn": turn_number,
                        "conversation_directive": conversation_directive,
                        "current_phase": athlete_turn["current_phase"],
                        "pending_commitments": rendered_pending_commitments,
                        "reaction": reaction,
                    },
                )

                if not reaction["continue_conversation"] and turn_number >= min_turns:
                    stop_reason = reaction["stop_reason"] or "athlete_stopped"
                    next_message = None
                    break

                if turn_number == max_turns:
                    stop_reason = "max_turns_reached"
                    next_message = None
                    break

                next_message = {
                    "subject": reaction["next_subject"],
                    "body": reaction["next_body"],
                }
                continue

            # ---- Normal (non-suppressed) reply path ----
            coach_reply = {
                "role": "coach",
                "turn": turn_number,
                "subject": harness_result.outbound["subject"],
                "text": harness_result.outbound["text"],
                "html": harness_result.outbound["html"],
                "lambda_body": harness_result.lambda_body,
                "date_received": harness_result.date_received,
            }
            transcript.append(coach_reply)
            # Capture obedience eval result from coaching module
            obedience_eval = getattr(_coaching_module, "last_obedience_eval_result", None)
            _coaching_module.last_obedience_eval_result = None  # reset for next turn

            # Capture pipeline trace (strategist/writer inputs and outputs)
            pipeline_trace = getattr(_coaching_module, "last_pipeline_trace", None)
            _coaching_module.last_pipeline_trace = None  # reset for next turn

            _append_jsonl(
                transcript_path,
                {
                    "phase": "coach_reply",
                    "turn": turn_number,
                    "subject": coach_reply["subject"],
                    "text": coach_reply["text"],
                    "html": coach_reply["html"],
                    "lambda_body": coach_reply["lambda_body"],
                    "obedience_eval": obedience_eval,
                    "pipeline_trace": pipeline_trace,
                },
            )

            if obedience_eval and not obedience_eval.get("passed"):
                tags = [v["violation_type"] for v in obedience_eval.get("violations", [])]
                print(f"  [obedience] T{turn_number} CORRECTED — {', '.join(tags)}")
            elif obedience_eval and obedience_eval.get("passed"):
                print(f"  [obedience] T{turn_number} passed")
            elif obedience_eval and obedience_eval.get("error"):
                print(f"  [obedience] T{turn_number} ERROR — used original email")

            state_snapshot = harness.fetch_state_snapshot(athlete_id)
            _append_jsonl(
                transcript_path,
                {
                    "phase": "state_snapshot",
                    "turn": turn_number,
                    "snapshot": state_snapshot,
                },
            )

            judge_result = judge_client.evaluate_reply(
                scenario_name=scenario["name"],
                judge_brief=scenario["judge_brief"],
                transcript=transcript,
                latest_athlete_message=athlete_turn,
                latest_coach_reply=coach_reply,
                state_snapshot=state_snapshot,
                evaluation_focus=list(scenario.get("evaluation_focus", [])),
                communication_style_preferences=communication_style_preferences,
                model_name=judge_model,
            )
            judge_results.append(judge_result)
            issue_counts.update(judge_result["issue_tags"])
            strength_counts.update(judge_result["strength_tags"])
            _append_jsonl(
                transcript_path,
                {
                    "phase": "judge_result",
                    "turn": turn_number,
                    "result": judge_result,
                },
            )

            conversation_directive = _detect_repetition(transcript)
            if conversation_directive:
                repetition_alert_count += 1
            reaction = athlete_client.react_to_coach_reply(
                scenario_name=scenario["name"],
                athlete_brief=scenario["athlete_brief"],
                transcript=transcript,
                latest_athlete_message=athlete_turn,
                latest_coach_reply=coach_reply,
                min_turns=min_turns,
                max_turns=max_turns,
                turn_number=turn_number,
                evaluation_focus=list(scenario.get("evaluation_focus", [])),
                communication_style_preferences=communication_style_preferences,
                conversation_directive=conversation_directive,
                current_phase=athlete_turn["current_phase"],
                pending_commitments=rendered_pending_commitments,
                model_name=athlete_model,
            )
            if turn_number < min_turns and not reaction["continue_conversation"]:
                if not reaction["next_subject"] or not reaction["next_body"]:
                    raise AthleteSimulationError(
                        f"athlete attempted to stop before min_turns={min_turns} without providing a follow-up"
                    )
                reaction = dict(reaction)
                reaction["continue_conversation"] = True
                reaction["stop_reason"] = f"forced_continue_before_min_turns:{reaction['stop_reason'] or 'empty'}"
                reaction["forced_continue_before_min_turns"] = True
            athlete_reactions.append(reaction)
            _append_jsonl(
                transcript_path,
                    {
                        "phase": "athlete_reaction",
                        "turn": turn_number,
                        "conversation_directive": conversation_directive,
                        "current_phase": athlete_turn["current_phase"],
                        "pending_commitments": rendered_pending_commitments,
                        "reaction": reaction,
                    },
                )

            if not reaction["continue_conversation"] and turn_number >= min_turns:
                stop_reason = reaction["stop_reason"] or "athlete_stopped"
                next_message = None
                break

            if turn_number == max_turns:
                stop_reason = "max_turns_reached"
                next_message = None
                break

            next_message = {
                "subject": reaction["next_subject"],
                "body": reaction["next_body"],
            }

        avg_scores = {
            "understanding": _average(result["scores"]["understanding"] for result in judge_results),
            "memory_continuity": _average(result["scores"]["memory_continuity"] for result in judge_results),
            "personalization": _average(result["scores"]["personalization"] for result in judge_results),
            "coaching_quality": _average(result["scores"]["coaching_quality"] for result in judge_results),
            "tone_trust": _average(result["scores"]["tone_trust"] for result in judge_results),
            "communication_style_fit": _average(
                result["scores"]["communication_style_fit"] for result in judge_results
            ),
            "safety": _average(result["scores"]["safety"] for result in judge_results),
        }
        avg_felt_understood = _average(
            reaction["felt_understood_score"] for reaction in athlete_reactions
        )
        avg_athlete_communication_style_fit = _average(
            reaction["communication_style_fit"] for reaction in athlete_reactions
        )
        max_consecutive_similar_athlete_messages = _max_consecutive_similar_athlete_messages(transcript)
        phase_coverage = _phase_coverage(transcript)
        ended_at = _utc_now_iso()
        summary = {
            **base,
            "ended_at": ended_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "athlete_id": athlete_id,
            "email_address": email_address,
            "synthetic_start_datetime": synthetic_start_datetime.isoformat(),
            "synthetic_days_per_turn": synthetic_days_per_turn,
            "turn_count": turn_count,
            "stop_reason": stop_reason,
            "average_judge_scores": avg_scores,
            "average_athlete_felt_understood": avg_felt_understood,
            "average_athlete_communication_style_fit": avg_athlete_communication_style_fit,
            "issue_tag_counts": _sorted_counter(issue_counts),
            "strength_tag_counts": _sorted_counter(strength_counts),
            "repetition_alert_count": repetition_alert_count,
            "max_consecutive_similar_athlete_messages": max_consecutive_similar_athlete_messages,
            "open_commitments_created": open_commitments_created,
            "open_commitments_fulfilled": open_commitments_fulfilled,
            "max_commitment_age_turns": max_commitment_age_turns,
            "phase_coverage": phase_coverage,
            "final_narrative_summary": _build_run_narrative(
                turn_count=turn_count,
                stop_reason=stop_reason,
                avg_felt_understood=avg_felt_understood,
                avg_athlete_communication_style_fit=avg_athlete_communication_style_fit,
                avg_scores=avg_scores,
                issue_counts=issue_counts,
                strength_counts=strength_counts,
                repetition_alert_count=repetition_alert_count,
                max_consecutive_similar_athlete_messages=max_consecutive_similar_athlete_messages,
                open_commitments_created=open_commitments_created,
                open_commitments_fulfilled=open_commitments_fulfilled,
                max_commitment_age_turns=max_commitment_age_turns,
            ),
        }
        _write_json(summary_path, summary)
        return summary
    except Exception as exc:
        ended_at = _utc_now_iso()
        error_summary = {
            **base,
            "status": ERROR,
            "ended_at": ended_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "athlete_id": athlete_id,
            "email_address": email_address,
            "turn_count": len(athlete_reactions),
            "stop_reason": "error",
            "error": f"{exc}\n{traceback.format_exc()}",
            "average_judge_scores": {},
            "average_athlete_felt_understood": 0.0,
            "average_athlete_communication_style_fit": 0.0,
            "issue_tag_counts": _sorted_counter(issue_counts),
            "strength_tag_counts": _sorted_counter(strength_counts),
            "repetition_alert_count": repetition_alert_count,
            "max_consecutive_similar_athlete_messages": _max_consecutive_similar_athlete_messages(transcript),
            "open_commitments_created": open_commitments_created,
            "open_commitments_fulfilled": open_commitments_fulfilled,
            "max_commitment_age_turns": max_commitment_age_turns,
            "phase_coverage": _phase_coverage(transcript),
            "final_narrative_summary": f"Run failed after {len(athlete_reactions)} completed turns: {exc}",
        }
        _write_json(summary_path, error_summary)
        return error_summary
    finally:
        harness.cleanup(email_address, athlete_id=athlete_id)


def run_scenario_attempts(
    *,
    scenario: Dict[str, Any],
    runs_per_scenario: int,
    athlete_model: Optional[str],
    judge_model: Optional[str],
    output_dir: Path,
    default_min_turns: int,
    default_max_turns: int,
    synthetic_start_datetime: datetime,
    synthetic_days_per_turn: int,
) -> List[Dict[str, Any]]:
    return [
        run_single_attempt(
            scenario=scenario,
            attempt=attempt,
            athlete_model=athlete_model,
            judge_model=judge_model,
            output_dir=output_dir,
            default_min_turns=default_min_turns,
            default_max_turns=default_max_turns,
            synthetic_start_datetime=synthetic_start_datetime,
            synthetic_days_per_turn=synthetic_days_per_turn,
        )
        for attempt in range(1, runs_per_scenario + 1)
    ]


def aggregate_results(
    *,
    scenarios: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    bench_path: Path,
    output_dir: Path,
    athlete_model: Optional[str],
    judge_model: Optional[str],
    runs_per_scenario: int,
    default_min_turns: int,
    default_max_turns: int,
    max_parallel: int,
    synthetic_start_datetime: datetime,
    synthetic_days_per_turn: int,
) -> Dict[str, Any]:
    runs_sorted = sorted(runs, key=lambda item: (item["scenario_id"], item["attempt"]))
    by_scenario: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for run in runs_sorted:
        by_scenario[run["scenario_id"]].append(run)

    per_scenario = []
    for scenario in scenarios:
        scenario_runs = by_scenario.get(scenario["id"], [])
        ok_runs = [run for run in scenario_runs if run["status"] == OK]
        error_runs = [run for run in scenario_runs if run["status"] == ERROR]
        avg_turns = _average(run["turn_count"] for run in ok_runs)
        avg_understood = _average(run["average_athlete_felt_understood"] for run in ok_runs)
        avg_repetition_alerts = _average(run.get("repetition_alert_count", 0) for run in ok_runs)
        avg_max_similar = _average(run.get("max_consecutive_similar_athlete_messages", 0) for run in ok_runs)
        avg_phase_coverage = _average(len(run.get("phase_coverage", [])) for run in ok_runs)
        avg_commitments_created = _average(run.get("open_commitments_created", 0) for run in ok_runs)
        avg_commitments_fulfilled = _average(run.get("open_commitments_fulfilled", 0) for run in ok_runs)
        avg_max_commitment_age = _average(run.get("max_commitment_age_turns", 0) for run in ok_runs)
        issue_counter: Counter[str] = Counter()
        strength_counter: Counter[str] = Counter()
        for run in scenario_runs:
            issue_counter.update(run.get("issue_tag_counts", {}))
            strength_counter.update(run.get("strength_tag_counts", {}))
        per_scenario.append(
            {
                "scenario_id": scenario["id"],
                "scenario_name": scenario["name"],
                "ok_runs": len(ok_runs),
                "error_runs": len(error_runs),
                "avg_turn_count_ok_runs": avg_turns,
                "avg_athlete_felt_understood_ok_runs": avg_understood,
                "avg_repetition_alert_count_ok_runs": avg_repetition_alerts,
                "avg_max_consecutive_similar_athlete_messages_ok_runs": avg_max_similar,
                "avg_phase_coverage_ok_runs": avg_phase_coverage,
                "avg_open_commitments_created_ok_runs": avg_commitments_created,
                "avg_open_commitments_fulfilled_ok_runs": avg_commitments_fulfilled,
                "avg_max_commitment_age_turns_ok_runs": avg_max_commitment_age,
                "top_issue_tags": _top_counter_entries(issue_counter),
                "top_strength_tags": _top_counter_entries(strength_counter),
            }
        )

    total_issue_counter: Counter[str] = Counter()
    total_strength_counter: Counter[str] = Counter()
    for run in runs_sorted:
        total_issue_counter.update(run.get("issue_tag_counts", {}))
        total_strength_counter.update(run.get("strength_tag_counts", {}))

    return {
        "generated_at": _utc_now_iso(),
        "benchmark_path": str(bench_path),
        "output_dir": str(output_dir),
        "athlete_model": str(athlete_model or OPENAI_GENERIC_MODEL),
        "judge_model": str(judge_model or OPENAI_REASONING_MODEL),
        "runs_per_scenario": runs_per_scenario,
        "default_min_turns": default_min_turns,
        "default_max_turns": default_max_turns,
        "max_parallel": max_parallel,
        "synthetic_start_datetime": synthetic_start_datetime.isoformat(),
        "synthetic_days_per_turn": synthetic_days_per_turn,
        "total_scenarios": len(scenarios),
        "total_runs": len(runs_sorted),
        "ok_runs": len([run for run in runs_sorted if run["status"] == OK]),
        "error_runs": len([run for run in runs_sorted if run["status"] == ERROR]),
        "per_scenario": per_scenario,
        "runs": runs_sorted,
        "top_issue_tags": _top_counter_entries(total_issue_counter, limit=5),
        "top_strength_tags": _top_counter_entries(total_strength_counter, limit=5),
        "avg_repetition_alert_count_ok_runs": _average(
            run.get("repetition_alert_count", 0) for run in runs_sorted if run["status"] == OK
        ),
        "avg_max_consecutive_similar_athlete_messages_ok_runs": _average(
            run.get("max_consecutive_similar_athlete_messages", 0) for run in runs_sorted if run["status"] == OK
        ),
        "avg_phase_coverage_ok_runs": _average(
            len(run.get("phase_coverage", [])) for run in runs_sorted if run["status"] == OK
        ),
        "avg_open_commitments_created_ok_runs": _average(
            run.get("open_commitments_created", 0) for run in runs_sorted if run["status"] == OK
        ),
        "avg_open_commitments_fulfilled_ok_runs": _average(
            run.get("open_commitments_fulfilled", 0) for run in runs_sorted if run["status"] == OK
        ),
        "avg_max_commitment_age_turns_ok_runs": _average(
            run.get("max_commitment_age_turns", 0) for run in runs_sorted if run["status"] == OK
        ),
    }


def write_results_json(summary: Dict[str, Any], path: Path) -> None:
    _write_json(path, summary)


def _print_run_line(run: Dict[str, Any]) -> None:
    avg_scores = run.get("average_judge_scores", {})
    score_bits = ", ".join(f"{key}={value:.2f}" for key, value in avg_scores.items()) if avg_scores else "n/a"
    top_issues = ", ".join(_top_counter_entries(Counter(run.get("issue_tag_counts", {})))) or "none"
    print(
        f"[{run['scenario_id']} attempt={run['attempt']}] status={run['status']} "
        f"turns={run.get('turn_count', 0)} stop={run.get('stop_reason', 'unknown')} "
        f"felt={run.get('average_athlete_felt_understood', 0.0):.2f} "
        f"ath_style={run.get('average_athlete_communication_style_fit', 0.0):.2f} "
        f"repetition_alerts={run.get('repetition_alert_count', 0)} "
        f"max_similar={run.get('max_consecutive_similar_athlete_messages', 0)} "
        f"commitments={run.get('open_commitments_fulfilled', 0)}/{run.get('open_commitments_created', 0)} "
        f"phases={len(run.get('phase_coverage', []))} "
        f"scores={score_bits} issues={top_issues}",
        flush=True,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    bench_path = Path(args.bench).expanduser().resolve()
    synthetic_start_datetime = _resolve_synthetic_start_datetime(args.synthetic_start_date)
    require_prerequisites(
        bench_path,
        runs_per_scenario=args.runs_per_scenario,
        min_turns=args.min_turns,
        max_turns=args.max_turns,
        max_parallel=args.max_parallel,
        synthetic_days_per_turn=args.synthetic_days_per_turn,
    )
    scenarios = select_scenarios(
        load_athlete_agent_bench_scenarios(bench_path),
        args.scenario,
    )
    if not scenarios:
        print("No scenarios selected.", file=sys.stderr)
        return 2

    output_dir = make_output_dir(args.output_dir)
    all_runs: List[Dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        future_map = {
            executor.submit(
                run_scenario_attempts,
                scenario=scenario,
                runs_per_scenario=args.runs_per_scenario,
                athlete_model=args.athlete_model,
                judge_model=args.judge_model,
                output_dir=output_dir,
                default_min_turns=args.min_turns,
                default_max_turns=args.max_turns,
                synthetic_start_datetime=synthetic_start_datetime,
                synthetic_days_per_turn=args.synthetic_days_per_turn,
            ): scenario
            for scenario in scenarios
        }
        for future in as_completed(future_map):
            runs = future.result()
            all_runs.extend(runs)
            for run in runs:
                _print_run_line(run)

    summary = aggregate_results(
        scenarios=scenarios,
        runs=all_runs,
        bench_path=bench_path,
        output_dir=output_dir,
        athlete_model=args.athlete_model,
        judge_model=args.judge_model,
        runs_per_scenario=args.runs_per_scenario,
        default_min_turns=args.min_turns,
        default_max_turns=args.max_turns,
        max_parallel=args.max_parallel,
        synthetic_start_datetime=synthetic_start_datetime,
        synthetic_days_per_turn=args.synthetic_days_per_turn,
    )
    results_path = output_dir / "results.json"
    write_results_json(summary, results_path)
    print(
        f"completed runs={summary['total_runs']} ok={summary['ok_runs']} error={summary['error_runs']} "
        f"top_issues={', '.join(summary['top_issue_tags']) or 'none'} "
        f"results={results_path}",
        flush=True,
    )
    return 0 if summary["error_runs"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
