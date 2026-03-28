"""Local CLI for exercising real conversation-intelligence classification."""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from typing import Any, Dict, Optional

from conversation_intelligence import analyze_conversation_intelligence


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run real conversation-intelligence classification locally."
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--message", help="Inline message text to classify.")
    group.add_argument("--file", dest="file_path", help="Path to a text file to classify.")
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty-print JSON output.",
    )
    parser.add_argument(
        "--raw",
        action="store_true",
        help="Include the submitted message in the output.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Repeat the same classification N times.",
    )
    return parser


def _read_message(args: argparse.Namespace, stdin_text: Optional[str] = None) -> str:
    if args.message is not None:
        message = args.message
    elif args.file_path is not None:
        with open(args.file_path, "r", encoding="utf-8") as handle:
            message = handle.read()
    else:
        if stdin_text is None:
            if sys.stdin.isatty():
                message = ""
            else:
                message = sys.stdin.read()
        else:
            message = stdin_text

    message = str(message).strip()
    if not message:
        raise ValueError(
            "No message provided. Use --message, --file, or pipe text on stdin."
        )
    return message


def _build_run_payload(
    message: str,
    *,
    include_raw: bool,
    run_index: int,
) -> Dict[str, Any]:
    started_at = time.perf_counter()
    result = analyze_conversation_intelligence(message)
    elapsed_ms = round((time.perf_counter() - started_at) * 1000, 2)

    payload: Dict[str, Any] = {
        "run": run_index,
        "intent": result.get("intent"),
        "complexity_score": result.get("complexity_score"),
        "requested_action": result.get("requested_action"),
        "brevity_preference": result.get("brevity_preference"),
        "model_name": result.get("model_name"),
        "resolution_source": result.get("resolution_source"),
        "intent_resolution_reason": result.get("intent_resolution_reason"),
        "elapsed_ms": elapsed_ms,
    }
    if "signals" in result:
        payload["signals"] = result["signals"]
    if include_raw:
        payload["raw_message"] = message
    return payload


def _serialize_output(payload: Any, *, pretty: bool) -> str:
    if pretty:
        return json.dumps(payload, indent=2, sort_keys=True)
    return json.dumps(payload, separators=(",", ":"), sort_keys=True)


def main(argv: Optional[list[str]] = None, *, stdin_text: Optional[str] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.repeat < 1:
        print("--repeat must be >= 1.", file=sys.stderr)
        return 2

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required for local intent debugging.", file=sys.stderr)
        return 2

    try:
        message = _read_message(args, stdin_text=stdin_text)
    except FileNotFoundError as exc:
        print(f"Message file not found: {exc.filename}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(f"Failed to read message input: {exc}", file=sys.stderr)
        return 2
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    try:
        if args.repeat == 1:
            output: Any = _build_run_payload(message, include_raw=args.raw, run_index=1)
        else:
            output = [
                _build_run_payload(message, include_raw=args.raw, run_index=index)
                for index in range(1, args.repeat + 1)
            ]
    except Exception as exc:
        print(f"Intent classification failed: {exc}", file=sys.stderr)
        return 1

    print(_serialize_output(output, pretty=args.pretty))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
