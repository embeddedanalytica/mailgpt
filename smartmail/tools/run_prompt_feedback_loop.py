#!/usr/bin/env python3
"""Operator-friendly wrapper for the prompt feedback loop."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import List


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

from athlete_agent_bench_fixture import DEFAULT_BENCH_PATH
import prompt_feedback_aggregate
import prompt_feedback_loop
import prompt_pack_loader


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the prompt feedback loop from an existing live athlete sim run directory."
    )
    parser.add_argument(
        "--run-dir",
        required=True,
        help="Live athlete sim run directory containing attempt JSONL files.",
    )
    parser.add_argument(
        "--base-version",
        default=prompt_pack_loader.get_active_coach_reply_prompt_pack_version(),
        help="Base coach-reply prompt-pack version. Defaults to the currently active version.",
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Bench fixture for regression runs. Defaults to athlete_agent_bench.md.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional workflow output directory. Defaults to <run-dir>/prompt-feedback-loop.",
    )
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Optional scenario id filter; may be repeated.",
    )
    parser.add_argument(
        "--runs-per-scenario",
        type=int,
        default=1,
        help="Number of live runs per scenario for regression execution.",
    )
    parser.add_argument("--min-turns", type=int, default=100, help="Default minimum turns.")
    parser.add_argument("--max-turns", type=int, default=100, help="Default maximum turns.")
    parser.add_argument("--athlete-model", help="Optional athlete model override.")
    parser.add_argument("--judge-model", help="Optional judge model override.")
    parser.add_argument("--max-parallel", type=int, default=1, help="Maximum concurrent scenarios.")
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote automatically if the regression decision is promote.",
    )
    parser.add_argument(
        "--promoted-version",
        help="Required with --promote. Immutable version to create on promotion.",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Activate the promoted version after promotion. Requires --promote.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    run_dir = Path(args.run_dir).expanduser().resolve()
    if not run_dir.exists():
        print(f"run directory not found: {run_dir}", file=sys.stderr)
        return 1

    aggregate_path = run_dir / prompt_feedback_aggregate.DEFAULT_OUTPUT_NAME
    try:
        aggregate = prompt_feedback_aggregate.aggregate_feedback(run_dir)
        prompt_feedback_aggregate.write_aggregate(aggregate_path, aggregate)
    except (RuntimeError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    output_dir = (
        Path(args.output_dir).expanduser().resolve()
        if args.output_dir
        else run_dir / "prompt-feedback-loop"
    )

    workflow_args = [
        "--aggregate",
        str(aggregate_path),
        "--base-version",
        args.base_version,
        "--bench",
        str(Path(args.bench).expanduser().resolve()),
        "--output-dir",
        str(output_dir),
        "--runs-per-scenario",
        str(args.runs_per_scenario),
        "--min-turns",
        str(args.min_turns),
        "--max-turns",
        str(args.max_turns),
        "--max-parallel",
        str(args.max_parallel),
    ]
    for scenario in args.scenario:
        workflow_args.extend(["--scenario", scenario])
    if args.athlete_model:
        workflow_args.extend(["--athlete-model", args.athlete_model])
    if args.judge_model:
        workflow_args.extend(["--judge-model", args.judge_model])
    if args.promote:
        workflow_args.append("--promote")
        if not args.promoted_version:
            print("--promoted-version is required when --promote is set.", file=sys.stderr)
            return 1
        workflow_args.extend(["--promoted-version", args.promoted_version])
    if args.activate:
        if not args.promote:
            print("--activate requires --promote.", file=sys.stderr)
            return 1
        workflow_args.append("--activate")

    return prompt_feedback_loop.main(workflow_args)


if __name__ == "__main__":
    raise SystemExit(main())
