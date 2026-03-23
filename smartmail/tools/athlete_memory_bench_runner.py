#!/usr/bin/env python3
"""Run sequential athlete-memory benchmark scenarios through live MemorySkill refresh calls."""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import time
import threading
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from contextlib import contextmanager, nullcontext
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, Iterator, List
from unittest import mock


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

import dynamodb_models
from athlete_memory_reducer import apply_candidate_refresh
from athlete_memory_bench_fixture import (
    DEFAULT_BENCH_PATH,
    load_athlete_memory_bench_scenarios,
)
from skills.memory import MemoryRefreshError, run_candidate_memory_refresh


logger = logging.getLogger(__name__)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "athlete-memory-bench"
OK = "ok"
ASSERTION_FAILED = "assertion_failed"
REFRESH_ERROR = "memory_refresh_error"
STORE_ERROR = "store_error"
EXCEPTION = "exception"

COACH_READY = "coach_ready"
MEMORY_OK_BUT_NOISY = "memory_ok_but_noisy"
UNSAFE_FOR_COACHING = "unsafe_for_coaching"

DIMENSION_WEIGHTS = {
    "durable_memory_quality": 0.3,
    "active_context_quality": 0.15,
    "retirement_quality": 0.2,
    "noise_control": 0.15,
    "coach_actionability": 0.15,
    "wording_nits": 0.05,
}
NEGATION_MARKERS = (
    "no longer",
    "not anymore",
    "isn't true anymore",
    "isnt true anymore",
    "outdated",
    "retired",
    "retire",
    "dropped",
    "drop the",
    "drop the old",
    "remove the",
    "moved from",
    "instead of",
    "opened up",
    "available now",
)
ROUTINE_STATUS_MARKERS = (
    "this week",
    "normal week",
    "today",
    "felt smooth",
    "on script",
    "got both",
    "completed both",
)
MATCH_STOPWORDS = {
    "a",
    "an",
    "am",
    "and",
    "are",
    "as",
    "at",
    "before",
    "by",
    "every",
    "finish",
    "finishes",
    "finishing",
    "for",
    "in",
    "is",
    "it",
    "its",
    "main",
    "most",
    "my",
    "night",
    "of",
    "on",
    "pm",
    "primary",
    "scheduled",
    "still",
    "that",
    "the",
    "their",
    "this",
    "to",
    "usual",
    "usually",
    "week",
}
TOKEN_EQUIVALENTS = {
    "available": "open",
    "availability": "open",
    "flexibility": "open",
    "flexible": "open",
    "opening": "open",
    "opens": "open",
    "saturdays": "saturday",
    "sundays": "sunday",
    "swimming": "swim",
    "swimmer": "swim",
    "swims": "swim",
    "strengthgroup": "strength",
    "triathlon": "tri",
    "triathlete": "tri",
    "bikework": "bike",
    "bikes": "bike",
    "workout": "train",
    "workouts": "train",
}


class _BenchCoachProfilesTable:
    def __init__(self):
        self.items: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def get_item(self, **kwargs: Any) -> Dict[str, Any]:
        athlete_id = kwargs.get("Key", {}).get("athlete_id")
        with self._lock:
            item = self.items.get(str(athlete_id or ""))
        if item is None:
            return {}
        return {"Item": dict(item)}

    def update_item(self, **kwargs: Any) -> Dict[str, Any]:
        athlete_id = str(kwargs.get("Key", {}).get("athlete_id") or "")
        values = kwargs.get("ExpressionAttributeValues", {})
        with self._lock:
            item = dict(self.items.get(athlete_id, {"athlete_id": athlete_id}))
            if ":created_at" in values and "created_at" not in item:
                item["created_at"] = values[":created_at"]
            if ":updated_at" in values:
                item["updated_at"] = values[":updated_at"]
            if ":memory_notes" in values:
                item["memory_notes"] = values[":memory_notes"]
            if ":continuity_summary" in values:
                item["continuity_summary"] = values[":continuity_summary"]
            self.items[athlete_id] = item
        return {}


class _RoutingDynamo:
    def __init__(self, tables: Dict[str, Any]):
        self.tables = tables

    def Table(self, name: str):  # noqa: N802
        return self.tables[name]


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run athlete-memory benchmark scenarios through live MemorySkill refresh calls."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Path to athlete-memory benchmark markdown fixture.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for benchmark artifacts.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario id filter; may be repeated.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent scenarios to run.",
    )
    parser.add_argument(
        "--runs-per-scenario",
        type=int,
        default=1,
        help="Number of independent runs to execute for each scenario.",
    )
    return parser


def use_live_dynamo() -> bool:
    return os.getenv("ATHLETE_MEMORY_BENCH_USE_LIVE_DYNAMO", "false").strip().lower() == "true"


