#!/usr/bin/env python3
"""Wrapper around the project-local intent debug CLI."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

# Intentionally blank. Set OPENAI_API_KEY in your shell environment.
LOCAL_OPENAI_API_KEY = ""


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[4]


def _debug_cli_path() -> Path:
    return _repo_root() / "sam-app" / "email_service" / "debug_conversation_intelligence.py"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the SmartMail local intent debugger."
    )
    parser.add_argument("--message", help="Inline message text to classify.")
    parser.add_argument("--repeat", type=int, help="Repeat the same classification N times.")
    parser.add_argument("--pretty", action="store_true", help="Pretty-print JSON output.")
    parser.add_argument("--raw", action="store_true", help="Include the submitted message in the output.")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cli_path = _debug_cli_path()
    if not cli_path.exists():
        print(f"Intent debug CLI not found: {cli_path}", file=sys.stderr)
        return 2

    command = [sys.executable, str(cli_path)]
    if args.message is not None:
        command.extend(["--message", args.message])
    if args.repeat is not None:
        command.extend(["--repeat", str(args.repeat)])
    if args.pretty:
        command.append("--pretty")
    if args.raw:
        command.append("--raw")

    # Allow a script-local fallback key for editor-only debugging without
    # modifying the production-facing debug CLI.
    env = os.environ.copy()
    if LOCAL_OPENAI_API_KEY.strip():
        env.setdefault("OPENAI_API_KEY", LOCAL_OPENAI_API_KEY.strip())

    stdin_text = None if sys.stdin.isatty() else sys.stdin.read()
    completed = subprocess.run(
        command,
        cwd=str(cli_path.parent),
        input=stdin_text,
        text=True,
        capture_output=True,
        env=env,
    )

    if completed.stdout:
        print(completed.stdout, end="")
    if completed.stderr:
        print(completed.stderr, end="", file=sys.stderr)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
