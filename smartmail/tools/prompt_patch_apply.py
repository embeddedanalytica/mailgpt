#!/usr/bin/env python3
"""Materialize a proposed prompt-pack version from a proposal artifact."""

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
SURFACE_FILE_MAP = {
    "response_generation.directive_system_prompt": (
        "response_generation.json",
        "directive_system_prompt_lines",
    ),
    "coaching_reasoning.base_prompt": ("coaching_reasoning.json", "base_prompt_lines"),
}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Materialize a proposed prompt-pack version from proposal.json."
    )
    parser.add_argument("--proposal", required=True, help="Path to proposal.json.")
    parser.add_argument(
        "--base-version",
        help="Optional base version override. Defaults to proposal.base_version.",
    )
    parser.add_argument(
        "--output-version",
        help="Optional proposed version override. Defaults to proposal.proposed_version.",
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


def _render_change_lines(change: Dict[str, Any]) -> List[str]:
    issue_tags = change.get("issue_tags") or []
    issue_tag_text = ", ".join(str(item) for item in issue_tags) or "unspecified"
    lines = [
        "",
        f"[Prompt feedback update for {issue_tag_text}]",
        str(change.get("patch_strategy") or "").strip(),
    ]
    example_refs = change.get("evidence", {}).get("example_refs", [])
    improved_examples = [
        str(item.get("improved_reply_example") or "").strip()
        for item in example_refs
        if isinstance(item, dict) and str(item.get("improved_reply_example") or "").strip()
    ]
    if improved_examples:
        lines.append(f"Representative improved example: {improved_examples[0]}")
    return [line for line in lines if line != "" or lines.count("") == 1]


def apply_proposal(
    *,
    proposal_path: Path,
    base_version: str | None = None,
    output_version: str | None = None,
) -> Path:
    proposal = _load_json(proposal_path)
    resolved_base_version = base_version or str(proposal.get("base_version") or "").strip()
    resolved_output_version = output_version or str(proposal.get("proposed_version") or "").strip()
    if not resolved_base_version:
        raise ValueError("proposal base_version is required.")
    if not resolved_output_version:
        raise ValueError("proposal proposed_version is required.")

    coach_reply_root = _coach_reply_root()
    source_dir = coach_reply_root / resolved_base_version
    target_dir = coach_reply_root / resolved_output_version
    if not source_dir.exists():
        raise ValueError(f"base prompt-pack version not found: {source_dir}")
    if target_dir.exists():
        raise ValueError(f"output prompt-pack version already exists: {target_dir}")

    shutil.copytree(source_dir, target_dir)
    changes = proposal.get("changes")
    if not isinstance(changes, list):
        raise ValueError("proposal changes must be a list.")

    grouped_lines: Dict[tuple[str, str], List[str]] = {}
    for change in changes:
        if not isinstance(change, dict):
            raise ValueError("proposal changes must contain objects.")
        target_surface = str(change.get("target_surface") or "").strip()
        mapping = SURFACE_FILE_MAP.get(target_surface)
        if mapping is None:
            raise ValueError(f"unsupported proposal target surface: {target_surface}")
        grouped_lines.setdefault(mapping, []).extend(_render_change_lines(change))

    for (file_name, key), extra_lines in grouped_lines.items():
        path = target_dir / file_name
        payload = _load_json(path)
        current_lines = payload.get(key)
        if not isinstance(current_lines, list) or not all(isinstance(item, str) for item in current_lines):
            raise ValueError(f"prompt-pack field {key!r} must be a string list: {path}")
        payload[key] = [*current_lines, *extra_lines]
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    manifest_path = target_dir / "manifest.json"
    manifest = _load_json(manifest_path)
    manifest["version"] = resolved_output_version
    manifest["parent_version"] = resolved_base_version
    manifest["created_at"] = _utc_now_iso()
    manifest["source_proposal"] = str(proposal_path.resolve())
    manifest["proposal_applied_at"] = _utc_now_iso()
    notes = manifest.get("notes")
    if isinstance(notes, list):
        updated_notes = list(notes)
    elif isinstance(notes, str):
        updated_notes = [notes]
    else:
        updated_notes = []
    updated_notes.append("Materialized from proposal.json via prompt_patch_apply.py.")
    manifest["notes"] = updated_notes
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return target_dir


def main(argv: List[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        target_dir = apply_proposal(
            proposal_path=Path(args.proposal).expanduser().resolve(),
            base_version=args.base_version,
            output_version=args.output_version,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    print(f"applied proposal target={target_dir}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