def require_prerequisites(bench_path: Path, *, max_parallel: int) -> None:
    missing: List[str] = []
    if not bench_path.exists():
        missing.append(f"athlete memory benchmark fixture not found: {bench_path}")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        missing.append("OPENAI_API_KEY is required for live athlete-memory benchmark runs.")
    if missing:
        raise RuntimeError("\n".join(missing))
    if max_parallel < 1:
        raise RuntimeError("--max-parallel must be at least 1.")
    os.environ["ENABLE_LIVE_LLM_CALLS"] = "true"


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
        if scenario["id"].strip().lower() in wanted
    ]


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = re.sub(r"(\d+):00\s*(am|pm)\b", r"\1\2", text)
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return " ".join(text.split())


def _normalize_signal(signal: str) -> str:
    return _normalize_text(signal)


def _canonical_match_token(token: str) -> str:
    time_match = re.fullmatch(r"(\d+)(am|pm)?", token)
    if time_match:
        return time_match.group(1)
    token = TOKEN_EQUIVALENTS.get(token, token)
    if token.endswith("ies") and len(token) > 3:
        return token[:-3] + "y"
    if token.endswith("s") and len(token) > 3 and not token.endswith("ss"):
        return token[:-1]
    return token


def _canonical_match_tokens(text: str) -> List[str]:
    return [_canonical_match_token(token) for token in text.split() if token]


def _content_match_tokens(text: str) -> List[str]:
    return [
        token
        for token in _canonical_match_tokens(text)
        if token and token not in MATCH_STOPWORDS
    ]


def _note_texts(notes: Iterable[Dict[str, Any]]) -> List[str]:
    return [_normalize_text(note.get("summary", "")) for note in notes if isinstance(note, dict)]


def get_benchmark_memory_notes(athlete_id: str) -> List[Dict[str, Any]]:
    """Read AM2 durable facts for benchmark matching."""
    return dynamodb_models.get_memory_notes(athlete_id)


def get_benchmark_retrieval_context(athlete_id: str) -> Dict[str, Any]:
    retrieval_context = dynamodb_models.get_memory_context_for_response_generation(athlete_id)
    # memory_notes is already a flat list of DurableFact dicts from AM2
    return retrieval_context


def _continuity_texts(continuity_summary: Dict[str, Any] | None) -> Dict[str, List[str] | str]:
    continuity_summary = continuity_summary or {}
    summary = _normalize_text(continuity_summary.get("summary", ""))
    recommendation = _normalize_text(continuity_summary.get("last_recommendation", ""))
    open_loops = [
        _normalize_text(value)
        for value in continuity_summary.get("open_loops", [])
        if _normalize_text(value)
    ]
    return {
        "summary": summary,
        "recommendation": recommendation,
        "open_loops": open_loops,
        "all_text": [summary, recommendation, *open_loops],
    }


def _signal_matches_text(signal: str, text: str) -> bool:
    if not signal or not text:
        return False
    if signal in text:
        return True
    signal_tokens = signal.split()
    text_tokens = text.split()
    if not signal_tokens or not text_tokens:
        return False
    text_index = 0
    for token in signal_tokens:
        while text_index < len(text_tokens) and text_tokens[text_index] != token:
            text_index += 1
        if text_index == len(text_tokens):
            break
        text_index += 1
    else:
        return True

    signal_content = _content_match_tokens(signal)
    text_content = set(_content_match_tokens(text))
    if not signal_content or not text_content:
        return False
    return all(token in text_content for token in signal_content)


def _fact_matches_text(fact: Dict[str, Any], text: str) -> bool:
    all_signals = list(fact.get("signals", [])) + list(fact.get("aliases", [])) + list(fact.get("semantic_signals", []))
    return any(_signal_matches_text(_normalize_signal(signal), text) for signal in all_signals)


def _fact_matches_any_text(fact: Dict[str, Any], texts: Iterable[str]) -> bool:
    return any(_fact_matches_text(fact, text) for text in texts)


def _fact_importance(fact: Dict[str, Any]) -> str:
    return str(fact.get("importance", "medium")).strip().lower()


def _is_negated(text: str) -> bool:
    return any(marker in text for marker in NEGATION_MARKERS)


def _fact_is_operationally_present(fact: Dict[str, Any], texts: Iterable[str]) -> bool:
    for text in texts:
        if _fact_matches_text(fact, text) and not _is_negated(text):
            return True
    return False


def _match_labels(
    *,
    facts: List[Dict[str, Any]],
    texts: Iterable[str],
    operational: bool = False,
) -> tuple[List[str], List[str]]:
    matched: List[str] = []
    missing: List[str] = []
    for fact in facts:
        found = (
            _fact_is_operationally_present(fact, texts)
            if operational
            else _fact_matches_any_text(fact, texts)
        )
        if found:
            matched.append(fact["label"])
        else:
            missing.append(fact["label"])
    return matched, missing


