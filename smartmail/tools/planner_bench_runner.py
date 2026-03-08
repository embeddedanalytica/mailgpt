#!/usr/bin/env python3
"""Run live PlannerLLM benchmark scenarios loaded from a markdown fixture."""

from __future__ import annotations

import argparse
import json
import os
import sys
import traceback
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

from openai_responder import PlannerProposalError, PlanningLLM
from planner_bench_fixture import DEFAULT_BENCH_PATH, build_scenario_brief, load_plan_bench_scenarios
from rule_engine import repair_or_fallback_plan, validate_planner_output

DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "planner-bench"
OK_RAW_VALID = "ok_raw_valid"
OK_REPAIRED = "ok_repaired"
PLANNER_ERROR = "planner_error"
INVALID_RESPONSE_SHAPE = "invalid_response_shape"
EXCEPTION = "exception"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run planner benchmark scenarios through live PlanningLLM calls."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Path to planner benchmark markdown fixture.",
    )
    parser.add_argument(
        "--attempts",
        type=int,
        default=3,
        help="Number of attempts per scenario.",
    )
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent planner calls.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional output directory override for benchmark artifacts.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario id or name filter; may be repeated.",
    )
    parser.add_argument(
        "--model",
        help="Optional model override passed to PlanningLLM.propose_plan.",
    )
    return parser


def require_prerequisites(bench_path: Path) -> None:
    missing: list[str] = []
    if not bench_path.exists():
        missing.append(f"planner benchmark fixture not found: {bench_path}")
    if not os.getenv("OPENAI_API_KEY", "").strip():
        missing.append("OPENAI_API_KEY is required for live planner benchmark runs.")
    if missing:
        raise RuntimeError("\n".join(missing))
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
    filtered = [
        scenario
        for scenario in scenarios
        if str(scenario.get("id", "")).strip().lower() in wanted
        or str(scenario.get("name", "")).strip().lower() in wanted
    ]
    return filtered


def _as_clean_string_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        raise ValueError("weekly_skeleton must be a list")
    return [str(item).strip().lower() for item in value if str(item).strip()]


def run_single_attempt(
    *,
    scenario: dict[str, Any],
    attempt: int,
    model_name: str | None,
) -> dict[str, Any]:
    started_at = datetime.now(timezone.utc).isoformat()
    timer_start = perf_counter()
    planner_brief = build_scenario_brief(scenario)
    base_result: dict[str, Any] = {
        "scenario_id": scenario["id"],
        "scenario_name": scenario["name"],
        "attempt": attempt,
        "started_at": started_at,
        "model_name": model_name,
        "planner_brief": planner_brief,
        "required_goal_tokens": list(scenario.get("required_goal_tokens", [])),
    }
    try:
        planner_response = PlanningLLM.propose_plan(planner_brief, model_name=model_name)
        if not isinstance(planner_response, dict):
            raise ValueError("planner_response must be an object")
        plan_proposal = planner_response.get("plan_proposal")
        if not isinstance(plan_proposal, dict):
            raise ValueError("plan_proposal must be an object")
        weekly_skeleton = _as_clean_string_list(plan_proposal.get("weekly_skeleton", []))
        validation = validate_planner_output(
            planner_brief,
            {"weekly_skeleton": weekly_skeleton},
        )
        elapsed = round(perf_counter() - timer_start, 4)

        result: dict[str, Any] = {
            **base_result,
            "duration_seconds": elapsed,
            "planner_response": planner_response,
            "raw_plan_proposal": {"weekly_skeleton": weekly_skeleton},
            "validation": validation,
            "rationale": str(planner_response.get("rationale", "")).strip(),
            "non_binding_state_suggestions": list(
                planner_response.get("non_binding_state_suggestions", [])
            ),
            "repair_result": None,
            "status": OK_RAW_VALID,
            "error": None,
        }
        if not validation.get("is_valid", False):
            result["repair_result"] = repair_or_fallback_plan(validation, planner_brief)
            result["status"] = OK_REPAIRED
        return result
    except PlannerProposalError as exc:
        elapsed = round(perf_counter() - timer_start, 4)
        return {
            **base_result,
            "duration_seconds": elapsed,
            "status": PLANNER_ERROR,
            "planner_response": None,
            "raw_plan_proposal": None,
            "validation": None,
            "repair_result": None,
            "rationale": "",
            "non_binding_state_suggestions": [],
            "error": str(exc),
        }
    except ValueError as exc:
        elapsed = round(perf_counter() - timer_start, 4)
        return {
            **base_result,
            "duration_seconds": elapsed,
            "status": INVALID_RESPONSE_SHAPE,
            "planner_response": None,
            "raw_plan_proposal": None,
            "validation": None,
            "repair_result": None,
            "rationale": "",
            "non_binding_state_suggestions": [],
            "error": str(exc),
        }
    except Exception as exc:  # pragma: no cover - defensive runtime capture
        elapsed = round(perf_counter() - timer_start, 4)
        return {
            **base_result,
            "duration_seconds": elapsed,
            "status": EXCEPTION,
            "planner_response": None,
            "raw_plan_proposal": None,
            "validation": None,
            "repair_result": None,
            "rationale": "",
            "non_binding_state_suggestions": [],
            "error": f"{exc}\n{traceback.format_exc()}",
        }


