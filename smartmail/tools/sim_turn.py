#!/usr/bin/env python3
"""Stateless CLI for driving the live coaching harness one turn at a time.

Used by the /athlete-sim skill. Each subcommand prints JSON to stdout.

Commands:
  register  — create + verify a sim athlete, print {"email", "athlete_id"}
  send      — send one inbound email, print coach reply + metadata
  snapshot  — fetch current DynamoDB state for an athlete
  cleanup   — delete all data for a sim athlete

Message trace (append-only JSONL, full athlete body + coach reply per send):
  Default path: sam-app/.cache/sim_turn_trace/<email_sanitized>.jsonl
  Disable: SMARTMAIL_SIM_TRACE=0
  Single file for all sims: SMARTMAIL_SIM_TRACE_LOG=/path/to/run.jsonl
"""

from __future__ import annotations

import argparse
import json
import os
import secrets
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
E2E_PATH = REPO_ROOT / "sam-app" / "tests" / "e2e"
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
for p in (E2E_PATH, EMAIL_SERVICE_PATH):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

os.environ.setdefault("ENABLE_LIVE_LLM_CALLS", "true")
os.environ.setdefault("ENABLE_SESSION_CHECKIN_EXTRACTION", "true")

# Append-only message trace (athlete → coach) for every `send`. Default on; set
# SMARTMAIL_SIM_TRACE=0 to disable. Override path with SMARTMAIL_SIM_TRACE_LOG.
_SIM_TRACE_DIR = REPO_ROOT / "sam-app" / ".cache" / "sim_turn_trace"


def _sim_trace_enabled() -> bool:
    raw = (os.environ.get("SMARTMAIL_SIM_TRACE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _sim_trace_path_for_email(email: str) -> Path:
    custom = (os.environ.get("SMARTMAIL_SIM_TRACE_LOG") or "").strip()
    if custom:
        return Path(custom).expanduser()
    safe = "".join(
        c if c.isalnum() or c in "-._" else "_"
        for c in email.strip().lower().replace("@", "_at_")
    ) or "unknown"
    _SIM_TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return _SIM_TRACE_DIR / f"{safe}.jsonl"


def _append_sim_trace(record: dict[str, Any]) -> None:
    if not _sim_trace_enabled():
        return
    try:
        path = _sim_trace_path_for_email(str(record.get("trace_email") or "unknown"))
        line = json.dumps(_json_safe(record), ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
    except OSError:
        pass


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(str(v) for v in value)
    return value


def _print_json(data: dict) -> None:
    print(json.dumps(_json_safe(data), indent=2, ensure_ascii=False))


def cmd_register(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness
    import dynamodb_models

    email = args.email or f"athlete-sim-{int(time.time())}-{secrets.token_hex(4)}@example.com"
    harness = LiveCoachingHarness()
    try:
        harness.prepare_verified_athlete(email)
    except RuntimeError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    athlete_id = dynamodb_models.get_athlete_id_for_email(email.lower())
    el = email.lower()
    _append_sim_trace({
        "kind": "register",
        "trace_email": el,
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "email": el,
        "athlete_id": athlete_id,
    })
    reg_out: dict[str, Any] = {"ok": True, "email": el, "athlete_id": athlete_id}
    if _sim_trace_enabled():
        reg_out["trace_log"] = str(_sim_trace_path_for_email(el))
    _print_json(reg_out)
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness

    if not args.email:
        _print_json({"ok": False, "error": "--email is required"})
        return 1
    if not args.body:
        _print_json({"ok": False, "error": "--body is required"})
        return 1

    harness = LiveCoachingHarness()
    subject = args.subject or "Coaching update"
    date_received = args.date or datetime.now(timezone.utc).strftime("%a, %d %b %Y %H:%M:%S +0000")
    email_l = args.email.strip().lower()

    try:
        result = harness.send_inbound_email(
            args.email,
            subject=subject,
            body=args.body,
            date_received=date_received,
        )
    except RuntimeError as exc:
        _append_sim_trace({
            "kind": "send_error",
            "trace_email": email_l,
            "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "error": str(exc),
            "athlete": {
                "date_received": date_received,
                "subject": subject,
                "body": args.body,
            },
        })
        _print_json({"ok": False, "error": str(exc)})
        return 1

    coach_reply_text = ""
    coach_reply_subject = ""
    if not result.suppressed and result.outbound:
        coach_reply_text = result.outbound.get("text", "")
        coach_reply_subject = result.outbound.get("subject", "")

    _append_sim_trace({
        "kind": "send",
        "trace_email": email_l,
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "athlete_id": result.athlete_id,
        "message_id": result.message_id,
        "athlete": {
            "date_received": result.date_received,
            "subject": subject,
            "body": args.body,
        },
        "coach": {
            "subject": coach_reply_subject,
            "text": coach_reply_text,
            "suppressed": result.suppressed,
            "lambda_body": result.lambda_body,
        },
    })
    trace_path = str(_sim_trace_path_for_email(email_l)) if _sim_trace_enabled() else ""
    out_ok: dict[str, Any] = {
        "ok": True,
        "athlete_id": result.athlete_id,
        "message_id": result.message_id,
        "date_received": result.date_received,
        "suppressed": result.suppressed,
        "lambda_body": result.lambda_body,
        "coach_reply_subject": coach_reply_subject,
        "coach_reply_text": coach_reply_text,
    }
    if trace_path:
        out_ok["trace_log"] = trace_path
    _print_json(out_ok)
    return 0


def cmd_snapshot(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness
    import dynamodb_models

    email = args.email
    if not email:
        _print_json({"ok": False, "error": "--email is required"})
        return 1

    athlete_id = args.athlete_id or dynamodb_models.get_athlete_id_for_email(email.lower())
    if not athlete_id:
        _print_json({"ok": False, "error": f"no athlete_id found for {email}"})
        return 1

    harness = LiveCoachingHarness()
    snap = harness.fetch_state_snapshot(athlete_id)
    snap["ok"] = True
    _print_json(snap)
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness

    if not args.email:
        _print_json({"ok": False, "error": "--email is required"})
        return 1

    harness = LiveCoachingHarness()
    harness.cleanup(args.email, athlete_id=args.athlete_id)
    _print_json({"ok": True, "email": args.email})
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Drive live coaching harness one turn at a time.")
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser("register", help="Register + verify a sim athlete")
    reg.add_argument("--email", help="Email address (auto-generated if omitted)")

    send = sub.add_parser("send", help="Send one inbound email, get coach reply")
    send.add_argument("--email", required=True)
    send.add_argument("--subject", default="Coaching update")
    send.add_argument("--body", required=True)
    send.add_argument("--date", help="RFC-2822 date string (defaults to now UTC)")

    snap = sub.add_parser("snapshot", help="Fetch current DynamoDB state")
    snap.add_argument("--email", required=True)
    snap.add_argument("--athlete-id", dest="athlete_id")

    clean = sub.add_parser("cleanup", help="Delete all data for a sim athlete")
    clean.add_argument("--email", required=True)
    clean.add_argument("--athlete-id", dest="athlete_id")

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "register": cmd_register,
        "send": cmd_send,
        "snapshot": cmd_snapshot,
        "cleanup": cmd_cleanup,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
