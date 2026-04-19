#!/usr/bin/env python3
"""Run a fixed multi-turn memory/continuity stress sequence against the live coaching pipeline.

Uses the same harness and trace logging as tools/debug_turn.py, but sends a
predefined list of messages turn-by-turn so continuity and durable memory can
be inspected over a longer interaction.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Any

from debug_turn import (  # type: ignore
    _do_send_turn,
    _print_json,
    _render_turn,
    _safe_snapshot,
    _trace_enabled,
    _trace_path_for_email,
)


DEFAULT_SEQUENCE = [
    "I’m not just rebuilding now. I want to raise FTP over the next 12 weeks.",
    "Actually, my main goal changed: I want long steady endurance more than FTP.",
    "My left knee is sore again, about 3/10, mostly after harder efforts.",
    "The knee is fine now. No pain this week.",
    "Starting next month I can only do long rides on Sundays.",
    "Correction: not Sundays, Saturdays only.",
    "Keep your replies short. I just want the decision, not a recap.",
    "Actually I do want a little explanation when the decision changes.",
    "My usual Zone 2 power is more like 105–125 W now.",
    "I did 4 rides last week for 160 km total.",
    "Should I test my FTP this week?",
    "I’d rather wait until next week.",
]


def _load_messages(path: str | None) -> list[str]:
    if not path:
        return list(DEFAULT_SEQUENCE)
    content = Path(path).read_text(encoding="utf-8")
    stripped = content.strip()
    if not stripped:
        return []
    if path.endswith(".json"):
        data = json.loads(stripped)
        if not isinstance(data, list) or not all(isinstance(item, str) for item in data):
            raise ValueError("messages JSON must be an array of strings")
        return [item.strip() for item in data if item.strip()]
    return [part.strip() for part in stripped.split("\n---\n") if part.strip()]


def cmd_run(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness  # type: ignore

    messages = _load_messages(args.messages_file)
    if not messages:
        _print_json({"ok": False, "error": "no messages to send"})
        return 1

    harness = LiveCoachingHarness()
    if args.register:
        print(f"[register] preparing verified athlete {args.email} ...")
        try:
            harness.prepare_verified_athlete(args.email)
        except RuntimeError as exc:
            _print_json({"ok": False, "error": f"register failed: {exc}"})
            return 1

    trace_path = _trace_path_for_email(args.email, override=args.trace_log)
    subject = args.subject or "Coaching update"
    turns: list[dict[str, Any]] = []

    print(f"memory-sequence run — email={args.email.lower()}")
    if _trace_enabled():
        print(f"trace log: {trace_path}")
    print(f"messages:  {len(messages)}")
    print()

    exit_code = 0
    for idx, body in enumerate(messages, start=1):
        print(f"[turn {idx}/{len(messages)}] sending {len(body)} chars")
        turn = _do_send_turn(
            harness,
            email_addr=args.email,
            subject=subject,
            body=body,
            date_received=None,
            trace_path=trace_path,
            turn_num=idx,
        )
        turns.append(turn)
        _render_turn(
            idx,
            subject,
            body,
            turn["coach_subject"],
            turn["coach_text"],
            turn["suppressed"],
            turn["prompt_calls"],
            turn["state_diff"],
            turn["trace_path"],
            turn["trace_line"],
        )
        if turn["error"]:
            exit_code = 1
            print(f"[error] turn {idx}: {turn['error']}", file=sys.stderr)
            if not args.keep_going:
                break
        if args.snapshot_each:
            snapshot = _safe_snapshot(harness, args.email.lower())
            print("snapshot keys:", sorted(snapshot.keys()))
            print()
        if args.delay_ms > 0 and idx < len(messages):
            time.sleep(args.delay_ms / 1000.0)

    if args.json:
        _print_json(
            {
                "ok": exit_code == 0,
                "email": args.email.lower(),
                "trace_log": str(trace_path),
                "turn_count": len(turns),
                "turns": [
                    {
                        "turn_num": i + 1,
                        "ok": turn["ok"],
                        "error": turn["error"],
                        "message_id": turn["message_id"],
                        "coach_reply_subject": turn["coach_subject"],
                        "coach_reply_text": turn["coach_text"],
                        "suppressed": turn["suppressed"],
                        "skill_count": len(turn["prompt_calls"]),
                        "skills": [c.get("skill") for c in turn["prompt_calls"]],
                        "memory_diff": turn["state_diff"],
                        "trace_line": turn["trace_line"],
                    }
                    for i, turn in enumerate(turns)
                ],
            }
        )

    print(f"[done] completed {len(turns)}/{len(messages)} turns")
    return exit_code


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run a fixed multi-turn memory/continuity stress sequence."
    )
    parser.add_argument("--email", required=True)
    parser.add_argument("--subject", default="starting a new season")
    parser.add_argument(
        "--messages-file",
        default=None,
        help="Optional path to messages. JSON array of strings, or plain text separated by '\\n---\\n'.",
    )
    parser.add_argument("--register", action="store_true", help="Cleanup + register before running")
    parser.add_argument("--trace-log", dest="trace_log", default=None)
    parser.add_argument("--delay-ms", type=int, default=0, help="Delay between turns")
    parser.add_argument("--snapshot-each", action="store_true", help="Print snapshot keys after each turn")
    parser.add_argument("--keep-going", action="store_true", help="Continue after an error")
    parser.add_argument("--json", action="store_true", help="Also print final JSON summary")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return cmd_run(args)


if __name__ == "__main__":
    sys.exit(main())