def _split_by_match_importance(
    *,
    facts: List[Dict[str, Any]],
    missing_labels: List[str],
) -> tuple[List[str], List[str]]:
    high: List[str] = []
    advisory: List[str] = []
    missing_set = set(missing_labels)
    for fact in facts:
        if fact["label"] not in missing_set:
            continue
        if _fact_importance(fact) == "high":
            high.append(fact["label"])
        else:
            advisory.append(fact["label"])
    return high, advisory


def _is_actionability_advisory(fact: Dict[str, Any]) -> bool:
    label = _normalize_text(fact.get("label", ""))
    if label.startswith("recommendation uses "):
        return True
    if label.startswith("open loop:"):
        return True
    if label.startswith("adjust for "):
        remainder = label.removeprefix("adjust for ").strip()
        if len(remainder.split()) <= 2 and _fact_importance(fact) != "high":
            return True
    return False


def _looks_like_routine_status(text: str) -> bool:
    normalized = _normalize_text(text)
    if any(marker in normalized for marker in ROUTINE_STATUS_MARKERS):
        return True
    count_tokens = (
        "one",
        "two",
        "three",
        "four",
        "five",
        "1",
        "2",
        "3",
        "4",
        "5",
    )
    workout_tokens = (
        "session",
        "sessions",
        "swim",
        "swims",
        "run",
        "runs",
        "ride",
        "rides",
        "court",
    )
    return any(token in normalized for token in count_tokens) and any(token in normalized for token in workout_tokens)


def _dimension_state(score: float) -> str:
    if score >= 0.99:
        return "pass"
    if score >= 0.5:
        return "warn"
    return "fail"


def _make_dimension(
    *,
    name: str,
    matched: List[str],
    missing: List[str],
    findings: List[str],
) -> Dict[str, Any]:
    total = len(matched) + len(missing)
    score = 1.0 if total == 0 else round(len(matched) / total, 3)
    dimension_findings = list(findings)
    if missing:
        dimension_findings.append(f"missing: {', '.join(missing)}")
    if matched:
        dimension_findings.append(f"matched: {', '.join(matched)}")
    return {
        "name": name,
        "score": score,
        "state": _dimension_state(score),
        "matched": matched,
        "missing": missing,
        "findings": dimension_findings,
    }


def _coach_label(score: float, dimensions: Dict[str, Dict[str, Any]]) -> str:
    failing = {
        name
        for name, value in dimensions.items()
        if value["state"] == "fail"
    }
    if {"durable_memory_quality", "retirement_quality", "coach_actionability"} & failing:
        return UNSAFE_FOR_COACHING
    if score >= 0.85 and not failing:
        return COACH_READY
    return MEMORY_OK_BUT_NOISY


