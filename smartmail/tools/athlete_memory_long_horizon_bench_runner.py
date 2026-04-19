#!/usr/bin/env python3
"""Run long-horizon athlete-memory benchmark scenarios through live MemorySkill refresh calls."""

from __future__ import annotations

import argparse
import json
import logging
import sys
import traceback
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Dict, Iterable, List


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

from athlete_memory_long_horizon_bench_fixture import (  # noqa: E402
    DEFAULT_LONG_HORIZON_BENCH_PATH,
    load_athlete_memory_long_horizon_bench_scenarios,
)
from skills.memory import MemoryRefreshError  # noqa: E402

import athlete_memory_bench_runner as short_bench  # noqa: E402
import dynamodb_models  # noqa: E402


logger = logging.getLogger(__name__)
DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "athlete-memory-bench"
DEFAULT_OUTPUT_SUBDIR = "long-horizon"

OK = short_bench.OK
ASSERTION_FAILED = short_bench.ASSERTION_FAILED
REFRESH_ERROR = short_bench.REFRESH_ERROR
STORE_ERROR = short_bench.STORE_ERROR
EXCEPTION = short_bench.EXCEPTION

COACH_READY = short_bench.COACH_READY
MEMORY_OK_BUT_NOISY = short_bench.MEMORY_OK_BUT_NOISY
UNSAFE_FOR_COACHING = short_bench.UNSAFE_FOR_COACHING

