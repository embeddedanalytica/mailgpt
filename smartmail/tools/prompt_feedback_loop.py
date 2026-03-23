#!/usr/bin/env python3
"""Run the prompt feedback loop from proposal through optional promotion."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

import prompt_pack_loader
import prompt_patch_apply
import prompt_pack_promote
import prompt_patch_proposer
import prompt_patch_regression


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "prompt-feedback-loop"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the prompt feedback loop from proposal through optional promotion."
    )
    parser.add_argument(
        "--aggregate",
        required=True,
        help="Path to aggregate.json used to generate or validate the proposal artifact.",
    )
    parser.add_argument(
        "--base-version",
        required=True,
        help="Base coach-reply prompt-pack version used for proposal and regression.",
    )
    parser.add_argument(
        "--proposal",
        help="Optional existing proposal.json. If omitted, a proposal artifact is generated into the workflow output directory.",
    )
    parser.add_argument(
        "--proposed-version",
        help="Prompt-pack version to regression-test as the candidate. Defaults to proposal.proposed_version.",
    )
    parser.add_argument(
        "--bench",
        required=True,
        help="Bench fixture used for real old-vs-new regression execution.",
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
        help="Number of live runs per scenario for regression execution.",
    )
    parser.add_argument(
        "--min-turns",
        type=int,
        default=100,
        help="Default minimum turns for live regression execution.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Default maximum turns for live regression execution.",
    )
    parser.add_argument("--athlete-model", help="Optional athlete model override.")
    parser.add_argument("--judge-model", help="Optional judge model override.")
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent scenarios during regression execution.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional workflow output directory; defaults to sam-app/.cache/prompt-feedback-loop/<timestamp>.",
    )
    parser.add_argument(
        "--promote",
        action="store_true",
        help="Promote the proposed prompt-pack version if the regression decision is promote.",
    )
    parser.add_argument(
        "--promoted-version",
        help="New immutable version name to create when --promote is set.",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Activate the promoted version after promotion. Requires --promote.",
    )
    return parser


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> Dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON at {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON object required at {path}")
    return payload


def _default_output_dir() -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return DEFAULT_OUTPUT_ROOT / timestamp


def _require_prompt_pack_version(version: str) -> Path:
    path = prompt_pack_loader.PROMPT_PACKS_ROOT / "coach_reply" / version
    if not path.exists():
        raise ValueError(
            f"prompt-pack version not found for regression: {version}. "
            f"Create or review {path} before running the closed-loop workflow."
        )
    return path


def _resolve_proposal(
    *,
    aggregate_path: Path,
    base_version: str,
    proposal_arg: str | None,
    output_dir: Path,
) -> tuple[Path, Dict[str, Any]]:
    if proposal_arg:
        proposal_path = Path(proposal_arg).expanduser().resolve()
        return proposal_path, _load_json(proposal_path)

    aggregate = prompt_patch_proposer._load_aggregate(aggregate_path)
    proposal = prompt_patch_proposer.build_proposal(aggregate, base_version=base_version)
    proposal_path = output_dir / "proposal.json"
    prompt_patch_proposer.write_proposal(proposal_path, proposal)
    return proposal_path, proposal


def _build_regression_args(
    *,
    base_version: str,
    proposed_version: str,
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
    arguments = [
        "--base-version",
        base_version,
        "--proposed-version",
        proposed_version,
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
        "--run-output-dir",
        str(output_dir / "regression_runs"),
        "--output",
        str(output_dir / "regression_report.json"),
    ]
    for scenario in scenario_tokens:
        arguments.extend(["--scenario", scenario])
    if athlete_model:
        arguments.extend(["--athlete-model", athlete_model])
    if judge_model:
        arguments.extend(["--judge-model", judge_model])
    return arguments


def run_workflow(
    *,
    aggregate_path: Path,
    base_version: str,
    proposal_arg: str | None,
    proposed_version_arg: str | None,
    bench_path: Path,
    scenario_tokens: List[str],
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    athlete_model: str | None,
    judge_model: str | None,
    max_parallel: int,
    output_dir: Path,
    promote: bool,
    promoted_version: str | None,
    activate: bool,
) -> Dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    proposal_path, proposal = _resolve_proposal(
        aggregate_path=aggregate_path,
        base_version=base_version,
        proposal_arg=proposal_arg,
        output_dir=output_dir,
    )
    proposed_version = proposed_version_arg or str(proposal.get("proposed_version") or "").strip()
    if not proposed_version:
        raise ValueError("proposed version is required either via --proposed-version or proposal.proposed_version.")

    _require_prompt_pack_version(base_version)
    proposed_version_path = prompt_pack_loader.PROMPT_PACKS_ROOT / "coach_reply" / proposed_version
    if not proposed_version_path.exists():
        prompt_patch_apply.PROMPT_PACKS_ROOT = prompt_pack_loader.PROMPT_PACKS_ROOT
        prompt_patch_apply.apply_proposal(
            proposal_path=proposal_path,
            base_version=base_version,
            output_version=proposed_version,
        )
    _require_prompt_pack_version(proposed_version)

    regression_args = _build_regression_args(
        base_version=base_version,
        proposed_version=proposed_version,
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
    regression_exit_code = prompt_patch_regression.main(regression_args)
    regression_report_path = output_dir / "regression_report.json"
    if regression_exit_code != 0:
        raise ValueError("regression workflow failed before producing a passing or rejecting decision artifact.")
    regression_report = _load_json(regression_report_path)

    promoted_dir: Path | None = None
    if promote:
        if not promoted_version:
            raise ValueError("--promoted-version is required when --promote is set.")
        if regression_report.get("decision") != "promote":
            raise ValueError("regression decision was not 'promote'; promotion is blocked.")
        promoted_dir = prompt_pack_promote.promote_prompt_pack(
            base_version=base_version,
            source_version=proposed_version,
            new_version=promoted_version,
            proposal_path=proposal_path,
            regression_report_path=regression_report_path,
            activate=activate,
        )
    elif activate:
        raise ValueError("--activate requires --promote.")

    summary = {
        "generated_at": _utc_now_iso(),
        "aggregate": str(aggregate_path),
        "base_version": base_version,
        "proposal_path": str(proposal_path),
        "proposed_version": proposed_version,
        "candidate_prompt_pack_dir": str(
            (prompt_pack_loader.PROMPT_PACKS_ROOT / "coach_reply" / proposed_version).resolve()
        ),
        "regression_report": str(regression_report_path),
        "regression_decision": regression_report.get("decision"),
        "promoted_version": promoted_version if promoted_dir is not None else None,
        "promoted_dir": str(promoted_dir) if promoted_dir is not None else None,
        "activated": bool(promoted_dir is not None and activate),
    }
    summary_path = output_dir / "workflow_summary.json"
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    summary["summary_path"] = str(summary_path)
    return summary


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_workflow(
            aggregate_path=Path(args.aggregate).expanduser().resolve(),
            base_version=args.base_version,
            proposal_arg=args.proposal,
            proposed_version_arg=args.proposed_version,
            bench_path=Path(args.bench).expanduser().resolve(),
            scenario_tokens=args.scenario,
            runs_per_scenario=args.runs_per_scenario,
            min_turns=args.min_turns,
            max_turns=args.max_turns,
            athlete_model=args.athlete_model,
            judge_model=args.judge_model,
            max_parallel=args.max_parallel,
            output_dir=(
                Path(args.output_dir).expanduser().resolve()
                if args.output_dir
                else _default_output_dir()
            ),
            promote=bool(args.promote),
            promoted_version=args.promoted_version,
            activate=bool(args.activate),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"decision={summary['regression_decision']} "
        f"proposal={summary['proposal_path']} "
        f"regression={summary['regression_report']} "
        f"promoted={summary['promoted_version'] or 'none'}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