def evaluate_step_result(
    *,
    previous_notes: List[Dict[str, Any]] | None = None,
    current_notes: List[Dict[str, Any]],
    continuity_summary: Dict[str, Any] | None,
    expectations: Dict[str, Any],
) -> Dict[str, Any]:
    previous_notes = previous_notes or []
    note_texts = _note_texts(current_notes)
    continuity_text = _continuity_texts(continuity_summary)
    continuity_all = list(continuity_text["all_text"])

    durable_matched, durable_missing = _match_labels(
        facts=expectations["durable_truths"],
        texts=note_texts,
    )
    active_context_mode = expectations.get("active_context_mode", "acceptable")
    if active_context_mode == "required":
        active_matched, active_missing = _match_labels(
            facts=expectations["active_context"],
            texts=continuity_all,
        )
        active_findings: List[str] = []
    elif active_context_mode == "acceptable":
        active_matched, active_missing = _match_labels(
            facts=expectations["active_context"],
            texts=continuity_all,
        )
        active_missing = []
        active_findings = []
    else:
        active_matched = []
        active_missing = []
        stale_active_texts = [
            continuity_text["summary"],
            continuity_text["recommendation"],
        ]
        stale_active_context = [
            fact["label"]
            for fact in expectations["active_context"]
            if _fact_is_operationally_present(fact, stale_active_texts)
        ]
        active_findings = []
        if stale_active_context:
            active_missing = stale_active_context
            active_findings.append(
                f"stale temporary context still operational: {', '.join(stale_active_context)}"
            )

    retired_cleared: List[str] = []
    retired_still_active: List[str] = []
    for fact in expectations["retired_truths"]:
        if _fact_is_operationally_present(fact, note_texts + continuity_all):
            retired_still_active.append(fact["label"])
        else:
            retired_cleared.append(fact["label"])

    noise_absent: List[str] = []
    noise_promoted: List[str] = []
    for fact in expectations["routine_noise"]:
        if _fact_matches_any_text(fact, note_texts):
            noise_promoted.append(fact["label"])
        else:
            noise_absent.append(fact["label"])
    if expectations.get("message_intent") == "routine_checkin":
        previous_note_texts = _note_texts(previous_notes)
        heuristic_noise = [
            text
            for text in note_texts
            if _looks_like_routine_status(text) and text not in previous_note_texts
        ]
        for text in heuristic_noise:
            if text not in noise_promoted:
                noise_promoted.append(text)

    substantive_adjust_facts = [
        fact for fact in expectations["coach_should_adjust_for"] if not _is_actionability_advisory(fact)
    ]
    advisory_adjust_facts = [
        fact for fact in expectations["coach_should_adjust_for"] if _is_actionability_advisory(fact)
    ]
    adjust_matched, adjust_missing = _match_labels(
        facts=substantive_adjust_facts,
        texts=continuity_all,
    )
    advisory_matched, advisory_missing = _match_labels(
        facts=advisory_adjust_facts,
        texts=continuity_all,
    )
    should_not_do_avoided: List[str] = []
    should_not_do_present: List[str] = []
    for fact in expectations["coach_should_not_do"]:
        if _fact_is_operationally_present(fact, continuity_all):
            should_not_do_present.append(fact["label"])
        else:
            should_not_do_avoided.append(fact["label"])

    durable_high_missing, durable_advisory_missing = _split_by_match_importance(
        facts=expectations["durable_truths"],
        missing_labels=durable_missing,
    )
    substantive_adjust_high_missing, substantive_adjust_advisory_missing = _split_by_match_importance(
        facts=substantive_adjust_facts,
        missing_labels=adjust_missing,
    )

    dimensions = {
        "durable_memory_quality": _make_dimension(
            name="durable_memory_quality",
            matched=durable_matched,
            missing=durable_high_missing,
            findings=[],
        ),
        "active_context_quality": _make_dimension(
            name="active_context_quality",
            matched=active_matched,
            missing=active_missing,
            findings=active_findings,
        ),
        "retirement_quality": _make_dimension(
            name="retirement_quality",
            matched=retired_cleared,
            missing=retired_still_active,
            findings=[],
        ),
        "noise_control": _make_dimension(
            name="noise_control",
            matched=noise_absent,
            missing=noise_promoted,
            findings=[],
        ),
        "coach_actionability": _make_dimension(
            name="coach_actionability",
            matched=adjust_matched + should_not_do_avoided,
            missing=substantive_adjust_high_missing + should_not_do_present,
            findings=[],
        ),
        "wording_nits": _make_dimension(
            name="wording_nits",
            matched=advisory_matched,
            missing=durable_advisory_missing + substantive_adjust_advisory_missing + advisory_missing,
            findings=[],
        ),
    }

    weighted_score = round(
        sum(dimensions[name]["score"] * weight for name, weight in DIMENSION_WEIGHTS.items() if name in dimensions),
        3,
    )
    label = _coach_label(weighted_score, dimensions)
    critical_failures: List[str] = []
    for name in ("durable_memory_quality", "retirement_quality", "coach_actionability"):
        if dimensions[name]["state"] == "fail":
            critical_failures.append(name)
    status = OK if label != UNSAFE_FOR_COACHING else ASSERTION_FAILED

    key_misses = (
        durable_high_missing + durable_advisory_missing
        + active_missing
        + retired_still_active
        + substantive_adjust_high_missing + substantive_adjust_advisory_missing + advisory_missing
        + should_not_do_present
    )
    over_retention_flags = list(noise_promoted)
    stale_assumption_risks = retired_still_active + should_not_do_present

    findings: List[str] = []
    for dimension in dimensions.values():
        if dimension["missing"]:
            findings.append(
                f"{dimension['name']}: missing {', '.join(dimension['missing'])}"
            )

    return {
        "status": status,
        "label": label,
        "score": weighted_score,
        "critical_failures": critical_failures,
        "findings": findings,
        "key_misses": key_misses,
        "stale_assumption_risks": stale_assumption_risks,
        "over_retention_flags": over_retention_flags,
        "dimensions": dimensions,
    }


