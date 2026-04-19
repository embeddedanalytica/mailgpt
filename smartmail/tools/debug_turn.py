#!/usr/bin/env python3
"""Interactive debug driver for the live coaching pipeline.

Use this when you need to manually type athlete messages and inspect what the
coaching pipeline does on each turn — every skill that fired, the full system
prompt + user content for each LLM call, and a memory diff before/after the
turn. Reuses LiveCoachingHarness so the run is end-to-end real (auth gates,
rule engine, business → coaching → skills → reply, real DynamoDB writes).

Subcommands:
  register   — create + verify a debug athlete, print {email, athlete_id}
  chat       — interactive REPL: type messages, see compact summaries per turn
  send       — one-shot: send a single message non-interactively (scriptable)
  snapshot   — fetch current DynamoDB state for an athlete
  cleanup    — delete all data for a debug athlete

Trace file (append-only JSONL, full prompts + state diff per turn):
  Default path: sam-app/.cache/debug_turn_trace/<email_sanitized>.jsonl
  Override:     SMARTMAIL_DEBUG_TRACE_LOG=/path/run.jsonl   or  --trace-log
  Disable:      SMARTMAIL_DEBUG_TRACE=0

Inspect the trace with jq, e.g.:
  jq 'select(.kind=="debug_send") | {turn:.turn_num, skills:[.skills[].skill], diff:.memory_diff}' file.jsonl
  jq '.skills[] | select(.skill=="response_generation") | .system_prompt' file.jsonl
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

# We are a debug tool: force live LLM calls and skill prompt tracing on.
os.environ.setdefault("ENABLE_LIVE_LLM_CALLS", "true")
os.environ.setdefault("ENABLE_SESSION_CHECKIN_EXTRACTION", "true")
os.environ["ENABLE_PROMPT_TRACE"] = "true"

_DEFAULT_TRACE_DIR = REPO_ROOT / "sam-app" / ".cache" / "debug_turn_trace"
_BAR = "─" * 60


# ─── trace file helpers ─────────────────────────────────────────────────────


def _trace_enabled() -> bool:
    raw = (os.environ.get("SMARTMAIL_DEBUG_TRACE") or "1").strip().lower()
    return raw not in ("0", "false", "no", "off")


def _trace_path_for_email(email: str, override: str | None = None) -> Path:
    custom = (override or os.environ.get("SMARTMAIL_DEBUG_TRACE_LOG") or "").strip()
    if custom:
        return Path(custom).expanduser()
    safe = "".join(
        c if c.isalnum() or c in "-._" else "_"
        for c in email.strip().lower().replace("@", "_at_")
    ) or "unknown"
    _DEFAULT_TRACE_DIR.mkdir(parents=True, exist_ok=True)
    return _DEFAULT_TRACE_DIR / f"{safe}.jsonl"


def _append_trace(path: Path, record: dict[str, Any]) -> int:
    """Append one record. Returns the resulting line number, or 0 if disabled/failed."""
    if not _trace_enabled():
        return 0
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps(_json_safe(record), ensure_ascii=False) + "\n"
        with path.open("a", encoding="utf-8") as fh:
            fh.write(line)
        with path.open("rb") as fh:
            return sum(1 for _ in fh)
    except OSError as exc:
        print(f"[warn] could not write trace: {exc}", file=sys.stderr)
        return 0


def _json_safe(value: Any) -> Any:
    if isinstance(value, Decimal):
        return int(value) if value == value.to_integral_value() else float(value)
    if isinstance(value, dict):
        return {str(k): _json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_safe(v) for v in value]
    if isinstance(value, set):
        return sorted(str(v) for v in value)
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def _print_json(data: dict) -> None:
    print(json.dumps(_json_safe(data), indent=2, ensure_ascii=False))


# ─── state diff ─────────────────────────────────────────────────────────────


def _shallow_diff(before: dict, after: dict) -> dict:
    if not isinstance(before, dict):
        before = {}
    if not isinstance(after, dict):
        after = {}
    before_keys = set(before.keys())
    after_keys = set(after.keys())
    added = sorted(after_keys - before_keys)
    removed = sorted(before_keys - after_keys)
    changed = sorted(k for k in before_keys & after_keys if before[k] != after[k])
    return {"added": added, "removed": removed, "changed": changed}


def _state_diff(before: dict | None, after: dict | None) -> dict:
    before = before or {}
    after = after or {}
    top = _shallow_diff(before, after)
    mem_b = before.get("memory_context") or {}
    mem_a = after.get("memory_context") or {}
    mem = _shallow_diff(
        mem_b if isinstance(mem_b, dict) else {},
        mem_a if isinstance(mem_a, dict) else {},
    )
    return {"top_level": top, "memory_context": mem}


# ─── prompt-trace capture (mutates skills.runtime.prompt_trace) ─────────────


def _reset_prompt_trace() -> None:
    from skills import runtime as skill_runtime  # type: ignore
    skill_runtime.prompt_trace.clear()


def _drain_prompt_trace() -> list[dict]:
    from skills import runtime as skill_runtime  # type: ignore
    drained = [dict(entry) for entry in skill_runtime.prompt_trace]
    skill_runtime.prompt_trace.clear()
    return drained


# ─── snapshot helper ────────────────────────────────────────────────────────


def _safe_snapshot(harness, email_l: str) -> dict:
    """Best-effort snapshot. Returns {} if athlete is not yet known."""
    try:
        import dynamodb_models  # type: ignore
        athlete_id = dynamodb_models.get_athlete_id_for_email(email_l)
        if not athlete_id:
            return {}
        snap = harness.fetch_state_snapshot(athlete_id)
        return _json_safe(snap) or {}
    except Exception as exc:  # noqa: BLE001 — debug tool, never crash on snapshot
        return {"_snapshot_error": str(exc)}


# ─── core: one debug send turn ──────────────────────────────────────────────


def _do_send_turn(
    harness,
    *,
    email_addr: str,
    subject: str,
    body: str,
    date_received: str | None,
    trace_path: Path,
    turn_num: int,
) -> dict:
    """Run one send turn. Captures state diff + prompt trace, appends a record."""
    email_l = email_addr.strip().lower()

    state_before = _safe_snapshot(harness, email_l)
    _reset_prompt_trace()

    resolved_date = date_received or datetime.now(timezone.utc).strftime(
        "%a, %d %b %Y %H:%M:%S +0000"
    )

    error_msg: str | None = None
    result = None
    try:
        result = harness.send_inbound_email(
            email_addr,
            subject=subject,
            body=body,
            date_received=resolved_date,
        )
    except RuntimeError as exc:
        error_msg = str(exc)

    prompt_calls = _drain_prompt_trace()
    state_after = _safe_snapshot(harness, email_l)
    diff = _state_diff(state_before, state_after)

    coach_subject = ""
    coach_text = ""
    suppressed = False
    athlete_id = ""
    message_id = ""
    lambda_body = ""
    if result is not None:
        athlete_id = result.athlete_id
        message_id = result.message_id
        lambda_body = result.lambda_body
        suppressed = result.suppressed
        if not result.suppressed and result.outbound:
            coach_subject = result.outbound.get("subject", "")
            coach_text = result.outbound.get("text", "")

    record = {
        "kind": "debug_send" if error_msg is None else "debug_send_error",
        "ts_utc": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "trace_email": email_l,
        "turn_num": turn_num,
        "athlete_id": athlete_id,
        "message_id": message_id,
        "athlete": {
            "subject": subject,
            "body": body,
            "date_received": resolved_date,
        },
        "coach": {
            "subject": coach_subject,
            "text": coach_text,
            "suppressed": suppressed,
            "lambda_body": lambda_body,
        },
        "skills": prompt_calls,
        "state_before": state_before,
        "state_after": state_after,
        "memory_diff": diff,
    }
    if error_msg:
        record["error"] = error_msg

    line_num = _append_trace(trace_path, record)

    return {
        "ok": error_msg is None,
        "error": error_msg,
        "athlete_id": athlete_id,
        "message_id": message_id,
        "athlete_subject": subject,
        "athlete_body": body,
        "coach_subject": coach_subject,
        "coach_text": coach_text,
        "suppressed": suppressed,
        "prompt_calls": prompt_calls,
        "state_diff": diff,
        "trace_path": trace_path,
        "trace_line": line_num,
    }


# ─── console rendering ──────────────────────────────────────────────────────


def _preview(text: str, *, limit: int = 240) -> str:
    s = " ".join(str(text or "").split())
    return s if len(s) <= limit else s[: limit - 3] + "..."


def _render_turn(
    turn_num: int,
    athlete_subject: str,
    athlete_body: str,
    coach_subject: str,
    coach_text: str,
    suppressed: bool,
    prompt_calls: list[dict],
    state_diff: dict,
    trace_path: Path,
    trace_line: int,
) -> None:
    print(f"\n─── turn {turn_num} ───────────────────────────────────────────")
    print(f"> athlete (subject: {athlete_subject})")
    print(f"  {_preview(athlete_body)}")
    print()
    print(f"< coach   (subject: {coach_subject or '(none)'}) suppressed={suppressed}")
    print(f"  {_preview(coach_text) if coach_text else '(no reply body)'}")
    print()
    print(f"skills fired ({len(prompt_calls)}):")
    if not prompt_calls:
        print("  (none — pipeline did not reach any LLM call)")
    for i, call in enumerate(prompt_calls, 1):
        sk = str(call.get("skill", "?"))
        sys_len = len(str(call.get("system_prompt", "")))
        usr_len = len(str(call.get("user_content", "")))
        model = str(call.get("model", "?"))
        print(f"  {i:>2}. {sk:<32} model={model:<22} sys={sys_len}ch user={usr_len}ch")
    print()
    top = state_diff.get("top_level", {})
    mem = state_diff.get("memory_context", {})
    print("memory diff:")
    print(
        f"  top_level:      changed={top.get('changed', [])}  "
        f"added={top.get('added', [])}  removed={top.get('removed', [])}"
    )
    print(
        f"  memory_context: changed={mem.get('changed', [])}  "
        f"added={mem.get('added', [])}  removed={mem.get('removed', [])}"
    )
    print()
    if trace_line:
        print(f"trace: {trace_path}  line={trace_line}")
    print(_BAR)


# ─── subcommands ────────────────────────────────────────────────────────────


def cmd_register(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness  # type: ignore
    import dynamodb_models  # type: ignore

    email_addr = args.email or (
        f"athlete-debug-{int(time.time())}-{secrets.token_hex(4)}@example.com"
    )
    harness = LiveCoachingHarness()
    try:
        harness.prepare_verified_athlete(email_addr)
    except RuntimeError as exc:
        _print_json({"ok": False, "error": str(exc)})
        return 1

    el = email_addr.lower()
    athlete_id = dynamodb_models.get_athlete_id_for_email(el)
    trace_path = _trace_path_for_email(el, override=args.trace_log)
    out: dict[str, Any] = {"ok": True, "email": el, "athlete_id": athlete_id}
    if _trace_enabled():
        out["trace_log"] = str(trace_path)
    _print_json(out)
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness  # type: ignore

    if not args.email or not args.body:
        _print_json({"ok": False, "error": "--email and --body are required"})
        return 1

    harness = LiveCoachingHarness()
    if args.register:
        try:
            harness.prepare_verified_athlete(args.email)
        except RuntimeError as exc:
            _print_json({"ok": False, "error": f"register failed: {exc}"})
            return 1

    trace_path = _trace_path_for_email(args.email, override=args.trace_log)
    subject = args.subject or "Coaching update"
    turn = _do_send_turn(
        harness,
        email_addr=args.email,
        subject=subject,
        body=args.body,
        date_received=args.date,
        trace_path=trace_path,
        turn_num=1,
    )

    if args.json:
        _print_json(
            {
                "ok": turn["ok"],
                "error": turn["error"],
                "athlete_id": turn["athlete_id"],
                "message_id": turn["message_id"],
                "coach_reply_subject": turn["coach_subject"],
                "coach_reply_text": turn["coach_text"],
                "suppressed": turn["suppressed"],
                "skill_count": len(turn["prompt_calls"]),
                "skills": [c.get("skill") for c in turn["prompt_calls"]],
                "memory_diff": turn["state_diff"],
                "trace_log": str(turn["trace_path"]),
                "trace_line": turn["trace_line"],
            }
        )
    else:
        _render_turn(
            1,
            subject,
            args.body,
            turn["coach_subject"],
            turn["coach_text"],
            turn["suppressed"],
            turn["prompt_calls"],
            turn["state_diff"],
            turn["trace_path"],
            turn["trace_line"],
        )
        if turn["error"]:
            print(f"[error] {turn['error']}", file=sys.stderr)
    return 0 if turn["ok"] else 1


def cmd_chat(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness  # type: ignore

    harness = LiveCoachingHarness()
    if args.register:
        print(f"[register] preparing verified athlete {args.email} ...")
        try:
            harness.prepare_verified_athlete(args.email)
        except RuntimeError as exc:
            print(f"[error] register failed: {exc}", file=sys.stderr)
            return 1

    trace_path = _trace_path_for_email(args.email, override=args.trace_log)
    email_l = args.email.lower()

    print(f"debug-turn chat — email={email_l}")
    print(f"trace log:    {trace_path}")
    print("input:        type a message, end with '.' on its own line to send")
    print("commands:     /subject TEXT  /snapshot  /quit  /help")
    print()

    default_subject = args.subject or "Coaching update"
    next_subject = default_subject
    turn_num = 0

    while True:
        try:
            print(f"\n--- turn {turn_num + 1} (subject: {next_subject}) ---")
            print("(end with '.' on its own line; or type a /command)")
            try:
                first = input("> ")
            except EOFError:
                print()
                return 0

            stripped = first.strip()

            if stripped.startswith("/"):
                cmd, _, rest = stripped[1:].partition(" ")
                cmd = cmd.lower()
                if cmd in ("quit", "exit", "q"):
                    return 0
                if cmd == "help":
                    print("  /subject TEXT   set subject for the next message")
                    print("  /snapshot       print the current DynamoDB snapshot")
                    print("  /quit           exit the REPL")
                    continue
                if cmd == "subject":
                    if rest.strip():
                        next_subject = rest.strip()
                        print(f"[subject set] {next_subject}")
                    else:
                        print(f"[current subject] {next_subject}")
                    continue
                if cmd == "snapshot":
                    _print_json(_safe_snapshot(harness, email_l))
                    continue
                print(f"[unknown command] /{cmd}  (try /help)")
                continue

            if stripped == ".":
                continue

            lines = [first]
            cancelled = False
            while True:
                try:
                    line = input("  ")
                except EOFError:
                    print()
                    return 0
                if line.strip() == ".":
                    break
                lines.append(line)

            if cancelled:
                continue
            body = "\n".join(lines).rstrip()
            if not body:
                continue

            turn_num += 1
            print(f"[sending] turn {turn_num}, subject={next_subject!r}, {len(body)} chars ...")
            turn = _do_send_turn(
                harness,
                email_addr=args.email,
                subject=next_subject,
                body=body,
                date_received=None,
                trace_path=trace_path,
                turn_num=turn_num,
            )
            _render_turn(
                turn_num,
                next_subject,
                body,
                turn["coach_subject"],
                turn["coach_text"],
                turn["suppressed"],
                turn["prompt_calls"],
                turn["state_diff"],
                turn["trace_path"],
                turn["trace_line"],
            )
            if not turn["ok"]:
                print(f"[error] {turn['error']}", file=sys.stderr)
            next_subject = default_subject
        except KeyboardInterrupt:
            print("\n[interrupted; type /quit to exit]")
            continue


def cmd_snapshot(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness  # type: ignore
    import dynamodb_models  # type: ignore

    if not args.email:
        _print_json({"ok": False, "error": "--email is required"})
        return 1

    athlete_id = args.athlete_id or dynamodb_models.get_athlete_id_for_email(
        args.email.lower()
    )
    if not athlete_id:
        _print_json({"ok": False, "error": f"no athlete_id found for {args.email}"})
        return 1

    harness = LiveCoachingHarness()
    snap = harness.fetch_state_snapshot(athlete_id)
    snap["ok"] = True
    _print_json(snap)
    return 0


def cmd_cleanup(args: argparse.Namespace) -> int:
    from live_coaching_harness import LiveCoachingHarness  # type: ignore

    if not args.email:
        _print_json({"ok": False, "error": "--email is required"})
        return 1

    harness = LiveCoachingHarness()
    harness.cleanup(args.email, athlete_id=args.athlete_id)
    _print_json({"ok": True, "email": args.email})
    return 0


# ─── argparse wiring ────────────────────────────────────────────────────────


def _add_trace_log_arg(p: argparse.ArgumentParser) -> None:
    p.add_argument(
        "--trace-log",
        dest="trace_log",
        default=None,
        help="Override trace log path (default: sam-app/.cache/debug_turn_trace/<email>.jsonl)",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Interactive debug driver for the live coaching pipeline."
    )
    sub = parser.add_subparsers(dest="command", required=True)

    reg = sub.add_parser("register", help="Register + verify a debug athlete")
    reg.add_argument("--email", help="Email address (auto-generated if omitted)")
    _add_trace_log_arg(reg)

    chat = sub.add_parser(
        "chat", help="Interactive REPL — type messages, see compact summaries"
    )
    chat.add_argument("--email", required=True)
    chat.add_argument("--subject", default=None, help="Default subject (override per turn with /subject)")
    chat.add_argument(
        "--register",
        action="store_true",
        help="Cleanup + re-register the athlete before starting the REPL",
    )
    _add_trace_log_arg(chat)

    send = sub.add_parser(
        "send", help="One-shot: send a single message non-interactively"
    )
    send.add_argument("--email", required=True)
    send.add_argument("--subject", default=None)
    send.add_argument("--body", required=True)
    send.add_argument("--date", default=None, help="RFC-2822 date string (defaults to now UTC)")
    send.add_argument("--register", action="store_true", help="Cleanup + register before sending")
    send.add_argument("--json", action="store_true", help="Print JSON instead of human-readable summary")
    _add_trace_log_arg(send)

    snap = sub.add_parser("snapshot", help="Print the current DynamoDB state for an athlete")
    snap.add_argument("--email", required=True)
    snap.add_argument("--athlete-id", dest="athlete_id")
    _add_trace_log_arg(snap)

    clean = sub.add_parser("cleanup", help="Delete all data for a debug athlete")
    clean.add_argument("--email", required=True)
    clean.add_argument("--athlete-id", dest="athlete_id")
    _add_trace_log_arg(clean)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    dispatch = {
        "register": cmd_register,
        "chat": cmd_chat,
        "send": cmd_send,
        "snapshot": cmd_snapshot,
        "cleanup": cmd_cleanup,
    }
    return dispatch[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