def aggregate_results(
    *,
    scenarios: list[dict[str, Any]],
    runs: list[dict[str, Any]],
    attempts: int,
    max_parallel: int,
    bench_path: Path,
    output_dir: Path,
) -> dict[str, Any]:
    by_scenario: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        by_scenario[run["scenario_id"]].append(run)

    per_scenario: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_runs = sorted(
            by_scenario.get(scenario["id"], []),
            key=lambda item: item["attempt"],
        )
        raw_valid_runs = [run for run in scenario_runs if run["status"] == OK_RAW_VALID]
        repaired_runs = [run for run in scenario_runs if run["status"] == OK_REPAIRED]
        failed_runs = [
            run
            for run in scenario_runs
            if run["status"] not in {OK_RAW_VALID, OK_REPAIRED}
        ]
        valid_shapes = [
            tuple(run["raw_plan_proposal"]["weekly_skeleton"])
            for run in raw_valid_runs
        ]
        raw_shapes = [
            tuple(run["raw_plan_proposal"]["weekly_skeleton"])
            for run in scenario_runs
            if isinstance(run.get("raw_plan_proposal"), dict)
        ]
        most_common_valid_shape = None
        if valid_shapes:
            most_common_valid_shape = list(Counter(valid_shapes).most_common(1)[0][0])
        per_scenario.append(
            {
                "scenario_id": scenario["id"],
                "scenario_name": scenario["name"],
                "attempts": attempts,
                "raw_valid_count": len(raw_valid_runs),
                "raw_valid_rate": round(len(raw_valid_runs) / attempts, 4),
                "repaired_count": len(repaired_runs),
                "failed_count": len(failed_runs),
                "unique_raw_valid_skeleton_count": len(set(valid_shapes)),
                "unique_raw_skeleton_count": len(set(raw_shapes)),
                "diverse_valid_output": len(set(valid_shapes)) > 1,
                "most_common_valid_skeleton": most_common_valid_shape,
                "runs": scenario_runs,
            }
        )

    raw_valid_runs = [run for run in runs if run["status"] == OK_RAW_VALID]
    repaired_runs = [run for run in runs if run["status"] == OK_REPAIRED]
    failed_runs = [run for run in runs if run["status"] not in {OK_RAW_VALID, OK_REPAIRED}]
    scenarios_with_raw_valid = sum(1 for item in per_scenario if item["raw_valid_count"] > 0)
    scenarios_with_distinct_valid = sum(
        1 for item in per_scenario if item["unique_raw_valid_skeleton_count"] > 1
    )

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "benchmark_path": str(bench_path),
        "output_dir": str(output_dir),
        "attempts": attempts,
        "max_parallel": max_parallel,
        "total_scenarios": len(scenarios),
        "total_runs": len(runs),
        "raw_valid_runs": len(raw_valid_runs),
        "repaired_runs": len(repaired_runs),
        "failed_runs": len(failed_runs),
        "raw_valid_rate": round((len(raw_valid_runs) / len(runs)) if runs else 0.0, 4),
        "scenarios_with_raw_valid": scenarios_with_raw_valid,
        "scenarios_with_multiple_valid_shapes": scenarios_with_distinct_valid,
        "per_scenario": per_scenario,
        "runs": sorted(runs, key=lambda item: (item["scenario_id"], item["attempt"])),
    }