def evaluate_final_retrieval(
    *,
    current_notes: List[Dict[str, Any]],
    retrieval_context: Dict[str, Any],
    final_assertions: Dict[str, Any],
) -> Dict[str, Any]:
    note_texts = _note_texts(current_notes)
    retrieval_texts = _note_texts(retrieval_context.get("memory_notes", []))

    durable_matched, durable_missing = _match_labels(
        facts=final_assertions["final_durable_truths"],
        texts=note_texts,
    )
    retrieval_matched, retrieval_missing = _match_labels(
        facts=final_assertions["final_retrieval_support"],
        texts=retrieval_texts,
    )
    retired_cleared: List[str] = []
    retired_present: List[str] = []
    for fact in final_assertions["final_retired_truths"]:
        if _fact_is_operationally_present(fact, note_texts + retrieval_texts):
            retired_present.append(fact["label"])
        else:
            retired_cleared.append(fact["label"])

    findings: List[str] = []
    durable_high_missing, durable_advisory_missing = _split_by_match_importance(
        facts=final_assertions["final_durable_truths"],
        missing_labels=durable_missing,
    )
    retrieval_high_missing, retrieval_advisory_missing = _split_by_match_importance(
        facts=final_assertions["final_retrieval_support"],
        missing_labels=retrieval_missing,
    )
    warnings: List[str] = []
    if durable_high_missing:
        findings.append(f"final durable truths missing: {', '.join(durable_high_missing)}")
    elif durable_advisory_missing:
        warnings.append(f"final durable truths missing: {', '.join(durable_advisory_missing)}")
    if retrieval_high_missing:
        findings.append(f"retrieval support missing: {', '.join(retrieval_high_missing)}")
    elif retrieval_advisory_missing:
        warnings.append(f"retrieval support missing: {', '.join(retrieval_advisory_missing)}")
    if retired_present:
        findings.append(f"retired truths still actionable: {', '.join(retired_present)}")

    total_expected = (
        len(final_assertions["final_durable_truths"])
        + len(final_assertions["final_retrieval_support"])
        + len(final_assertions["final_retired_truths"])
    )
    matched_total = len(durable_matched) + len(retrieval_matched) + len(retired_cleared)
    score = 1.0 if total_expected == 0 else round(matched_total / total_expected, 3)

    return {
        "score": score,
        "findings": findings,
        "warnings": warnings,
        "durable_missing": durable_high_missing + durable_advisory_missing,
        "retrieval_missing": retrieval_high_missing + retrieval_advisory_missing,
        "retired_present": retired_present,
        "status": OK if not findings else ASSERTION_FAILED,
    }


@contextmanager
def local_fake_storage() -> Iterator[None]:
    profile_table = _BenchCoachProfilesTable()
    routing = _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table})
    with mock.patch.object(dynamodb_models, "dynamodb", routing):
        yield


def _interaction_context(
    *,
    scenario: Dict[str, Any],
    message: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "inbound_email": message["email"],
        "inbound_subject": f"{scenario['sport']} benchmark step {message['step']}",
        "coach_reply": message["synthetic_coach_reply"],
        "profile_updates_applied": [],
        "manual_activity_detected": False,
        "selected_model_name": "athlete_memory_bench",
        "rule_engine_decision": {
            "scenario_id": scenario["id"],
            "profile_hint": scenario["profile_hint"],
            "step": message["step"],
        },
    }


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def apply_benchmark_memory_refresh(
    *,
    athlete_id: str,
    latest_interaction_context: Dict[str, Any],
) -> Dict[str, Any]:
    current_memory_notes = dynamodb_models.get_memory_notes(athlete_id)
    current_continuity = dynamodb_models.get_continuity_summary(athlete_id)

    validated = run_candidate_memory_refresh(
        current_memory_notes=current_memory_notes,
        current_continuity=current_continuity,
        interaction_context=latest_interaction_context,
    )
    persisted = apply_candidate_refresh(validated, current_memory_notes, int(time.time()))
    if not dynamodb_models.replace_memory(
        athlete_id,
        persisted["memory_notes"],
        persisted["continuity_summary"],
    ):
        raise MemoryRefreshError("memory persistence failed")

    return {
        "memory_notes": get_benchmark_memory_notes(athlete_id),
        "continuity_summary": dynamodb_models.get_continuity_summary(athlete_id),
        "pre_reply_route": "candidate",
        "post_reply_route": "candidate",
        "long_term_debug": {
            "pre_reply": None,
            "post_reply": validated,
        },
        "routing_debug": {
            "pre_reply": None,
            "post_reply": {
                "latest_interaction_context": latest_interaction_context,
                "mode": "candidate",
            },
        },
    }


