#!/usr/bin/env python3
"""Promote a prompt-pack version from a passing regression report."""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

import prompt_pack_loader


PROMPT_PACKS_ROOT = prompt_pack_loader.PROMPT_PACKS_ROOT


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Promote a new prompt-pack version from a passing regression report."
    )
    parser.add_argument("--base-version", help="Base prompt-pack version to copy from.")
    parser.add_argument(
        "--source-version",
        help="Existing prompt-pack version whose files should be copied into the promoted version.",
    )
    parser.add_argument("--new-version", help="New prompt-pack version to create.")
    parser.add_argument("--proposal", help="Path to proposal.json.")
    parser.add_argument("--regression-report", help="Path to regression_report.json.")
    parser.add_argument(
        "--activate",
        action="store_true",
        help="Write ACTIVE_VERSION for coach_reply to the new version after promotion.",
    )
    parser.add_argument(
        "--activate-version",
        help="Switch ACTIVE_VERSION for coach_reply to an existing version without promoting a new copy.",
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


def _coach_reply_root() -> Path:
    return PROMPT_PACKS_ROOT / "coach_reply"


def set_active_prompt_pack_version(version: str) -> Path:
    coach_reply_root = _coach_reply_root()
    target_dir = coach_reply_root / version
    if not target_dir.exists():
        raise ValueError(f"prompt-pack version not found: {target_dir}")
    active_version_path = coach_reply_root / prompt_pack_loader.ACTIVE_VERSION_FILE_NAME
    active_version_path.write_text(f"{version}\n", encoding="utf-8")
    return active_version_path


def promote_prompt_pack(
    *,
    base_version: str,
    source_version: str | None,
    new_version: str,
    proposal_path: Path,
    regression_report_path: Path,
    activate: bool,
) -> Path:
    coach_reply_root = _coach_reply_root()
    resolved_source_version = source_version or base_version
    source_dir = coach_reply_root / resolved_source_version
    target_dir = coach_reply_root / new_version
    if not source_dir.exists():
        raise ValueError(f"source prompt-pack version not found: {source_dir}")
    if target_dir.exists():
        raise ValueError(f"new prompt-pack version already exists: {target_dir}")

    proposal = _load_json(proposal_path)
    regression_report = _load_json(regression_report_path)
    if proposal.get("base_version") not in (None, base_version):
        raise ValueError("proposal base_version must match the requested base_version.")
    if regression_report.get("decision") != "promote":
        raise ValueError("regression report decision must be 'promote' before promotion.")
    if regression_report.get("base_version") not in (None, base_version):
        raise ValueError("regression report base_version must match the requested base_version.")

    shutil.copytree(source_dir, target_dir)
    manifest_path = target_dir / "manifest.json"
    manifest = _load_json(manifest_path)
    manifest["version"] = new_version
    manifest["parent_version"] = base_version
    manifest["source_version"] = resolved_source_version
    manifest["created_at"] = _utc_now_iso()
    manifest["source_proposal"] = str(proposal_path.resolve())
    manifest["source_regression_report"] = str(regression_report_path.resolve())
    manifest["metrics_summary"] = {
        "decision": regression_report.get("decision"),
        "base_metrics": regression_report.get("base_metrics", {}),
        "proposed_metrics": regression_report.get("proposed_metrics", {}),
        "score_deltas": regression_report.get("score_deltas", {}),
    }
    manifest["promotion_notes"] = [
        "Promoted from a passing regression report.",
        f"Proposal base_version={proposal.get('base_version')}",
        f"Proposal proposed_version={proposal.get('proposed_version')}",
        f"Regression proposed_version={regression_report.get('proposed_version')}",
        f"Copied from source_version={resolved_source_version}",
    ]
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    if activate:
        set_active_prompt_pack_version(new_version)

    return target_dir


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        if args.activate_version:
            if any([args.base_version, args.new_version, args.proposal, args.regression_report]):
                raise ValueError("--activate-version cannot be combined with promotion arguments.")
            active_path = set_active_prompt_pack_version(args.activate_version)
            print(
                f"active_version={args.activate_version} active_file={active_path}",
                flush=True,
            )
            return 0

        missing = [
            flag
            for flag, value in (
                ("--base-version", args.base_version),
                ("--new-version", args.new_version),
                ("--proposal", args.proposal),
                ("--regression-report", args.regression_report),
            )
            if not value
        ]
        if missing:
            raise ValueError(f"missing required arguments for promotion: {', '.join(missing)}")

        target_dir = promote_prompt_pack(
            base_version=args.base_version,
            source_version=args.source_version,
            new_version=args.new_version,
            proposal_path=Path(args.proposal).expanduser().resolve(),
            regression_report_path=Path(args.regression_report).expanduser().resolve(),
            activate=bool(args.activate),
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(
        f"promoted version={args.new_version} activate={str(bool(args.activate)).lower()} target={target_dir}",
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
