#!/usr/bin/env python3
"""One-command entrypoint for the autonomous prompt feedback loop."""

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
import prompt_feedback_loop


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the true one-command autonomous prompt feedback loop."
    )
    parser.add_argument(
        "--bench",
        default=str(DEFAULT_BENCH_PATH),
        help="Bench fixture used for baseline and candidate live execution.",
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
        help="Number of live runs per scenario.",
    )
    parser.add_argument("--min-turns", type=int, default=100, help="Default minimum turns.")
    parser.add_argument("--max-turns", type=int, default=100, help="Default maximum turns.")
    parser.add_argument("--max-parallel", type=int, default=1, help="Maximum concurrent scenarios.")
    parser.add_argument("--max-rounds", type=int, default=3, help="Maximum optimization rounds.")
    parser.add_argument("--athlete-model", help="Optional athlete model override.")
    parser.add_argument("--judge-model", help="Optional judge model override.")
    parser.add_argument(
        "--start-version",
        help="Starting coach-reply prompt-pack version. Defaults to the active version.",
    )
    parser.add_argument(
        "--auto-promote",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Promote winning candidates automatically.",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Activate the final promoted version after the workflow completes.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional workflow output directory; defaults to sam-app/.cache/prompt-feedback-loop/<timestamp>.",
    )
    return parser


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    workflow_args = [
        "--bench",
        str(Path(args.bench).expanduser().resolve()),
        "--runs-per-scenario",
        str(args.runs_per_scenario),
        "--min-turns",
        str(args.min_turns),
        "--max-turns",
        str(args.max_turns),
        "--max-parallel",
        str(args.max_parallel),
        "--max-rounds",
        str(args.max_rounds),
    ]
    for scenario in args.scenario:
        workflow_args.extend(["--scenario", scenario])
    if args.athlete_model:
        workflow_args.extend(["--athlete-model", args.athlete_model])
    if args.judge_model:
        workflow_args.extend(["--judge-model", args.judge_model])
    if args.start_version:
        workflow_args.extend(["--start-version", args.start_version])
    if args.output_dir:
        workflow_args.extend(["--output-dir", str(Path(args.output_dir).expanduser().resolve())])
    if args.auto_promote:
        workflow_args.append("--auto-promote")
    else:
        workflow_args.append("--no-auto-promote")
    if args.activate:
        workflow_args.append("--activate")

    return prompt_feedback_loop.main(workflow_args)


if __name__ == "__main__":
    raise SystemExit(main())