def run_single_scenario(
    scenario: Dict[str, Any],
    *,
    run_index: int = 1,
    total_runs: int = 1,
) -> Dict[str, Any]:
    athlete_id = f"bench_{scenario['id'].lower()}_run_{run_index:02d}"
    step_results: List[Dict[str, Any]] = []
    started_at = datetime.now(timezone.utc).isoformat()
    timer_start = perf_counter()
    previous_notes: List[Dict[str, Any]] = []

    try:
        for message in scenario["messages"]:
            interaction_context = _interaction_context(scenario=scenario, message=message)
            step_timer_start = perf_counter()
            step_started_at = _utc_now_iso()
            logger.info(
                "Starting memory refresh scenario=%s step=%s athlete_id=%s",
                scenario["id"],
                message["step"],
                athlete_id,
            )
            try:
                refreshed = apply_benchmark_memory_refresh(
                    athlete_id=athlete_id,
                    latest_interaction_context=interaction_context,
                )
                api_duration_seconds = round(perf_counter() - step_timer_start, 4)
                step_completed_at = _utc_now_iso()
                logger.info(
                    "Completed memory refresh scenario=%s step=%s athlete_id=%s duration_seconds=%.4f pre_reply_route=%s post_reply_route=%s",
                    scenario["id"],
                    message["step"],
                    athlete_id,
                    api_duration_seconds,
                    refreshed.get("pre_reply_route", ""),
                    refreshed.get("post_reply_route", ""),
                )
            except MemoryRefreshError as exc:
                api_duration_seconds = round(perf_counter() - step_timer_start, 4)
                step_completed_at = _utc_now_iso()
                logger.error(
                    "Memory refresh failed scenario=%s step=%s athlete_id=%s duration_seconds=%.4f cause=%s",
                    scenario["id"],
                    message["step"],
                    athlete_id,
                    api_duration_seconds,
                    getattr(exc, "cause_message", str(exc)),
                )
                step_results.append(
                    {
                        "step": message["step"],
                        "started_at": step_started_at,
                        "completed_at": step_completed_at,
                        "api_duration_seconds": api_duration_seconds,
                        "status": REFRESH_ERROR,
                        "label": UNSAFE_FOR_COACHING,
                        "score": 0.0,
                        "critical_failures": ["memory_refresh_error"],
                        "findings": [str(exc)],
                        "memory_notes": [],
                        "continuity_summary": None,
                        "dimensions": {},
                        "key_misses": [],
                        "stale_assumption_risks": [],
                        "over_retention_flags": [],
                    }
                )
                return {
                    "scenario_id": scenario["id"],
                    "run_index": run_index,
                    "total_runs": total_runs,
                    "athlete_name": scenario["athlete_name"],
                    "sport": scenario["sport"],
                    "started_at": started_at,
                    "duration_seconds": round(perf_counter() - timer_start, 4),
                    "status": REFRESH_ERROR,
                    "step_results": step_results,
                    "final_evaluation": None,
                        "retrieval_context": None,
                }

            current_notes = get_benchmark_memory_notes(athlete_id)
            continuity_summary = dynamodb_models.get_continuity_summary(athlete_id)
            evaluation = evaluate_step_result(
                previous_notes=previous_notes,
                current_notes=current_notes,
                continuity_summary=continuity_summary,
                expectations=message,
            )
            step_results.append(
                {
                    "step": message["step"],
                    "started_at": step_started_at,
                    "completed_at": step_completed_at,
                    "api_duration_seconds": api_duration_seconds,
                    "status": evaluation["status"],
                    "label": evaluation["label"],
                    "score": evaluation["score"],
                    "critical_failures": evaluation["critical_failures"],
                    "findings": evaluation["findings"],
                    "memory_notes": current_notes,
                    "continuity_summary": continuity_summary,
                    "long_term_debug": refreshed.get("long_term_debug"),
                    "routing_debug": refreshed.get("routing_debug"),
                    "dimensions": evaluation["dimensions"],
                    "key_misses": evaluation["key_misses"],
                    "stale_assumption_risks": evaluation["stale_assumption_risks"],
                    "over_retention_flags": evaluation["over_retention_flags"],
                }
            )
            previous_notes = current_notes

        retrieval_context = get_benchmark_retrieval_context(athlete_id)
        final_evaluation = evaluate_final_retrieval(
            current_notes=get_benchmark_memory_notes(athlete_id),
            retrieval_context=retrieval_context,
            final_assertions=scenario["final_assertions"],
        )
        unsafe_steps = sum(
            1 for step in step_results if step["label"] == UNSAFE_FOR_COACHING
        )
        scenario_status = OK if unsafe_steps == 0 and final_evaluation["status"] == OK else ASSERTION_FAILED
        return {
            "scenario_id": scenario["id"],
            "run_index": run_index,
            "total_runs": total_runs,
            "athlete_name": scenario["athlete_name"],
            "sport": scenario["sport"],
            "started_at": started_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "status": scenario_status,
            "step_results": step_results,
            "final_evaluation": final_evaluation,
            "retrieval_context": retrieval_context,
        }
    except Exception as exc:  # pragma: no cover - defensive capture
        return {
            "scenario_id": scenario["id"],
            "run_index": run_index,
            "total_runs": total_runs,
            "athlete_name": scenario["athlete_name"],
            "sport": scenario["sport"],
            "started_at": started_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "status": EXCEPTION,
            "step_results": step_results,
            "final_evaluation": {
                "status": ASSERTION_FAILED,
                "score": 0.0,
                "findings": [f"{exc}\n{traceback.format_exc()}"],
                "durable_missing": [],
                "retrieval_missing": [],
                "retired_present": [],
            },
            "retrieval_context": None,
        }