LONG_DIMENSION_WEIGHTS = {
    "durable_memory_quality": 0.25,
    "active_context_quality": 0.15,
    "retirement_quality": 0.15,
    "noise_control": 0.1,
    "coach_actionability": 0.15,
    "salience_under_pressure": 0.2,
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run long-horizon athlete-memory benchmark scenarios through live MemorySkill refresh calls."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_LONG_HORIZON_BENCH_PATH),
        help="Path to long-horizon athlete-memory benchmark markdown fixture.",
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
    return parser


def _make_output_dir(output_dir: str | None) -> Path:
    if output_dir:
        path = Path(output_dir).expanduser().resolve()
    else:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = DEFAULT_OUTPUT_ROOT / DEFAULT_OUTPUT_SUBDIR / timestamp
    path.mkdir(parents=True, exist_ok=True)
    return path


def _select_scenarios(
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


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _interaction_context(
    *,
    scenario: Dict[str, Any],
    phase: Dict[str, Any],
    message: Dict[str, Any],
) -> Dict[str, Any]:
    return {
        "inbound_email": message["email"],
        "inbound_subject": f"{scenario['sport']} long-horizon benchmark step {message['step']}",
        "coach_reply": message["synthetic_coach_reply"],
        "profile_updates_applied": [],
        "manual_activity_detected": False,
        "selected_model_name": "athlete_memory_long_horizon_bench",
        "rule_engine_decision": {
            "scenario_id": scenario["id"],
            "profile_hint": scenario["profile_hint"],
            "phase_id": phase["phase_id"],
            "phase_goal": phase["phase_goal"],
            "step": message["step"],
            "event_tags": message.get("event_tags", []),
        },
    }


def _salience_dimension(
    *,
    checkpoint_assertions: Dict[str, Any],
    current_notes: List[Dict[str, Any]],
) -> Dict[str, Any]:
    note_texts = short_bench._note_texts(current_notes)  # type: ignore[attr-defined]
    durable_truths = checkpoint_assertions["durable_truths"]
    high_priority = [fact for fact in durable_truths if fact.get("importance") == "high"]
    medium_priority = [fact for fact in durable_truths if fact.get("importance") != "high"]

    high_matched, high_missing = short_bench._match_labels(  # type: ignore[attr-defined]
        facts=high_priority,
        texts=note_texts,
    )
    medium_matched, medium_missing = short_bench._match_labels(  # type: ignore[attr-defined]
        facts=medium_priority,
        texts=note_texts,
    )

    findings: List[str] = []
    score = 1.0
    if high_missing:
        score = 0.0
        findings.append(f"core durable truths dropped under pressure: {', '.join(high_missing)}")
    elif medium_missing:
        score = 0.6
        findings.append(f"secondary durable truths not retained: {', '.join(medium_missing)}")

    noise_present = []
    for fact in checkpoint_assertions["routine_noise"]:
        if short_bench._fact_matches_any_text(fact, note_texts):  # type: ignore[attr-defined]
            noise_present.append(fact["label"])
    if noise_present and high_missing:
        findings.append(f"routine noise retained while core truths were missing: {', '.join(noise_present)}")
        score = 0.0
    elif noise_present and score > 0.5:
        findings.append(f"routine noise retained under memory pressure: {', '.join(noise_present)}")
        score = min(score, 0.6)

    return {
        "name": "salience_under_pressure",
        "score": round(score, 3),
        "state": short_bench._dimension_state(score),  # type: ignore[attr-defined]
        "matched": high_matched + medium_matched,
        "missing": high_missing + medium_missing,
        "findings": findings,
    }


def _section_key_from_label(label: str) -> str:
    normalized = str(label or "").strip().lower()
    return {
        "goal": "goals",
        "goals": "goals",
        "constraint": "constraints",
        "constraints": "constraints",
        "schedule_anchor": "schedule_anchors",
        "schedule_anchors": "schedule_anchors",
        "preference": "preferences",
        "preferences": "preferences",
        "context": "context_notes",
        "context_note": "context_notes",
        "context_notes": "context_notes",
    }.get(normalized, normalized)


def _note_texts(notes: Iterable[Dict[str, Any]]) -> List[str]:
    return short_bench._note_texts(notes)  # type: ignore[attr-defined]


def _normalize_text(value: Any) -> str:
    return short_bench._normalize_text(value)  # type: ignore[attr-defined]


def _normalize_signal(value: Any) -> str:
    return short_bench._normalize_text(value)  # type: ignore[attr-defined]


def _active_and_retired_notes(memory_state: Any) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    if isinstance(memory_state, list):
        return [item for item in memory_state if isinstance(item, dict)], []
    if not isinstance(memory_state, dict):
        return [], []
    section_keys = ("goals", "constraints", "schedule_anchors", "preferences", "context_notes")
    if not any(key in memory_state for key in section_keys):
        notes = memory_state.get("memory_notes")
        if isinstance(notes, list):
            return [item for item in notes if isinstance(item, dict)], []
        return [], []
    active: List[Dict[str, Any]] = []
    retired: List[Dict[str, Any]] = []
    for key in section_keys:
        bucket = memory_state.get(key)
        if not isinstance(bucket, dict):
            continue
        active.extend(item for item in bucket.get("active", []) if isinstance(item, dict))
        retired.extend(item for item in bucket.get("retired", []) if isinstance(item, dict))
    return active, retired


def _section_counts(memory_state: Any, *, bucket_name: str) -> Dict[str, int]:
    if not isinstance(memory_state, dict):
        return {}
    counts: Dict[str, int] = {}
    for key in ("goals", "constraints", "schedule_anchors", "preferences", "context_notes"):
        bucket = memory_state.get(key)
        if isinstance(bucket, dict):
            values = bucket.get(bucket_name, [])
            if isinstance(values, list):
                counts[key] = sum(1 for item in values if isinstance(item, dict))
    return counts


def _compiled_prompt_texts(retrieval_context: Dict[str, Any] | None) -> List[str]:
    if not isinstance(retrieval_context, dict):
        return []
    texts: List[str] = []
    for key in ("priority_facts", "structure_facts", "preference_facts", "context_facts"):
        values = retrieval_context.get(key)
        if not isinstance(values, list):
            continue
        for item in values:
            if isinstance(item, dict):
                normalized = _normalize_text(item.get("summary", ""))
            else:
                normalized = _normalize_text(item)
            if normalized:
                texts.append(normalized)
    if texts:
        return texts
    notes = retrieval_context.get("memory_notes")
    if isinstance(notes, list):
        return _note_texts(notes)
    return []


def _memory_refresh_error_details(exc: Exception) -> Dict[str, Any]:
    raw_response = ""
    cause_message = ""
    if isinstance(exc, MemoryRefreshError):
        raw_response = str(getattr(exc, "raw_response", "") or "")
        cause_message = str(getattr(exc, "cause_message", "") or "")
    cause = getattr(exc, "__cause__", None)
    return {
        "error_type": type(exc).__name__,
        "error_message": str(exc),
        "cause_type": type(cause).__name__ if cause is not None else "",
        "cause_message": cause_message or (str(cause) if cause is not None else ""),
        "raw_response_preview": raw_response[:1000],
    }


def _evaluate_storage_assertions(
    *,
    assertions: Dict[str, Any],
    texts: Iterable[str],
    counts: Dict[str, int],
    dimension_name: str,
) -> Dict[str, Any]:
    findings: List[str] = []
    matched: List[str] = []
    missing: List[str] = []
    if not assertions:
        return {
            "name": dimension_name,
            "score": 1.0,
            "state": short_bench._dimension_state(1.0),  # type: ignore[attr-defined]
            "matched": [],
            "missing": [],
            "findings": [],
        }

    must_include = assertions.get("must_include", [])
    if must_include:
        matched, missing = short_bench._match_labels(facts=must_include, texts=texts)  # type: ignore[attr-defined]
        if missing:
            findings.append(f"{dimension_name} missing: {', '.join(missing)}")

    excluded_present: List[str] = []
    for fact in assertions.get("must_exclude", []):
        if short_bench._fact_matches_any_text(fact, texts):  # type: ignore[attr-defined]
            excluded_present.append(fact["label"])
    if excluded_present:
        findings.append(f"{dimension_name} unexpectedly included: {', '.join(excluded_present)}")

    for raw_key, limit in assertions.get("max_active_counts", {}).items():
        section_key = _section_key_from_label(raw_key)
        actual = counts.get(section_key, 0)
        if actual > limit:
            findings.append(f"{dimension_name} {section_key} count {actual} exceeds max {limit}")
    for raw_key, limit in assertions.get("max_retired_counts", {}).items():
        section_key = _section_key_from_label(raw_key)
        actual = counts.get(section_key, 0)
        if actual > limit:
            findings.append(f"{dimension_name} {section_key} count {actual} exceeds max {limit}")

    score = 1.0 if not findings else 0.0
    return {
        "name": dimension_name,
        "score": score,
        "state": short_bench._dimension_state(score),  # type: ignore[attr-defined]
        "matched": matched,
        "missing": missing + excluded_present,
        "findings": findings,
    }


def _evaluate_rejections(
    *,
    assertions: List[Dict[str, Any]],
    step_results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    findings: List[str] = []
    matched: List[str] = []
    missing: List[str] = []
    actual_texts: List[str] = []
    for step in step_results:
        for rejection in step.get("rejected_candidates", []):
            if not isinstance(rejection, dict):
                continue
            actual_texts.append(
                _normalize_text(
                    " ".join(
                        str(rejection.get(field, ""))
                        for field in ("label", "summary", "fact_key", "reason")
                    )
                )
            )
    for expected in assertions:
        signals = [_normalize_signal(signal) for signal in expected.get("signals", [])]
        reason = _normalize_text(expected.get("reason", ""))
        found = any(all(signal in text for signal in signals) and reason in text for text in actual_texts)
        if found:
            matched.append(expected["label"])
        else:
            missing.append(expected["label"])
    if missing:
        findings.append(f"expected rejections missing: {', '.join(missing)}")
    score = 1.0 if not findings else 0.0
    return {
        "name": "expected_rejections",
        "score": score,
        "state": short_bench._dimension_state(score),  # type: ignore[attr-defined]
        "matched": matched,
        "missing": missing,
        "findings": findings,
    }


def evaluate_checkpoint_result(
    *,
    current_notes: Any,
    continuity_summary: Dict[str, Any] | None,
    checkpoint_assertions: Dict[str, Any],
    retrieval_context: Dict[str, Any] | None = None,
    step_results: List[Dict[str, Any]] | None = None,
) -> Dict[str, Any]:
    active_notes, retired_notes = _active_and_retired_notes(current_notes)
    base = short_bench.evaluate_step_result(
        current_notes=active_notes,
        continuity_summary=continuity_summary,
        expectations=checkpoint_assertions,
    )
    dimensions = dict(base["dimensions"])
    salience_dimension = _salience_dimension(
        checkpoint_assertions=checkpoint_assertions,
        current_notes=active_notes,
    )
    dimensions["salience_under_pressure"] = salience_dimension

    if checkpoint_assertions.get("expected_active_storage"):
        dimensions["expected_active_storage"] = _evaluate_storage_assertions(
            assertions=checkpoint_assertions["expected_active_storage"],
            texts=_note_texts(active_notes),
            counts=_section_counts(current_notes, bucket_name="active"),
            dimension_name="expected_active_storage",
        )

    if checkpoint_assertions.get("expected_retired_storage"):
        dimensions["expected_retired_storage"] = _evaluate_storage_assertions(
            assertions=checkpoint_assertions["expected_retired_storage"],
            texts=_note_texts(retired_notes),
            counts=_section_counts(current_notes, bucket_name="retired"),
            dimension_name="expected_retired_storage",
        )

    if checkpoint_assertions.get("expected_compiled_prompt"):
        dimensions["expected_compiled_prompt"] = _evaluate_storage_assertions(
            assertions=checkpoint_assertions["expected_compiled_prompt"],
            texts=_compiled_prompt_texts(retrieval_context),
            counts={},
            dimension_name="expected_compiled_prompt",
        )

    if checkpoint_assertions.get("expected_rejections"):
        dimensions["expected_rejections"] = _evaluate_rejections(
            assertions=checkpoint_assertions["expected_rejections"],
            step_results=step_results or [],
        )

    weighted_score = round(
        sum(dimensions[name]["score"] * weight for name, weight in LONG_DIMENSION_WEIGHTS.items() if name in dimensions),
        3,
    )
    failing = {
        name
        for name, value in dimensions.items()
        if value["state"] == "fail"
    }
    if {"durable_memory_quality", "retirement_quality", "coach_actionability", "salience_under_pressure"} & failing:
        label = UNSAFE_FOR_COACHING
        status = ASSERTION_FAILED
    elif weighted_score >= 0.85 and not failing:
        label = COACH_READY
        status = OK
    else:
        label = MEMORY_OK_BUT_NOISY
        status = OK

    key_misses = list(base["key_misses"]) + list(salience_dimension["missing"])
    findings = list(base["findings"]) + list(salience_dimension["findings"])
    for dimension_name in (
        "expected_active_storage",
        "expected_retired_storage",
        "expected_compiled_prompt",
        "expected_rejections",
    ):
        dimension = dimensions.get(dimension_name) or {}
        key_misses.extend(dimension.get("missing", []))
        findings.extend(dimension.get("findings", []))
    critical_failures = list(base["critical_failures"])
    if salience_dimension["state"] == "fail":
        critical_failures.append("salience_under_pressure")

    return {
        "status": status,
        "label": label,
        "score": weighted_score,
        "critical_failures": critical_failures,
        "findings": findings,
        "key_misses": key_misses,
        "stale_assumption_risks": base["stale_assumption_risks"],
        "over_retention_flags": list(base["over_retention_flags"]),
        "dimensions": dimensions,
    }


def run_single_scenario(scenario: Dict[str, Any]) -> Dict[str, Any]:
    athlete_id = f"long_bench_{scenario['id'].lower()}"
    step_results: List[Dict[str, Any]] = []
    checkpoint_results: List[Dict[str, Any]] = []
    started_at = datetime.now(timezone.utc).isoformat()
    timer_start = perf_counter()

    try:
        for phase in scenario["phases"]:
            for message in phase["messages"]:
                interaction_context = _interaction_context(
                    scenario=scenario,
                    phase=phase,
                    message=message,
                )
                step_timer_start = perf_counter()
                step_started_at = _utc_now_iso()
                logger.info(
                    "Starting long-horizon memory refresh scenario=%s phase=%s step=%s athlete_id=%s",
                    scenario["id"],
                    phase["phase_id"],
                    message["step"],
                    athlete_id,
                )
                try:
                    refreshed = short_bench.apply_benchmark_memory_refresh(
                        athlete_id=athlete_id,
                        latest_interaction_context=interaction_context,
                    )
                    api_duration_seconds = round(perf_counter() - step_timer_start, 4)
                    step_completed_at = _utc_now_iso()
                    logger.info(
                        "Completed long-horizon memory refresh scenario=%s phase=%s step=%s athlete_id=%s duration_seconds=%.4f pre_reply_route=%s post_reply_route=%s",
                        scenario["id"],
                        phase["phase_id"],
                        message["step"],
                        athlete_id,
                        api_duration_seconds,
                        refreshed.get("pre_reply_route", ""),
                        refreshed.get("post_reply_route", ""),
                    )
                except MemoryRefreshError as exc:
                    api_duration_seconds = round(perf_counter() - step_timer_start, 4)
                    step_completed_at = _utc_now_iso()
                    error_details = _memory_refresh_error_details(exc)
                    logger.error(
                        "Long-horizon memory refresh failed scenario=%s phase=%s step=%s athlete_id=%s duration_seconds=%.4f error_type=%s cause_type=%s cause=%s",
                        scenario["id"],
                        phase["phase_id"],
                        message["step"],
                        athlete_id,
                        api_duration_seconds,
                        error_details["error_type"],
                        error_details["cause_type"],
                        error_details["cause_message"] or error_details["error_message"],
                    )
                    step_results.append(
                        {
                            "phase_id": phase["phase_id"],
                            "phase_goal": phase["phase_goal"],
                            "step": message["step"],
                            "event_tags": message.get("event_tags", []),
                            "started_at": step_started_at,
                            "completed_at": step_completed_at,
                            "api_duration_seconds": api_duration_seconds,
                            "status": REFRESH_ERROR,
                            "pre_reply_route": "",
                            "post_reply_route": "",
                            "memory_notes": [],
                            "continuity_summary": None,
                            "rejected_candidates": [],
                            **error_details,
                        }
                    )
                    return {
                        "scenario_id": scenario["id"],
                        "athlete_name": scenario["athlete_name"],
                        "sport": scenario["sport"],
                        "started_at": started_at,
                        "duration_seconds": round(perf_counter() - timer_start, 4),
                        "status": REFRESH_ERROR,
                        "step_results": step_results,
                        "checkpoint_results": checkpoint_results,
                        "final_evaluation": None,
                        "retrieval_context": None,
                    }

                current_notes = short_bench.get_benchmark_memory_notes(athlete_id)
                continuity_summary = dynamodb_models.get_continuity_summary(athlete_id)
                step_results.append(
                    {
                        "phase_id": phase["phase_id"],
                        "phase_goal": phase["phase_goal"],
                        "step": message["step"],
                        "event_tags": message.get("event_tags", []),
                        "started_at": step_started_at,
                        "completed_at": step_completed_at,
                        "api_duration_seconds": api_duration_seconds,
                        "status": OK,
                        "pre_reply_route": refreshed.get("pre_reply_route", ""),
                        "post_reply_route": refreshed.get("post_reply_route", ""),
                        "memory_notes": current_notes,
                        "continuity_summary": continuity_summary,
                        "rejected_candidates": list(refreshed.get("rejected_candidates", [])) if isinstance(refreshed, dict) else [],
                    }
                )

            phase_notes = short_bench.get_benchmark_memory_notes(athlete_id)
            phase_continuity = dynamodb_models.get_continuity_summary(athlete_id)
            phase_retrieval_context = short_bench.get_benchmark_retrieval_context(athlete_id)
            checkpoint = evaluate_checkpoint_result(
                current_notes=phase_notes,
                continuity_summary=phase_continuity,
                checkpoint_assertions=phase["checkpoint_assertions"],
                retrieval_context=phase_retrieval_context,
                step_results=step_results,
            )
            checkpoint_results.append(
                {
                    "phase_id": phase["phase_id"],
                    "phase_goal": phase["phase_goal"],
                    "checkpoint_label": phase["checkpoint_assertions"]["label"],
                    **checkpoint,
                }
            )

        retrieval_context = short_bench.get_benchmark_retrieval_context(athlete_id)
        final_evaluation = short_bench.evaluate_final_retrieval(
            current_notes=short_bench.get_benchmark_memory_notes(athlete_id),
            retrieval_context=retrieval_context,
            final_assertions=scenario["final_assertions"],
        )
        final_active_notes, final_retired_notes = _active_and_retired_notes(
            short_bench.get_benchmark_memory_notes(athlete_id)
        )
        final_findings = list(final_evaluation.get("findings", []))
        final_key_misses = list(final_evaluation.get("durable_missing", [])) + list(final_evaluation.get("retrieval_missing", []))
        if scenario["final_assertions"].get("final_active_storage"):
            dimension = _evaluate_storage_assertions(
                assertions=scenario["final_assertions"]["final_active_storage"],
                texts=_note_texts(final_active_notes),
                counts=_section_counts(short_bench.get_benchmark_memory_notes(athlete_id), bucket_name="active"),
                dimension_name="final_active_storage",
            )
            final_findings.extend(dimension["findings"])
            final_key_misses.extend(dimension["missing"])
        if scenario["final_assertions"].get("final_retired_storage"):
            dimension = _evaluate_storage_assertions(
                assertions=scenario["final_assertions"]["final_retired_storage"],
                texts=_note_texts(final_retired_notes),
                counts=_section_counts(short_bench.get_benchmark_memory_notes(athlete_id), bucket_name="retired"),
                dimension_name="final_retired_storage",
            )
            final_findings.extend(dimension["findings"])
            final_key_misses.extend(dimension["missing"])
        if scenario["final_assertions"].get("final_compiled_prompt"):
            dimension = _evaluate_storage_assertions(
                assertions=scenario["final_assertions"]["final_compiled_prompt"],
                texts=_compiled_prompt_texts(retrieval_context),
                counts={},
                dimension_name="final_compiled_prompt",
            )
            final_findings.extend(dimension["findings"])
            final_key_misses.extend(dimension["missing"])
        if scenario["final_assertions"].get("final_rejections"):
            dimension = _evaluate_rejections(
                assertions=scenario["final_assertions"]["final_rejections"],
                step_results=step_results,
            )
            final_findings.extend(dimension["findings"])
            final_key_misses.extend(dimension["missing"])
        final_evaluation["findings"] = final_findings
        final_evaluation["key_misses"] = final_key_misses
        if final_findings:
            final_evaluation["status"] = ASSERTION_FAILED
        scenario_status = OK
        if any(result["label"] == UNSAFE_FOR_COACHING for result in checkpoint_results):
            scenario_status = ASSERTION_FAILED
        if final_evaluation["status"] != OK:
            scenario_status = ASSERTION_FAILED
        return {
            "scenario_id": scenario["id"],
            "athlete_name": scenario["athlete_name"],
            "sport": scenario["sport"],
            "started_at": started_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "status": scenario_status,
            "step_results": step_results,
            "checkpoint_results": checkpoint_results,
            "final_evaluation": final_evaluation,
            "retrieval_context": retrieval_context,
        }
    except Exception as exc:  # pragma: no cover - defensive capture
        return {
            "scenario_id": scenario["id"],
            "athlete_name": scenario["athlete_name"],
            "sport": scenario["sport"],
            "started_at": started_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "status": EXCEPTION,
            "step_results": step_results,
            "checkpoint_results": checkpoint_results,
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
) -> Dict[str, Any]:
    status_counts = Counter(run["status"] for run in runs)
    checkpoint_label_counts = Counter(
        checkpoint["label"]
        for run in runs
        for checkpoint in run.get("checkpoint_results", [])
    )
    per_scenario: List[Dict[str, Any]] = []
    for scenario in scenarios:
        run = next(item for item in runs if item["scenario_id"] == scenario["id"])
        checkpoint_scores = [
            float(checkpoint.get("score", 0.0))
            for checkpoint in run.get("checkpoint_results", [])
        ]
        per_scenario.append(
            {
                "scenario_id": scenario["id"],
                "athlete_name": run["athlete_name"],
                "sport": run["sport"],
                "status": run["status"],
                "duration_seconds": run["duration_seconds"],
                "average_checkpoint_score": (
                    round(sum(checkpoint_scores) / len(checkpoint_scores), 3)
                    if checkpoint_scores else 0.0
                ),
                "unsafe_checkpoint_count": sum(
                    1
                    for checkpoint in run.get("checkpoint_results", [])
                    if checkpoint["label"] == UNSAFE_FOR_COACHING
                ),
                "final_score": (run.get("final_evaluation") or {}).get("score", 0.0),
                "slowest_step": max(
                    run.get("step_results", []),
                    key=lambda step: float(step.get("api_duration_seconds", 0.0)),
                    default=None,
                ),
            }
        )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": str(bench_path),
        "output_dir": str(output_dir),
        "storage_mode": "live_dynamo" if short_bench.use_live_dynamo() else "local_fake",
        "total_scenarios": len(scenarios),
        "status_counts": dict(status_counts),
        "checkpoint_label_counts": dict(checkpoint_label_counts),
        "per_scenario": per_scenario,
        "runs": runs,
    }


def write_summary(summary: Dict[str, Any], path: Path) -> None:
    lines = [
        "# Long-Horizon Athlete Memory Benchmark Summary",
        "",
        f"- Generated at: {summary['generated_at']}",
        f"- Benchmark path: {summary['benchmark_path']}",
        f"- Output dir: {summary['output_dir']}",
        f"- Storage mode: {summary['storage_mode']}",
        f"- Total scenarios: {summary['total_scenarios']}",
        "",
        "## Checkpoint Readiness",
    ]
    for item in summary["per_scenario"]:
        slowest_step = item.get("slowest_step") or {}
        lines.append(
            f"- {item['scenario_id']} ({item['sport']}): {item['status']} avg_checkpoint_score={item['average_checkpoint_score']} unsafe_checkpoints={item['unsafe_checkpoint_count']} final_score={item['final_score']} duration_seconds={item['duration_seconds']} slowest_step={slowest_step.get('step')} api_duration_seconds={slowest_step.get('api_duration_seconds')}"
        )

    lines.append("")
    lines.append("## Durable Truth Survival")
    added = False
    for run in summary["runs"]:
        for checkpoint in run.get("checkpoint_results", []):
            missing = (checkpoint.get("dimensions", {}).get("durable_memory_quality", {}) or {}).get("missing", [])
            if missing:
                added = True
                lines.append(f"- {run['scenario_id']} {checkpoint['phase_id']}: {', '.join(missing)}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Temporary Context Lifecycle")
    added = False
    for run in summary["runs"]:
        for checkpoint in run.get("checkpoint_results", []):
            missing = (checkpoint.get("dimensions", {}).get("active_context_quality", {}) or {}).get("missing", [])
            if missing:
                added = True
                lines.append(f"- {run['scenario_id']} {checkpoint['phase_id']}: missing {', '.join(missing)}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Stale Assumption Risks")
    added = False
    for run in summary["runs"]:
        for checkpoint in run.get("checkpoint_results", []):
            risks = checkpoint.get("stale_assumption_risks", [])
            if risks:
                added = True
                lines.append(f"- {run['scenario_id']} {checkpoint['phase_id']}: {', '.join(risks)}")
        final_eval = run.get("final_evaluation") or {}
        if final_eval.get("retired_present"):
            added = True
            lines.append(
                f"- {run['scenario_id']} final: {', '.join(final_eval['retired_present'])}"
            )
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Salience / Compression Failures")
    added = False
    for run in summary["runs"]:
        for checkpoint in run.get("checkpoint_results", []):
            salience = checkpoint.get("dimensions", {}).get("salience_under_pressure", {}) or {}
            if salience.get("missing") or salience.get("findings"):
                added = True
                parts = list(salience.get("findings", []))
                if salience.get("missing"):
                    parts.append("missing: " + ", ".join(salience["missing"]))
                lines.append(f"- {run['scenario_id']} {checkpoint['phase_id']}: {' | '.join(parts)}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Final Coach Retrieval")
    added = False
    for run in summary["runs"]:
        final_eval = run.get("final_evaluation") or {}
        for finding in final_eval.get("findings", []):
            added = True
            lines.append(f"- {run['scenario_id']}: {finding}")
    if not added:
        lines.append("- none")

    lines.append("")
    lines.append("## Step Timings")
    added = False
    for run in summary["runs"]:
        for step in run.get("step_results", []):
            added = True
            lines.append(
                f"- {run['scenario_id']} {step['phase_id']} step {step['step']}: status={step['status']} api_duration_seconds={step.get('api_duration_seconds')}"
            )
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
    short_bench.require_prerequisites(bench_path, max_parallel=args.max_parallel)
    output_dir = _make_output_dir(args.output_dir)
    scenarios = _select_scenarios(
        load_athlete_memory_long_horizon_bench_scenarios(bench_path),
        args.scenario,
    )
    if not scenarios:
        raise RuntimeError("No long-horizon athlete memory benchmark scenarios selected.")

    runs: List[Dict[str, Any]] = []
    storage_ctx = short_bench.local_fake_storage if not short_bench.use_live_dynamo() else short_bench.nullcontext
    with storage_ctx():
        if args.max_parallel == 1:
            runs = [run_single_scenario(scenario) for scenario in scenarios]
        else:
            with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
                futures = {
                    executor.submit(run_single_scenario, scenario): scenario["id"]
                    for scenario in scenarios
                }
                for future in as_completed(futures):
                    runs.append(future.result())
            runs.sort(key=lambda item: item["scenario_id"])

    summary = aggregate_results(
        scenarios=scenarios,
        runs=runs,
        bench_path=bench_path,
        output_dir=output_dir,
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
