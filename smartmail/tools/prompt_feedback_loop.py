#!/usr/bin/env python3
"""Run the autonomous prompt feedback loop from baseline through summary."""

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

import prompt_feedback_aggregate
import prompt_pack_loader
import prompt_pack_promote
import prompt_patch_apply
import prompt_patch_proposer
import prompt_patch_regression


DEFAULT_OUTPUT_ROOT = REPO_ROOT / "sam-app" / ".cache" / "prompt-feedback-loop"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the autonomous prompt feedback loop from zero or from an existing aggregate."
    )
    parser.add_argument(
        "--bench",
        required=True,
        help="Bench fixture used for baseline and candidate live execution.",
    )
    parser.add_argument(
        "--aggregate",
        help="Optional existing baseline aggregate.json for resume/manual workflows.",
    )
    parser.add_argument(
        "--start-version",
        help="Starting coach-reply prompt-pack version. Defaults to the currently active version.",
    )
    parser.add_argument(
        "--base-version",
        dest="start_version_compat",
        help=argparse.SUPPRESS,
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
    parser.add_argument(
        "--min-turns",
        type=int,
        default=100,
        help="Default minimum turns for live execution.",
    )
    parser.add_argument(
        "--max-turns",
        type=int,
        default=100,
        help="Default maximum turns for live execution.",
    )
    parser.add_argument("--athlete-model", help="Optional athlete model override.")
    parser.add_argument("--judge-model", help="Optional judge model override.")
    parser.add_argument(
        "--max-parallel",
        type=int,
        default=1,
        help="Maximum concurrent scenarios during live execution.",
    )
    parser.add_argument(
        "--max-rounds",
        type=int,
        default=3,
        help="Maximum optimization rounds after the baseline run.",
    )
    parser.add_argument(
        "--output-dir",
        help="Optional workflow output directory; defaults to sam-app/.cache/prompt-feedback-loop/<timestamp>.",
    )
    parser.add_argument(
        "--auto-promote",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Promote winning candidates into immutable prompt-pack versions.",
    )
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Activate the final promoted version when the workflow finishes.",
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
        raise ValueError(f"prompt-pack version not found: {path}")
    return path


def _write_json(path: Path, payload: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _workflow_label(output_dir: Path) -> str:
    return output_dir.name.replace(":", "-")


def _candidate_version_name(*, baseline_version: str, round_number: int, workflow_label: str) -> str:
    return f"{baseline_version}-r{round_number}-candidate-{workflow_label}"


def _promoted_version_name(*, baseline_version: str, round_number: int, workflow_label: str) -> str:
    return f"{baseline_version}-r{round_number}-{workflow_label}"


def _run_live_suite(
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
    return prompt_patch_regression._run_live_suite_for_prompt_pack(
        prompt_pack_version=prompt_pack_version,
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


def _aggregate_run(run_dir: Path, aggregate_path: Path) -> Dict[str, Any]:
    aggregate = prompt_feedback_aggregate.aggregate_feedback(run_dir)
    prompt_feedback_aggregate.write_aggregate(aggregate_path, aggregate)
    return aggregate


def _copy_aggregate(source_path: Path, target_path: Path) -> Dict[str, Any]:
    aggregate = _load_json(source_path)
    _write_json(target_path, aggregate)
    return aggregate


def _build_proposal(
    *,
    aggregate_path: Path,
    base_version: str,
    candidate_version: str,
    output_path: Path,
) -> Dict[str, Any]:
    aggregate = prompt_patch_proposer._load_aggregate(aggregate_path)
    proposal = prompt_patch_proposer.build_proposal(aggregate, base_version=base_version)
    proposal["proposed_version"] = candidate_version
    prompt_patch_proposer.write_proposal(output_path, proposal)
    return proposal


def _apply_candidate(
    *,
    proposal_path: Path,
    base_version: str,
    candidate_version: str,
) -> Path:
    prompt_patch_apply.PROMPT_PACKS_ROOT = prompt_pack_loader.PROMPT_PACKS_ROOT
    return prompt_patch_apply.apply_proposal(
        proposal_path=proposal_path,
        base_version=base_version,
        output_version=candidate_version,
    )


def _run_regression(
    *,
    base_version: str,
    candidate_version: str,
    bench_path: Path,
    scenario_tokens: List[str],
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    athlete_model: str | None,
    judge_model: str | None,
    max_parallel: int,
    round_dir: Path,
) -> Dict[str, Any]:
    regression_args = [
        "--base-version",
        base_version,
        "--proposed-version",
        candidate_version,
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
        str(round_dir / "regression_runs"),
        "--output",
        str(round_dir / "regression-report.json"),
    ]
    for scenario in scenario_tokens:
        regression_args.extend(["--scenario", scenario])
    if athlete_model:
        regression_args.extend(["--athlete-model", athlete_model])
    if judge_model:
        regression_args.extend(["--judge-model", judge_model])

    exit_code = prompt_patch_regression.main(regression_args)
    if exit_code != 0:
        raise ValueError("regression workflow failed before producing a decision artifact.")
    return _load_json(round_dir / "regression-report.json")


def _promote_candidate(
    *,
    base_version: str,
    candidate_version: str,
    promoted_version: str,
    proposal_path: Path,
    regression_report_path: Path,
) -> Path:
    prompt_pack_promote.PROMPT_PACKS_ROOT = prompt_pack_loader.PROMPT_PACKS_ROOT
    return prompt_pack_promote.promote_prompt_pack(
        base_version=base_version,
        source_version=candidate_version,
        new_version=promoted_version,
        proposal_path=proposal_path,
        regression_report_path=regression_report_path,
        activate=False,
    )


def _activate_final_version(version: str) -> None:
    prompt_pack_promote.PROMPT_PACKS_ROOT = prompt_pack_loader.PROMPT_PACKS_ROOT
    prompt_pack_promote.set_active_prompt_pack_version(version)


def _round_record(*, round_number: int, baseline_version: str, round_dir: Path) -> Dict[str, Any]:
    return {
        "round": round_number,
        "baseline_version": baseline_version,
        "round_dir": str(round_dir),
    }


def run_workflow(
    *,
    bench_path: Path,
    aggregate_path: Path | None,
    start_version: str | None,
    scenario_tokens: List[str],
    runs_per_scenario: int,
    min_turns: int,
    max_turns: int,
    athlete_model: str | None,
    judge_model: str | None,
    max_parallel: int,
    max_rounds: int,
    output_dir: Path,
    auto_promote: bool,
    activate: bool,
) -> Dict[str, Any]:
    if max_rounds < 1:
        raise ValueError("--max-rounds must be at least 1.")
    if not bench_path.exists():
        raise ValueError(f"bench fixture not found: {bench_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    workflow_label = _workflow_label(output_dir)
    starting_version = start_version or prompt_pack_loader.get_active_coach_reply_prompt_pack_version()
    _require_prompt_pack_version(starting_version)

    summary: Dict[str, Any] = {
        "generated_at": _utc_now_iso(),
        "workflow_output_dir": str(output_dir),
        "bench": str(bench_path),
        "start_version": starting_version,
        "final_version": starting_version,
        "final_decision": "in_progress",
        "rounds_attempted": 0,
        "rounds_promoted": 0,
        "activated": False,
        "auto_promote": auto_promote,
        "max_rounds": max_rounds,
        "scenario_tokens": list(scenario_tokens),
        "runs_per_scenario": runs_per_scenario,
        "min_turns": min_turns,
        "max_turns": max_turns,
        "max_parallel": max_parallel,
        "athlete_model": athlete_model,
        "judge_model": judge_model,
        "rounds": [],
    }
    summary_path = output_dir / "workflow_summary.json"

    try:
        baseline_version = starting_version
        round_zero_dir = output_dir / "round-0"
        round_zero_dir.mkdir(parents=True, exist_ok=True)
        base_run_dir = round_zero_dir / "base-run"
        base_aggregate_path = round_zero_dir / "base-aggregate.json"
        round_zero = _round_record(round_number=0, baseline_version=baseline_version, round_dir=round_zero_dir)

        if aggregate_path is None:
            _run_live_suite(
                prompt_pack_version=baseline_version,
                bench_path=bench_path,
                scenario_tokens=scenario_tokens,
                runs_per_scenario=runs_per_scenario,
                min_turns=min_turns,
                max_turns=max_turns,
                athlete_model=athlete_model,
                judge_model=judge_model,
                max_parallel=max_parallel,
                output_dir=base_run_dir,
            )
            baseline_aggregate = _aggregate_run(base_run_dir, base_aggregate_path)
            round_zero["base_run_dir"] = str(base_run_dir)
        else:
            aggregate_path = aggregate_path.expanduser().resolve()
            if not aggregate_path.exists():
                raise ValueError(f"aggregate artifact not found: {aggregate_path}")
            baseline_aggregate = _copy_aggregate(aggregate_path, base_aggregate_path)
            round_zero["base_run_dir"] = None
            round_zero["resumed_from_aggregate"] = str(aggregate_path)

        round_zero["base_aggregate"] = str(base_aggregate_path)
        round_zero["judge_result_count"] = baseline_aggregate.get("judge_result_count")
        summary["rounds"].append(round_zero)

        current_baseline_aggregate_path = base_aggregate_path
        current_baseline_aggregate = baseline_aggregate

        for round_number in range(1, max_rounds + 1):
            round_dir = output_dir / f"round-{round_number}"
            round_dir.mkdir(parents=True, exist_ok=True)
            round_summary = _round_record(
                round_number=round_number,
                baseline_version=baseline_version,
                round_dir=round_dir,
            )
            current_round_base_aggregate_path = round_dir / "base-aggregate.json"
            _write_json(current_round_base_aggregate_path, current_baseline_aggregate)
            round_summary["base_aggregate"] = str(current_round_base_aggregate_path)

            candidate_version = _candidate_version_name(
                baseline_version=baseline_version,
                round_number=round_number,
                workflow_label=workflow_label,
            )
            proposal_path = round_dir / "proposal.json"
            proposal = _build_proposal(
                aggregate_path=current_baseline_aggregate_path,
                base_version=baseline_version,
                candidate_version=candidate_version,
                output_path=proposal_path,
            )
            round_summary["proposal_path"] = str(proposal_path)
            round_summary["proposal_change_count"] = len(proposal.get("changes", []))

            if not proposal.get("changes"):
                round_summary["decision"] = "stop"
                round_summary["stop_reason"] = "no_supported_changes"
                summary["rounds"].append(round_summary)
                summary["final_decision"] = "no_supported_changes"
                break

            candidate_dir = _apply_candidate(
                proposal_path=proposal_path,
                base_version=baseline_version,
                candidate_version=candidate_version,
            )
            candidate_pack_info = {
                "base_version": baseline_version,
                "candidate_version": candidate_version,
                "candidate_prompt_pack_dir": str(candidate_dir.resolve()),
                "proposal_path": str(proposal_path),
            }
            _write_json(round_dir / "candidate-pack-info.json", candidate_pack_info)
            round_summary["candidate_pack_info"] = str(round_dir / "candidate-pack-info.json")
            round_summary["candidate_version"] = candidate_version
            round_summary["candidate_prompt_pack_dir"] = str(candidate_dir.resolve())

            regression_report = _run_regression(
                base_version=baseline_version,
                candidate_version=candidate_version,
                bench_path=bench_path,
                scenario_tokens=scenario_tokens,
                runs_per_scenario=runs_per_scenario,
                min_turns=min_turns,
                max_turns=max_turns,
                athlete_model=athlete_model,
                judge_model=judge_model,
                max_parallel=max_parallel,
                round_dir=round_dir,
            )
            summary["rounds_attempted"] += 1
            round_summary["decision"] = regression_report.get("decision")
            round_summary["failed_gates"] = regression_report.get("failed_gates", [])
            round_summary["score_deltas"] = regression_report.get("score_deltas", {})
            round_summary["regression_report"] = str(round_dir / "regression-report.json")

            suite_runs = regression_report.get("suite_runs") or {}
            round_summary["candidate_run_dir"] = suite_runs.get("proposed_run_dir")
            round_summary["candidate_aggregate"] = suite_runs.get("proposed_aggregate")

            if regression_report.get("decision") != "promote":
                round_summary["stop_reason"] = "candidate_rejected"
                summary["rounds"].append(round_summary)
                summary["final_decision"] = "candidate_rejected"
                break

            if not auto_promote:
                round_summary["stop_reason"] = "candidate_won_auto_promote_disabled"
                summary["rounds"].append(round_summary)
                summary["final_decision"] = "candidate_won_not_promoted"
                summary["final_version"] = baseline_version
                break

            promoted_version = _promoted_version_name(
                baseline_version=baseline_version,
                round_number=round_number,
                workflow_label=workflow_label,
            )
            promoted_dir = _promote_candidate(
                base_version=baseline_version,
                candidate_version=candidate_version,
                promoted_version=promoted_version,
                proposal_path=proposal_path,
                regression_report_path=round_dir / "regression-report.json",
            )
            promotion_payload = {
                "base_version": baseline_version,
                "candidate_version": candidate_version,
                "promoted_version": promoted_version,
                "promoted_dir": str(promoted_dir.resolve()),
                "regression_report": str((round_dir / "regression-report.json").resolve()),
            }
            _write_json(round_dir / "promotion.json", promotion_payload)
            round_summary["promotion"] = str(round_dir / "promotion.json")
            round_summary["promoted_version"] = promoted_version
            round_summary["promoted_dir"] = str(promoted_dir.resolve())
            summary["rounds_promoted"] += 1
            summary["final_version"] = promoted_version
            summary["rounds"].append(round_summary)

            current_baseline_aggregate_path = Path(suite_runs["proposed_aggregate"]).resolve()
            current_baseline_aggregate = _load_json(current_baseline_aggregate_path)
            baseline_version = promoted_version

            if round_number == max_rounds:
                summary["final_decision"] = "max_rounds_reached"
        else:
            summary["final_decision"] = "max_rounds_reached"

        if (
            activate
            and auto_promote
            and summary["rounds_promoted"] > 0
            and summary["final_version"] != starting_version
        ):
            _activate_final_version(str(summary["final_version"]))
            summary["activated"] = True
        elif activate and summary["rounds_promoted"] == 0:
            summary["activated"] = False

        if summary["final_decision"] == "in_progress":
            summary["final_decision"] = "completed"
    except Exception as exc:
        summary["final_decision"] = "failed"
        summary["error"] = str(exc)
        _write_json(summary_path, summary)
        raise

    _write_json(summary_path, summary)
    summary["summary_path"] = str(summary_path)
    return summary


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    start_version = args.start_version or args.start_version_compat
    try:
        summary = run_workflow(
            bench_path=Path(args.bench).expanduser().resolve(),
            aggregate_path=Path(args.aggregate).expanduser().resolve() if args.aggregate else None,
            start_version=start_version,
            scenario_tokens=args.scenario,
            runs_per_scenario=args.runs_per_scenario,
            min_turns=args.min_turns,
            max_turns=args.max_turns,
            athlete_model=args.athlete_model,
            judge_model=args.judge_model,
            max_parallel=args.max_parallel,
            max_rounds=args.max_rounds,
            output_dir=(
                Path(args.output_dir).expanduser().resolve()
                if args.output_dir
                else _default_output_dir()
            ),
            auto_promote=bool(args.auto_promote),
            activate=bool(args.activate),
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"final_version={summary['final_version']} "
        f"decision={summary['final_decision']} "
        f"rounds_attempted={summary['rounds_attempted']} "
        f"rounds_promoted={summary['rounds_promoted']} "
        f"summary={summary['summary_path']}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