def aggregate_results(
    *,
    scenarios: List[Dict[str, Any]],
    runs: List[Dict[str, Any]],
    bench_path: Path,
    output_dir: Path,
    runs_per_scenario: int,
) -> Dict[str, Any]:
    status_counts = Counter(run["status"] for run in runs)
    step_label_counts = Counter(
        step.get("label", COACH_READY)
        for run in runs
        for step in run.get("step_results", [])
    )
    per_scenario: List[Dict[str, Any]] = []
    for scenario in scenarios:
        scenario_runs = [
            item for item in runs
            if item["scenario_id"] == scenario["id"]
        ]
        all_scores = [
            float(step.get("score", 0.0))
            for run in scenario_runs
            for step in run.get("step_results", [])
        ]
        final_scores = [
            float((run.get("final_evaluation") or {}).get("score", 0.0))
            for run in scenario_runs
        ]
        slowest_step = max(
            (
                {
                    **step,
                    "run_index": run.get("run_index"),
                }
                for run in scenario_runs
                for step in run.get("step_results", [])
            ),
            key=lambda step: float(step.get("api_duration_seconds", 0.0)),
            default=None,
        )
        per_scenario.append(
            {
                "scenario_id": scenario["id"],
                "athlete_name": scenario_runs[0]["athlete_name"],
                "sport": scenario_runs[0]["sport"],
                "runs_attempted": len(scenario_runs),
                "status_counts": dict(Counter(run["status"] for run in scenario_runs)),
                "pass_rate": round(
                    sum(1 for run in scenario_runs if run["status"] == OK) / len(scenario_runs),
                    3,
                ) if scenario_runs else 0.0,
                "average_duration_seconds": round(
                    sum(float(run["duration_seconds"]) for run in scenario_runs) / len(scenario_runs),
                    4,
                ) if scenario_runs else 0.0,
                "average_step_score": round(sum(all_scores) / len(all_scores), 3) if all_scores else 0.0,
                "unsafe_step_count": sum(
                    1
                    for run in scenario_runs
                    for step in run.get("step_results", [])
                    if step.get("label") == UNSAFE_FOR_COACHING
                ),
                "final_score_average": round(sum(final_scores) / len(final_scores), 3) if final_scores else 0.0,
                "slowest_step": slowest_step,
                "run_results": [
                    {
                        "run_index": run.get("run_index"),
                        "status": run["status"],
                        "duration_seconds": run["duration_seconds"],
                        "final_score": (run.get("final_evaluation") or {}).get("score", 0.0),
                    }
                    for run in sorted(scenario_runs, key=lambda item: int(item.get("run_index", 0)))
                ],
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": str(bench_path),
        "output_dir": str(output_dir),
        "storage_mode": "live_dynamo" if use_live_dynamo() else "local_fake",
        "total_scenarios": len(scenarios),
        "runs_per_scenario": runs_per_scenario,
        "total_runs": len(runs),
        "status_counts": dict(status_counts),
        "step_label_counts": dict(step_label_counts),
        "per_scenario": per_scenario,
        "runs": runs,
    }


def write_summary(summary: Dict[str, Any], path: Path) -> None:
    lines = [
        "# Athlete Memory Benchmark Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Benchmark path: {summary['benchmark_path']}",
        f"- Output dir: {summary['output_dir']}",
        f"- Storage mode: {summary['storage_mode']}",
        f"- Total scenarios: {summary['total_scenarios']}",
        f"- Runs per scenario: {summary['runs_per_scenario']}",
        f"- Total runs: {summary['total_runs']}",
        "",
        "## Coach Readiness",
    ]
    for item in summary["per_scenario"]:
        slowest_step = item.get("slowest_step") or {}
        lines.append(
            f"- {item['scenario_id']} ({item['sport']}): pass_rate={item['pass_rate']} avg_step_score={item['average_step_score']} unsafe_steps={item['unsafe_step_count']} final_score_avg={item['final_score_average']} avg_duration_seconds={item['average_duration_seconds']} status_counts={item['status_counts']} slowest_step={slowest_step.get('step')} slowest_run={slowest_step.get('run_index')} api_duration_seconds={slowest_step.get('api_duration_seconds')}"
        )
        for run_result in item.get("run_results", []):
            lines.append(
                f"- {item['scenario_id']} run {run_result['run_index']}: status={run_result['status']} final_score={run_result['final_score']} duration_seconds={run_result['duration_seconds']}"
            )

    lines.append("")
    lines.append("## Step Timings")
    any_step_timing = False
    for run in summary["runs"]:
        for step in run.get("step_results", []):
            any_step_timing = True
            lines.append(
                f"- {run['scenario_id']} run {run.get('run_index')} step {step['step']}: status={step['status']} label={step.get('label')} score={step.get('score')} started_at={step.get('started_at')} completed_at={step.get('completed_at')} api_duration_seconds={step.get('api_duration_seconds')}"
            )
    if not any_step_timing:
        lines.append("- none")

    lines.append("")
    lines.append("## Durable Memory Misses")
    added = False
    for run in summary["runs"]:
        for step in run.get("step_results", []):
            missing = (step.get("dimensions", {}).get("durable_memory_quality", {}) or {}).get("missing", [])
            if missing:
                added = True
                lines.append(f"- {run['scenario_id']} run {run.get('run_index')} step {step['step']}: {', '.join(missing)}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Active Context Handling")
    added = False
    for run in summary["runs"]:
        for step in run.get("step_results", []):
            missing = (step.get("dimensions", {}).get("active_context_quality", {}) or {}).get("missing", [])
            if missing:
                added = True
                lines.append(f"- {run['scenario_id']} run {run.get('run_index')} step {step['step']}: missing {', '.join(missing)}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Stale Assumption Risks")
    added = False
    for run in summary["runs"]:
        for step in run.get("step_results", []):
            risks = step.get("stale_assumption_risks", [])
            if risks:
                added = True
                lines.append(f"- {run['scenario_id']} run {run.get('run_index')} step {step['step']}: {', '.join(risks)}")
        final_eval = run.get("final_evaluation") or {}
        if final_eval.get("retired_present"):
            added = True
            lines.append(
                f"- {run['scenario_id']} run {run.get('run_index')} final: {', '.join(final_eval['retired_present'])}"
            )
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Noise / Over-Retention")
    added = False
    for run in summary["runs"]:
        for step in run.get("step_results", []):
            flags = step.get("over_retention_flags", [])
            if flags:
                added = True
                lines.append(f"- {run['scenario_id']} run {run.get('run_index')} step {step['step']}: {', '.join(flags)}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Final Retrieval Findings")
    added = False
    for run in summary["runs"]:
        final_eval = run.get("final_evaluation") or {}
        for finding in final_eval.get("findings", []):
            added = True
            lines.append(f"- {run['scenario_id']} run {run.get('run_index')}: {finding}")
    if not added:
        lines.append("- none")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    bench_path = Path(args.bench).expanduser().resolve()
    require_prerequisites(bench_path, max_parallel=args.max_parallel)
    if args.runs_per_scenario < 1:
        raise RuntimeError("--runs-per-scenario must be at least 1.")
    output_dir = make_output_dir(args.output_dir)
    scenarios = select_scenarios(
        load_athlete_memory_bench_scenarios(bench_path),
        args.scenario,
    )
    if not scenarios:
        raise RuntimeError("No athlete memory benchmark scenarios selected.")

    runs: List[Dict[str, Any]] = []
    run_requests = [
        (scenario, run_index)
        for scenario in scenarios
        for run_index in range(1, args.runs_per_scenario + 1)
    ]
    storage_ctx = nullcontext if use_live_dynamo() else local_fake_storage
    with storage_ctx():
        if args.max_parallel == 1:
            runs = [
                run_single_scenario(
                    scenario,
                    run_index=run_index,
                    total_runs=args.runs_per_scenario,
                )
                for scenario, run_index in run_requests
            ]
        else:
            with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
                futures = {
                    executor.submit(
                        run_single_scenario,
                        scenario,
                        run_index=run_index,
                        total_runs=args.runs_per_scenario,
                    ): (scenario["id"], run_index)
                    for scenario, run_index in run_requests
                }
                for future in as_completed(futures):
                    runs.append(future.result())
            runs.sort(key=lambda item: (item["scenario_id"], int(item.get("run_index", 0))))

    summary = aggregate_results(
        scenarios=scenarios,
        runs=runs,
        bench_path=bench_path,
        output_dir=output_dir,
        runs_per_scenario=args.runs_per_scenario,
    )
    (output_dir / "results.json").write_text(
        json.dumps(runs, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=True) + "\n",
        encoding="utf-8",
    )
    write_summary(summary, output_dir / "summary.md")
    print(json.dumps(summary["status_counts"], sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
