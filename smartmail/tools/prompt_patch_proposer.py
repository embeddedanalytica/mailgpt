#!/usr/bin/env python3
"""Generate a structured prompt-change proposal from aggregated feedback."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
import sys

if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

from prompt_pack_loader import PromptPackError, load_coach_reply_prompt_pack


DEFAULT_OUTPUT_NAME = "proposal.json"
ALLOWED_SURFACES = {
    "response_generation.directive_system_prompt",
    "coaching_reasoning.base_prompt",
}
ISSUE_STRATEGIES = {
    "generic_reply": {
        "target_surface": "response_generation.directive_system_prompt",
        "patch_strategy": (
            "Add or strengthen instructions that force concrete athlete-specific references "
            "and prohibit generic filler phrasing."
        ),
        "expected_benefit": "Reduce generic responses and improve perceived specificity.",
    },
    "hallucinated_context": {
        "target_surface": "response_generation.directive_system_prompt",
        "patch_strategy": (
            "Strengthen the authority split around visible thread facts and memory context "
            "so the model does not invent athlete history or unsupported constraints."
        ),
        "expected_benefit": "Reduce invented context and improve trustworthiness.",
    },
    "missed_continuity": {
        "target_surface": "response_generation.directive_system_prompt",
        "patch_strategy": (
            "Emphasize continuity handling and near-term open loops so the reply carries forward "
            "relevant prior context when the athlete has not already resolved it."
        ),
        "expected_benefit": "Improve memory continuity and thread coherence.",
    },
    "missed_fact": {
        "target_surface": "response_generation.directive_system_prompt",
        "patch_strategy": (
            "Reinforce use of high-salience memory facts and current-message constraints when they "
            "materially affect this week's coaching guidance."
        ),
        "expected_benefit": "Reduce omissions of disclosed athlete facts.",
    },
    "too_vague": {
        "target_surface": "response_generation.directive_system_prompt",
        "patch_strategy": (
            "Require more concrete session guidance, clearer action language, and fewer abstract "
            "coaching generalities."
        ),
        "expected_benefit": "Increase coaching specificity and actionability.",
    },
    "unclear_priority": {
        "target_surface": "coaching_reasoning.base_prompt",
        "patch_strategy": (
            "Strengthen prioritization guidance so the strategist clearly decides the main point "
            "and the writer presents one obvious next step."
        ),
        "expected_benefit": "Improve reply focus and decision clarity.",
    },
    "unsafe_push": {
        "target_surface": "coaching_reasoning.base_prompt",
        "patch_strategy": (
            "Tighten caution language for fragile or elevated-risk states and make conservative "
            "load control instructions more explicit."
        ),
        "expected_benefit": "Preserve or improve safety behavior.",
    },
    "weak_guidance": {
        "target_surface": "coaching_reasoning.base_prompt",
        "patch_strategy": (
            "Push the strategist toward clearer session intent, load progression rationale, and "
            "more decisive coaching direction."
        ),
        "expected_benefit": "Improve coaching quality and usefulness.",
    },
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate a deterministic prompt-change proposal from aggregate feedback."
    )
    parser.add_argument(
        "--aggregate",
        required=True,
        help="Path to aggregate.json produced by prompt_feedback_aggregate.py.",
    )
    parser.add_argument(
        "--base-version",
        default="v1",
        help="Base coach-reply prompt-pack version to propose against.",
    )
    parser.add_argument(
        "--output",
        help="Optional output path override; defaults to proposal.json next to the aggregate artifact.",
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
    if not isinstance(payload.get("issue_tag_counts"), dict):
        raise ValueError("aggregate artifact missing issue_tag_counts.")
    if not isinstance(payload.get("examples"), list):
        raise ValueError("aggregate artifact missing examples.")
    return payload


def _example_refs_for_tag(aggregate: Dict[str, Any], issue_tag: str, *, limit: int = 3) -> List[Dict[str, Any]]:
    refs: List[Dict[str, Any]] = []
    for item in aggregate.get("examples", []):
        if not isinstance(item, dict):
            continue
        if issue_tag not in item.get("issue_tags", []):
            continue
        refs.append(
            {
                "scenario_id": item.get("scenario_id"),
                "scenario_name": item.get("scenario_name"),
                "attempt": item.get("attempt"),
                "turn": item.get("turn"),
                "headline": item.get("headline"),
                "what_missed": item.get("what_missed", []),
                "improved_reply_example": item.get("improved_reply_example"),
            }
        )
        if len(refs) >= limit:
            break
    return refs


def build_proposal(aggregate: Dict[str, Any], *, base_version: str) -> Dict[str, Any]:
    prompt_pack = load_coach_reply_prompt_pack(version=base_version)
    issue_tag_counts = aggregate.get("issue_tag_counts", {})
    changes = []

    for issue_tag in sorted(issue_tag_counts):
        if issue_tag not in ISSUE_STRATEGIES:
            continue
        count = int(issue_tag_counts[issue_tag] or 0)
        if count < 1:
            continue
        strategy = ISSUE_STRATEGIES[issue_tag]
        target_surface = strategy["target_surface"]
        if target_surface not in ALLOWED_SURFACES:
            raise ValueError(f"unsupported proposal target surface: {target_surface}")
        changes.append(
            {
                "change_id": f"{base_version}-{issue_tag}",
                "target_surface": target_surface,
                "issue_tags": [issue_tag],
                "rationale": f"Recurring issue tag {issue_tag!r} appeared {count} time(s) in the aggregate feedback.",
                "expected_benefit": strategy["expected_benefit"],
                "patch_strategy": strategy["patch_strategy"],
                "evidence": {
                    "issue_tag_count": count,
                    "example_refs": _example_refs_for_tag(aggregate, issue_tag),
                },
            }
        )

    target_surfaces = sorted({change["target_surface"] for change in changes})
    summary = (
        "Deterministic prompt proposal generated from recurring issue tags in aggregate feedback. "
        "This proposal suggests prompt-only edits and does not change code or business logic."
    )
    risks = [
        "Prompt changes may overfit to the sampled aggregate batch.",
        "Increasing specificity too aggressively may reduce brevity or tone quality.",
        "Any future applied patch must preserve safety and already-working strengths.",
    ]
    if not changes:
        risks.append("No supported issue tags were present, so the proposal contains no changes.")

    return {
        "generated_at": _utc_now_iso(),
        "aggregate_run_id": aggregate.get("run_id"),
        "aggregate_path": aggregate.get("input_dir"),
        "base_version": prompt_pack["version"],
        "proposed_version": f"{prompt_pack['version']}-proposal",
        "target_surfaces": target_surfaces,
        "summary": summary,
        "notes": [
            "This is a contract-first proposal artifact.",
            "No prompt pack was modified by this tool.",
        ],
        "risks": risks,
        "changes": changes,
    }


def write_proposal(path: Path, payload: Dict[str, Any]) -> None:
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    aggregate_path = Path(args.aggregate).expanduser().resolve()
    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else aggregate_path.with_name(DEFAULT_OUTPUT_NAME)
    )

    try:
        aggregate = _load_aggregate(aggregate_path)
        proposal = build_proposal(aggregate, base_version=args.base_version)
    except (ValueError, PromptPackError) as exc:
        print(str(exc), file=sys.stderr)
        return 1

    write_proposal(output_path, proposal)
    print(
        f"proposal changes={len(proposal['changes'])} "
        f"surfaces={', '.join(proposal['target_surfaces']) or 'none'} "
        f"output={output_path}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
