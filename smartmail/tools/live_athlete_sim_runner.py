#!/usr/bin/env python3
"""Run a live athlete simulator bench against the local coaching workflow."""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from decimal import Decimal
from datetime import datetime, timezone
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
from live_coaching_harness import LiveCoachingHarness  # noqa: E402


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "live-athlete-sim"
OK = "ok"
ERROR = "error"


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
    return parser


def require_prerequisites(
    bench_path: Path,
    *,
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    max_parallel: int,
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


def _build_run_narrative(
    *,
    turn_count: int,
    stop_reason: str,
    avg_felt_understood: float,
    avg_athlete_communication_style_fit: float,
    avg_scores: Dict[str, float],
    issue_counts: Counter[str],
    strength_counts: Counter[str],
) -> str:
    score_bits = ", ".join(f"{key}={value:.2f}" for key, value in avg_scores.items())
    issues = ", ".join(_top_counter_entries(issue_counts)) or "none"
    strengths = ", ".join(_top_counter_entries(strength_counts)) or "none"
    return (
        f"Conversation ended after {turn_count} turns via {stop_reason}. "
        f"Athlete felt-understood average was {avg_felt_understood:.2f}; "
        f"athlete-reported communication-style fit average was {avg_athlete_communication_style_fit:.2f}. "
        f"Judge averages: {score_bits}. Top issues: {issues}. Top strengths: {strengths}."
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
    harness_factory=LiveCoachingHarness,
    athlete_client: Any = AthleteSimulator,
    judge_client: Any = CoachReplyJudge,
) -> Dict[str, Any]:
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
            athlete_turn = {
                "role": "athlete",
                "turn": turn_number,
                "subject": str(next_message["subject"]).strip(),
                "body": str(next_message["body"]).strip(),
            }
            transcript.append(athlete_turn)
            _append_jsonl(
                transcript_path,
                {
                    "phase": "athlete_turn",
                    "turn": turn_number,
                    "subject": athlete_turn["subject"],
                    "body": athlete_turn["body"],
                },
            )

            harness_result = harness.send_inbound_email(
                email_address,
                subject=athlete_turn["subject"],
                body=athlete_turn["body"],
            )
            athlete_id = harness_result.athlete_id
            coach_reply = {
                "role": "coach",
                "turn": turn_number,
                "subject": harness_result.outbound["subject"],
                "text": harness_result.outbound["text"],
                "html": harness_result.outbound["html"],
                "lambda_body": harness_result.lambda_body,
            }
            transcript.append(coach_reply)
            _append_jsonl(
                transcript_path,
                {
                    "phase": "coach_reply",
                    "turn": turn_number,
                    "subject": coach_reply["subject"],
                    "text": coach_reply["text"],
                    "html": coach_reply["html"],
                    "lambda_body": coach_reply["lambda_body"],
                },
            )

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
        ended_at = _utc_now_iso()
        summary = {
            **base,
            "ended_at": ended_at,
            "duration_seconds": round(perf_counter() - timer_start, 4),
            "athlete_id": athlete_id,
            "email_address": email_address,
            "turn_count": turn_count,
            "stop_reason": stop_reason,
            "average_judge_scores": avg_scores,
            "average_athlete_felt_understood": avg_felt_understood,
            "average_athlete_communication_style_fit": avg_athlete_communication_style_fit,
            "issue_tag_counts": _sorted_counter(issue_counts),
            "strength_tag_counts": _sorted_counter(strength_counts),
            "final_narrative_summary": _build_run_narrative(
                turn_count=turn_count,
                stop_reason=stop_reason,
                avg_felt_understood=avg_felt_understood,
                avg_athlete_communication_style_fit=avg_athlete_communication_style_fit,
                avg_scores=avg_scores,
                issue_counts=issue_counts,
                strength_counts=strength_counts,
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
        "total_scenarios": len(scenarios),
        "total_runs": len(runs_sorted),
        "ok_runs": len([run for run in runs_sorted if run["status"] == OK]),
        "error_runs": len([run for run in runs_sorted if run["status"] == ERROR]),
        "per_scenario": per_scenario,
        "runs": runs_sorted,
        "top_issue_tags": _top_counter_entries(total_issue_counter, limit=5),
        "top_strength_tags": _top_counter_entries(total_strength_counter, limit=5),
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
        f"scores={score_bits} issues={top_issues}",
        flush=True,
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    bench_path = Path(args.bench).expanduser().resolve()
    require_prerequisites(
        bench_path,
        runs_per_scenario=args.runs_per_scenario,
        min_turns=args.min_turns,
        max_turns=args.max_turns,
        max_parallel=args.max_parallel,
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