def write_summary(summary: dict[str, Any], summary_path: Path) -> None:
    low_diversity = [
        item
        for item in summary["per_scenario"]
        if item["raw_valid_count"] > 0 and item["unique_raw_valid_skeleton_count"] <= 1
    ]
    invalid_outputs = [
        run
        for run in summary["runs"]
        if run["status"] == OK_REPAIRED
        or run["status"] in {INVALID_RESPONSE_SHAPE, PLANNER_ERROR, EXCEPTION}
    ]

    lines = [
        "# Planner Benchmark Summary",
        "",
        f"- Generated at: `{summary['generated_at']}`",
        f"- Benchmark fixture: `{summary['benchmark_path']}`",
        f"- Output directory: `{summary['output_dir']}`",
        f"- Total scenarios: `{summary['total_scenarios']}`",
        f"- Total runs: `{summary['total_runs']}`",
        f"- Raw-valid runs: `{summary['raw_valid_runs']}`",
        f"- Repaired runs: `{summary['repaired_runs']}`",
        f"- Failed runs: `{summary['failed_runs']}`",
        f"- Raw-valid rate: `{summary['raw_valid_rate']:.2%}`",
        "",
        "## Per-Scenario Results",
        "",
        "| Scenario | Raw Valid | Repaired | Failed | Distinct Valid Shapes |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for item in summary["per_scenario"]:
        lines.append(
            f"| {item['scenario_id']} ({item['scenario_name']}) | "
            f"{item['raw_valid_count']}/{item['attempts']} | "
            f"{item['repaired_count']} | {item['failed_count']} | "
            f"{item['unique_raw_valid_skeleton_count']} |"
        )

    lines.extend(["", "## Low Diversity Scenarios", ""])
    if low_diversity:
        for item in low_diversity:
            lines.append(
                f"- `{item['scenario_id']}`: only {item['unique_raw_valid_skeleton_count']} "
                "distinct raw-valid shape."
            )
    else:
        lines.append("- None")

    lines.extend(["", "## Invalid Raw Outputs", ""])
    if invalid_outputs:
        for run in invalid_outputs:
            if run["status"] == OK_REPAIRED:
                lines.append(
                    f"- `{run['scenario_id']}` attempt `{run['attempt']}`: invalid raw output "
                    f"repaired via `{run['repair_result']['source']}` "
                    f"(errors: {run['validation']['errors']})"
                )
            else:
                lines.append(
                    f"- `{run['scenario_id']}` attempt `{run['attempt']}`: "
                    f"{run['status']} ({run.get('error', 'unknown error')})"
                )
    else:
        lines.append("- None")

    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def run_benchmark(
    *,
    scenarios: list[dict[str, Any]],
    attempts: int,
    max_parallel: int,
    output_dir: Path,
    bench_path: Path,
    model_name: str | None,
) -> dict[str, Any]:
    runs: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=max_parallel) as executor:
        futures = [
            executor.submit(
                run_single_attempt,
                scenario=scenario,
                attempt=attempt,
                model_name=model_name,
            )
            for scenario in scenarios
            for attempt in range(1, attempts + 1)
        ]
        for future in as_completed(futures):
            runs.append(future.result())

    summary = aggregate_results(
        scenarios=scenarios,
        runs=runs,
        attempts=attempts,
        max_parallel=max_parallel,
        bench_path=bench_path,
        output_dir=output_dir,
    )
    runs_path = output_dir / "runs.json"
    summary_path = output_dir / "summary.md"
    runs_path.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
    write_summary(summary, summary_path)
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.attempts < 1:
        print("--attempts must be >= 1.", file=sys.stderr)
        return 2
    if args.max_parallel < 1:
        print("--max-parallel must be >= 1.", file=sys.stderr)
        return 2

    bench_path = Path(args.bench).expanduser().resolve()
    try:
        require_prerequisites(bench_path)
        scenarios = load_plan_bench_scenarios(bench_path)
    except (RuntimeError, ValueError, OSError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    selected_scenarios = select_scenarios(scenarios, args.scenario)
    if not selected_scenarios:
        print("No scenarios matched --scenario filters.", file=sys.stderr)
        return 2

    output_dir = make_output_dir(args.output_dir)
    summary = run_benchmark(
        scenarios=selected_scenarios,
        attempts=args.attempts,
        max_parallel=args.max_parallel,
        output_dir=output_dir,
        bench_path=bench_path,
        model_name=args.model,
    )

    print(f"Planner benchmark completed. Artifacts written to {output_dir}")
    print(f"Raw-valid rate: {summary['raw_valid_rate']:.2%}")
    print(f"Scenarios with multiple valid shapes: {summary['scenarios_with_multiple_valid_shapes']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
