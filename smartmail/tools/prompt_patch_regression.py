#!/usr/bin/env python3
"""Compare base and proposed prompt-pack versions and emit a regression decision."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

REPO_ROOT = Path(__file__).resolve().parents[1]
LIVE_RUNNER_PATH = REPO_ROOT / "tools" / "live_athlete_sim_runner.py"

import prompt_feedback_aggregate


DEFAULT_OUTPUT_NAME = "regression_report.json"
DEFAULT_REGRESSION_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "prompt-regression"
PROTECTED_DIMENSIONS = ("memory_continuity", "tone_trust")
PROTECTED_DIMENSION_MAX_DROP = 0.05
SCORE_FIELDS = (
    "understanding",
    "memory_continuity",
    "personalization",
    "coaching_quality",
    "tone_trust",
    "safety",
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compare base and proposed prompt-pack versions and emit a regression decision."
    )
    parser.add_argument("--base-version", required=True, help="Base prompt-pack version label.")
    parser.add_argument("--proposed-version", required=True, help="Proposed prompt-pack version label.")
    parser.add_argument("--base-aggregate", help="Path to base aggregate.json.")
    parser.add_argument("--proposed-aggregate", help="Path to proposed aggregate.json.")
    parser.add_argument(
        "--bench",
        help="Run the live regression workflow against this bench fixture instead of precomputed aggregates.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario id filter for live regression runs; may be repeated.",
    )
    parser.add_argument(
        "--runs-per-scenario",
        type=int,
        default=1,
        help="Number of independent live runs per scenario when using --bench.",
    )
    parser.add_argument(
        "--min-turns",
        type=int,
        default=100,
        help="Default minimum turns for live regression runs when using --bench.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Default maximum turns for live regression runs when using --bench.",
    )
    parser.add_argument("--athlete-model", help="Optional athlete-model override for live regression runs.")
    parser.add_argument("--judge-model", help="Optional judge-model override for live regression runs.")
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent scenarios for live regression runs when using --bench.",
    )
    parser.add_argument(
        "--run-output-dir",
        help=(
            "Optional output root for live regression runs; defaults to "
            "sam-app/.cache/prompt-regression/<timestamp>."
        ),
    )
    parser.add_argument(
        "--output",
        help=(
            "Optional output path override; defaults to regression_report.json next to the proposed aggregate "
            "or inside the live regression output root."
        ),
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_aggregate(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"aggregate artifact invalid JSON: {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError("aggregate artifact must be a JSON object.")
    average_scores = payload.get("average_scores")
    if not isinstance(average_scores, dict):
        raise ValueError("aggregate artifact missing average_scores.")
    for field in SCORE_FIELDS:
        value = average_scores.get(field)
        if not isinstance(value, (int, float)):
            raise ValueError(f"aggregate artifact missing numeric average_scores.{field}.")
    return payload


def _build_live_runner_command(
    *,
    bench_path: Path,
    scenario_tokens: List[str],
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    athlete_model: str | None,
    judge_model: str | None,
    max_parallel: int,
    output_dir: Path,
) -> List[str]:
    command = [
        sys.executable,
        str(LIVE_RUNNER_PATH),
        "--bench",
        str(bench_path),
        "--runs-per-scenario",
        str(runs_per_scenario),
        "--min-turns",
        str(min_turns),
        "--max-turns",
        str(max_turns),
        "--max-parallel",
        str(max_parallel),
        "--output-dir",
        str(output_dir),
    ]
    for scenario in scenario_tokens:
        command.extend(["--scenario", scenario])
    if athlete_model:
        command.extend(["--athlete-model", athlete_model])
    if judge_model:
        command.extend(["--judge-model", judge_model])
    return command


def _run_live_suite_for_prompt_pack(
    *,
    prompt_pack_version: str,
    bench_path: Path,
    scenario_tokens: List[str],
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    athlete_model: str | None,
    judge_model: str | None,
    max_parallel: int,
    output_dir: Path,
) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env["COACH_REPLY_PROMPT_PACK_VERSION"] = prompt_pack_version
    command = _build_live_runner_command(
        bench_path=bench_path,
        scenario_tokens=scenario_tokens,
        runs_per_scenario=runs_per_scenario,
        min_turns=min_turns,
        max_turns=max_turns,
        athlete_model=athlete_model,
        judge_model=judge_model,
        max_parallel=max_parallel,
        output_dir=output_dir,
    )
    result = subprocess.run(command, env=env, text=True, capture_output=True)
    if result.returncode != 0:
        detail = result.stderr.strip() or result.stdout.strip() or f"exit={result.returncode}"
        raise ValueError(
            f"live regression runner failed for prompt-pack {prompt_pack_version!r}: {detail}"
        )
    return output_dir


def _aggregate_run_dir(run_dir: Path) -> Path:
    aggregate_path = run_dir / prompt_feedback_aggregate.DEFAULT_OUTPUT_NAME
    aggregate = prompt_feedback_aggregate.aggregate_feedback(run_dir)
    prompt_feedback_aggregate.write_aggregate(aggregate_path, aggregate)
    return aggregate_path


def _default_live_output_root() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_REGRESSION_OUTPUT_ROOT / timestamp


def _prepare_live_aggregates(args: argparse.Namespace) -> tuple[Path, Path, Path]:
    bench_path = Path(args.bench).expanduser().resolve()
    if not bench_path.exists():
        raise ValueError(f"bench fixture not found: {bench_path}")

    output_root = (
        Path(args.run_output_dir).expanduser().resolve()
        if args.run_output_dir
        else _default_live_output_root()
    )
    base_run_dir = output_root / f"base-{args.base_version}"
    proposed_run_dir = output_root / f"proposed-{args.proposed_version}"

    _run_live_suite_for_prompt_pack(
        prompt_pack_version=args.base_version,
        bench_path=bench_path,
        scenario_tokens=args.scenario,
        runs_per_scenario=args.runs_per_scenario,
        min_turns=args.min_turns,
        max_turns=args.max_turns,
        athlete_model=args.athlete_model,
        judge_model=args.judge_model,
        max_parallel=args.max_parallel,
        output_dir=base_run_dir,
    )
    _run_live_suite_for_prompt_pack(
        prompt_pack_version=args.proposed_version,
        bench_path=bench_path,
        scenario_tokens=args.scenario,
        runs_per_scenario=args.runs_per_scenario,
        min_turns=args.min_turns,
        max_turns=args.max_turns,
        athlete_model=args.athlete_model,
        judge_model=args.judge_model,
        max_parallel=args.max_parallel,
        output_dir=proposed_run_dir,
    )
    return _aggregate_run_dir(base_run_dir), _aggregate_run_dir(proposed_run_dir), output_root


def _resolve_aggregate_inputs(args: argparse.Namespace) -> tuple[Path, Path, Path | None]:
    if args.base_aggregate or args.proposed_aggregate:
        if not (args.base_aggregate and args.proposed_aggregate):
            raise ValueError("--base-aggregate and --proposed-aggregate must be provided together.")
        return (
            Path(args.base_aggregate).expanduser().resolve(),
            Path(args.proposed_aggregate).expanduser().resolve(),
            None,
        )
    if args.bench:
        return _prepare_live_aggregates(args)
    raise ValueError(
        "provide either --base-aggregate/--proposed-aggregate or --bench to run live regression."
    )


def _overall_average(average_scores: Dict[str, Any]) -> float:
    return round(sum(float(average_scores[field]) for field in SCORE_FIELDS) / len(SCORE_FIELDS), 3)


def build_regression_report(
    *,
    base_aggregate: Dict[str, Any],
    proposed_aggregate: Dict[str, Any],
    base_version: str,
    proposed_version: str,
) -> Dict[str, Any]:
    base_scores = base_aggregate["average_scores"]
    proposed_scores = proposed_aggregate["average_scores"]
    score_deltas = {
        field: round(float(proposed_scores[field]) - float(base_scores[field]), 3)
        for field in SCORE_FIELDS
    }
    base_overall = _overall_average(base_scores)
    proposed_overall = _overall_average(proposed_scores)
    overall_delta = round(proposed_overall - base_overall, 3)

    failed_gates: List[str] = []
    if overall_delta <= 0:
        failed_gates.append("average_score_not_improved")
    if score_deltas["safety"] < 0:
        failed_gates.append("safety_regressed")
    for field in PROTECTED_DIMENSIONS:
        if score_deltas[field] < -PROTECTED_DIMENSION_MAX_DROP:
            failed_gates.append(f"{field}_regressed")

    decision = "promote" if not failed_gates else "reject"

    return {
        "generated_at": _utc_now_iso(),
        "base_version": base_version,
        "proposed_version": proposed_version,
        "decision": decision,
        "failed_gates": failed_gates,
        "gates": {
            "average_score_must_improve": True,
            "safety_must_not_decline": True,
            "protected_dimensions": list(PROTECTED_DIMENSIONS),
            "protected_dimension_max_drop": PROTECTED_DIMENSION_MAX_DROP,
        },
        "base_metrics": {
            "run_id": base_aggregate.get("run_id"),
            "judge_result_count": base_aggregate.get("judge_result_count"),
            "average_scores": base_scores,
            "overall_average_score": base_overall,
            "issue_tag_counts": base_aggregate.get("issue_tag_counts", {}),
            "strength_tag_counts": base_aggregate.get("strength_tag_counts", {}),
        },
        "proposed_metrics": {
            "run_id": proposed_aggregate.get("run_id"),
            "judge_result_count": proposed_aggregate.get("judge_result_count"),
            "average_scores": proposed_scores,
            "overall_average_score": proposed_overall,
            "issue_tag_counts": proposed_aggregate.get("issue_tag_counts", {}),
            "strength_tag_counts": proposed_aggregate.get("strength_tag_counts", {}),
        },
        "score_deltas": {
            **score_deltas,
            "overall_average_score": overall_delta,
        },
    }


def write_report(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        base_path, proposed_path, live_output_root = _resolve_aggregate_inputs(args)
        default_output_path = (
            Path(args.output).expanduser().resolve()
            if args.output
            else (
                proposed_path.with_name(DEFAULT_OUTPUT_NAME)
                if live_output_root is None
                else live_output_root / DEFAULT_OUTPUT_NAME
            )
        )
        output_path = default_output_path
        base_aggregate = _load_aggregate(base_path)
        proposed_aggregate = _load_aggregate(proposed_path)
        report = build_regression_report(
            base_aggregate=base_aggregate,
            proposed_aggregate=proposed_aggregate,
            base_version=args.base_version,
            proposed_version=args.proposed_version,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if live_output_root is not None:
        report["suite_runs"] = {
            "output_root": str(live_output_root),
            "base_run_dir": str(base_path.parent),
            "proposed_run_dir": str(proposed_path.parent),
            "base_aggregate": str(base_path),
            "proposed_aggregate": str(proposed_path),
        }
    write_report(output_path, report)
    print(
        f"decision={report['decision']} "
        f"failed_gates={','.join(report['failed_gates']) or 'none'} "
        f"output={output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
