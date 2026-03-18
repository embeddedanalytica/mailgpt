#!/usr/bin/env python3
"""Run response-generation benchmark scenarios through live LLM calls."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

from response_generation_bench_fixture import (  # noqa: E402
    DEFAULT_BENCH_PATH,
    load_response_generation_bench_scenarios,
)
from skills.response_generation import (  # noqa: E402
    ResponseGenerationProposalError,
    run_response_generation_workflow,
)


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "response-generation-bench"
OK = "ok"
ERROR = "error"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run response-generation benchmark scenarios through live response generation calls."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Path to response-generation benchmark markdown fixture.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario id or name filter; may be repeated.",
    )
    parser.add_argument(
        "--runs-per-scenario",
        type=int,
        default=2,
        help="Number of independent runs per scenario.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent response-generation calls.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override passed to response generation workflow.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for benchmark artifacts.",
    )
    return parser


def require_prerequisites(bench_path: Path, *, max_parallel: int, runs_per_scenario: int) -> None:
    missing: list[str] = []
    if not bench_path.exists():
        missing.append(f"response-generation benchmark fixture not found: {bench_path}")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        missing.append("OPENAI_API_KEY is required for live response-generation benchmark runs.")
    if missing:
        raise RuntimeError("\n".join(missing))
    if max_parallel < 1:
        raise RuntimeError("--max-parallel must be at least 1.")
    if runs_per_scenario < 1:
        raise RuntimeError("--runs-per-scenario must be at least 1.")
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
    scenarios: list[dict[str, Any]],
    selected_tokens: list[str],
) -> list[dict[str, Any]]:
    if not selected_tokens:
        return list(scenarios)
    wanted = {token.strip().lower() for token in selected_tokens if token.strip()}
    return [
        scenario
        for scenario in scenarios
        if str(scenario.get("id", "")).strip().lower() in wanted
        or str(scenario.get("name", "")).strip().lower() in wanted
    ]


def _non_empty_lines_count(text: str) -> int:
    return len([line for line in text.splitlines() if line.strip()])


def run_single_attempt(
    *,
    scenario: dict[str, Any],
    attempt: int,
    model_name: str | None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    timer_start = perf_counter()
    base = {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "attempt": attempt,
        "started_at": started_at,
        "model_name": model_name,
        "review_focus": list(scenario.get("review_focus", [])),
        "notes": scenario.get("notes"),
    }

    try:
        actual = run_response_generation_workflow(
            dict(scenario["response_brief"]),
            model_name=model_name,
        )
        final_email_body = str(actual.get("final_email_body", "") or "")
        ended_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = round(perf_counter() - timer_start, 4)
        return {
            **base,
            "status": OK,
            "error": None,
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "final_email_body": final_email_body,
            "line_count": _non_empty_lines_count(final_email_body),
            "char_count": len(final_email_body),
            "response_payload": actual,
        }
    except ResponseGenerationProposalError as exc:
        ended_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = round(perf_counter() - timer_start, 4)
        return {
            **base,
            "status": ERROR,
            "error": str(exc),
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "final_email_body": "",
            "line_count": 0,
            "char_count": 0,
            "response_payload": None,
        }
    except Exception as exc:  # pragma: no cover - defensive runtime capture
        ended_at = datetime.now(timezone.utc).isoformat()
        duration_seconds = round(perf_counter() - timer_start, 4)
        return {
            **base,
            "status": ERROR,
            "error": f"{exc}\n{traceback.format_exc()}",
            "ended_at": ended_at,
            "duration_seconds": duration_seconds,
            "final_email_body": "",
            "line_count": 0,
            "char_count": 0,
            "response_payload": None,
        }


def aggregate_results(
    *,
    scenarios: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    runs_per_scenario: int,
    max_parallel: int,
    bench_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    runs_sorted = sorted(runs, key=lambda item: (item["scenario_id"], item["attempt"]))
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs_sorted:
        by_scenario[run["scenario_id"]].append(run)

    per_scenario = []
    for scenario in scenarios:
        scenario_runs = by_scenario.get(scenario["id"], [])
        ok_runs = [run for run in scenario_runs if run["status"] == OK]
        error_runs = [run for run in scenario_runs if run["status"] == ERROR]
        avg_chars = (
            round(sum(run["char_count"] for run in ok_runs) / len(ok_runs), 2)
            if ok_runs
            else 0.0
        )
        avg_lines = (
            round(sum(run["line_count"] for run in ok_runs) / len(ok_runs), 2)
            if ok_runs
            else 0.0
        )
        per_scenario.append(
            {
                "scenario_id": scenario["id"],
                "scenario_name": scenario["name"],
                "runs_per_scenario": runs_per_scenario,
                "ok_runs": len(ok_runs),
                "error_runs": len(error_runs),
                "avg_char_count_ok_runs": avg_chars,
                "avg_line_count_ok_runs": avg_lines,
            }
        )

    ok_runs = [run for run in runs_sorted if run["status"] == OK]
    error_runs = [run for run in runs_sorted if run["status"] == ERROR]
    avg_duration = (
        round(sum(float(run["duration_seconds"]) for run in runs_sorted) / len(runs_sorted), 4)
        if runs_sorted
        else 0.0
    )
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": str(bench_path),
        "output_dir": str(output_dir),
        "runs_per_scenario": runs_per_scenario,
        "max_parallel": max_parallel,
        "total_scenarios": len(scenarios),
        "total_runs": len(runs_sorted),
        "ok_runs": len(ok_runs),
        "error_runs": len(error_runs),
        "avg_duration_seconds": avg_duration,
        "per_scenario": per_scenario,
        "runs": runs_sorted,
    }


def write_results_json(summary: dict[str, Any], path: Path) -> None:
    path.write_text(json.dumps(summary, indent=2), encoding="utf-8")


def _preview(text: str, *, max_len: int = 220) -> str:
    normalized = " ".join(str(text or "").split())
    if len(normalized) <= max_len:
        return normalized
    return normalized[: max_len - 3] + "..."


def write_summary_markdown(summary: dict[str, Any], path: Path) -> None:
    lines = [
        "# Response Generation Benchmark Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Benchmark fixture: `{summary['benchmark_path']}`",
        f"- Output directory: `{summary['output_dir']}`",
        f"- Total scenarios: `{summary['total_scenarios']}`",
        f"- Total runs: `{summary['total_runs']}`",
        f"- Successful runs: `{summary['ok_runs']}`",
        f"- Failed runs: `{summary['error_runs']}`",
        f"- Average duration (s): `{summary['avg_duration_seconds']}`",
        "",
        "## Per-Scenario Status",
        "",
        "| Scenario | Success | Failed | Avg chars (ok runs) | Avg lines (ok runs) |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["per_scenario"]:
        lines.append(
            f"| {item['scenario_id']} ({item['scenario_name']}) | "
            f"{item['ok_runs']}/{item['runs_per_scenario']} | "
            f"{item['error_runs']} | "
            f"{item['avg_char_count_ok_runs']} | "
            f"{item['avg_line_count_ok_runs']} |"
        )

    lines.extend(["", "## Run Outcomes", ""])
    for run in summary["runs"]:
        lines.append(
            f"### {run['scenario_id']} attempt {run['attempt']} ({run['status']})"
        )
        lines.append(
            f"- Duration (s): `{run['duration_seconds']}`"
        )
        lines.append(f"- Char count: `{run['char_count']}`")
        lines.append(f"- Non-empty lines: `{run['line_count']}`")
        if run.get("review_focus"):
            lines.append(
                "- Review focus: " + "; ".join(str(item) for item in run["review_focus"])
            )
        if run.get("notes"):
            lines.append(f"- Notes: {run['notes']}")
        if run["status"] == OK:
            lines.append(f"- Preview: {_preview(run['final_email_body'])}")
        else:
            lines.append(f"- Error: {_preview(run.get('error', ''), max_len=300)}")
        lines.append("")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    bench_path = Path(args.bench).expanduser().resolve()
    require_prerequisites(
        bench_path,
        max_parallel=args.max_parallel,
        runs_per_scenario=args.runs_per_scenario,
    )

    scenarios = load_response_generation_bench_scenarios(bench_path)
    selected = select_scenarios(scenarios, args.scenario)
    if not selected:
        raise RuntimeError("No scenarios matched --scenario filters.")

    output_dir = make_output_dir(args.output_dir)
    runs: list[dict[str, Any]] = []

    jobs = [
        (scenario, attempt)
        for scenario in selected
        for attempt in range(1, args.runs_per_scenario + 1)
    ]
    with ThreadPoolExecutor(max_workers=args.max_parallel) as executor:
        future_map = {
            executor.submit(
                run_single_attempt,
                scenario=scenario,
                attempt=attempt,
                model_name=args.model,
            ): (scenario["id"], attempt)
            for scenario, attempt in jobs
        }
        for future in as_completed(future_map):
            runs.append(future.result())

    summary = aggregate_results(
        scenarios=selected,
        runs=runs,
        runs_per_scenario=args.runs_per_scenario,
        max_parallel=args.max_parallel,
        bench_path=bench_path,
        output_dir=output_dir,
    )

    results_path = output_dir / "results.json"
    summary_path = output_dir / "summary.md"
    write_results_json(summary, results_path)
    write_summary_markdown(summary, summary_path)

    print(f"Response-generation benchmark complete: {summary['total_runs']} runs")
    print(f"Results JSON: {results_path}")
    print(f"Summary markdown: {summary_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
