#!/usr/bin/env python3
"""Run coaching-reasoning on a production-shaped ResponseBrief (local OpenAI call).

Uses the same path as production: build_response_brief → run_coaching_reasoning_workflow.

Example (repo root):
  PYTHONPATH=sam-app/email_service OPENAI_API_KEY=sk-... ENABLE_LIVE_LLM_CALLS=true \\
    python3 tools/debug_coaching_reply_action.py \\
    --subject 'starting a new season' --body-file ./my_email_body.txt

  echo 'Your email text...' | PYTHONPATH=sam-app/email_service ... \\
    python3 tools/debug_coaching_reply_action.py --subject 'Re: hi'
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path
from typing import Any, Dict, List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE = REPO_ROOT / "sam-app" / "email_service"
if str(EMAIL_SERVICE) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE))

os.environ.setdefault("ENABLE_LIVE_LLM_CALLS", "true")

from continuity_bootstrap import bootstrap_continuity_state  # noqa: E402
from coaching import _resolve_reply_mode  # noqa: E402
from response_generation_assembly import build_response_brief  # noqa: E402
from sectioned_memory_contract import empty_sectioned_memory  # noqa: E402
from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow  # noqa: E402


def _default_profile() -> Dict[str, Any]:
    now = int(time.time())
    return {
        "primary_goal": "rebuild fitness",
        "experience_level": "intermediate",
        "main_sport_current": "bike",
        "time_availability": {
            "availability_notes": (
                "300 minutes per week in active zones; at least 100km ride per week"
            ),
        },
        "created_at": now - 86400,
    }


def _default_rule_engine(args: argparse.Namespace) -> Dict[str, Any]:
    d: Dict[str, Any] = {
        "intent": args.intent,
        "requested_action": args.requested_action or "",
        "clarification_needed": not args.no_clarification,
    }
    if args.rule_engine_status:
        d["rule_engine_status"] = args.rule_engine_status
    return d


def _parse_missing(raw: str) -> List[str]:
    parts = [p.strip() for p in raw.replace("|", ",").split(",")]
    return [p for p in parts if p]


def main(argv: Optional[List[str]] = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--subject", default="Coaching", help="Inbound subject line")
    p.add_argument("--body", default="", help="Inbound body (short); prefer --body-file or stdin")
    p.add_argument("--body-file", type=Path, help="File containing inbound body")
    p.add_argument(
        "--model",
        default=os.getenv("ADVANCED_RESPONSE_MODEL") or os.getenv("OPENAI_GENERIC_MODEL") or "gpt-4o-mini-2024-07-18",
        help="Model name for coaching-reasoning",
    )
    p.add_argument(
        "--missing",
        default="injury_status",
        help="Comma-separated missing_profile_fields (e.g. injury_status or time_availability,injury_status)",
    )
    p.add_argument("--intent", default="coaching", help="rule_engine_decision.intent")
    p.add_argument(
        "--requested-action",
        default="plan_update",
        dest="requested_action",
        help="rule_engine_decision.requested_action",
    )
    p.add_argument(
        "--no-clarification",
        action="store_true",
        help="Set clarification_needed=false on rule_engine_decision (typical coaching turn)",
    )
    p.add_argument(
        "--rule-engine-status",
        default="inactive",
        help="rule_engine_status string (e.g. inactive)",
    )
    p.add_argument(
        "--plan-summary",
        default="Base rebuild week: easy aerobic focus, consistency first.",
        help="Plan summary string for validated_plan",
    )
    p.add_argument(
        "--profile-json",
        type=Path,
        help="JSON file overriding synthetic coach profile (merge over defaults)",
    )
    p.add_argument(
        "--print-brief",
        action="store_true",
        help="Print full response_brief JSON before the LLM call",
    )
    args = p.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required.", file=sys.stderr)
        return 2

    if args.body_file:
        body = args.body_file.read_text(encoding="utf-8")
    elif not sys.stdin.isatty():
        body = sys.stdin.read()
    else:
        body = args.body
    body = (body or "").strip()
    if not body:
        print("Provide --body, --body-file, or pipe body on stdin.", file=sys.stderr)
        return 2

    profile = _default_profile()
    if args.profile_json:
        extra = json.loads(args.profile_json.read_text(encoding="utf-8"))
        if not isinstance(extra, dict):
            print("--profile-json must be a JSON object.", file=sys.stderr)
            return 2
        profile.update(extra)

    missing = _parse_missing(args.missing)
    rule_engine = _default_rule_engine(args)

    reply_mode = _resolve_reply_mode(
        missing_profile_fields=missing,
        rule_engine_decision=rule_engine,
    )

    memory_context: Dict[str, Any] = {
        "memory_available": False,
        "continuity_summary": None,
        "sectioned_memory": empty_sectioned_memory(),
    }

    brief = build_response_brief(
        athlete_id="debug_local_athlete",
        reply_kind=reply_mode,
        inbound_subject=args.subject,
        inbound_body=body,
        selected_model_name=args.model,
        profile_after=profile,
        missing_profile_fields=missing,
        plan_summary=args.plan_summary,
        rule_engine_decision=rule_engine,
        memory_context=memory_context,
        connect_strava_link=None,
        intake_completed_this_turn=False,
    )

    today = date.today()
    continuity_ctx = bootstrap_continuity_state(profile, "base", today).to_continuity_context(today)

    if args.print_brief:
        print("=== response_brief (canonical) ===")
        print(json.dumps(brief.to_dict(), indent=2, ensure_ascii=False))
        print("=== resolved reply_mode ===", reply_mode)
        print()

    result = run_coaching_reasoning_workflow(
        brief.to_dict(),
        model_name=args.model,
        continuity_context=continuity_ctx,
    )
    directive = result["directive"]
    trace = result.get("doctrine_trace") or {}

    out = {
        "reply_mode_resolved": reply_mode,
        "rule_engine_stub": rule_engine,
        "missing_profile_fields": missing,
        "reply_action": directive.get("reply_action"),
        "rationale": directive.get("rationale"),
        "doctrine_files_loaded": result.get("doctrine_files_loaded"),
        "doctrine_trace": {
            "turn_purpose": trace.get("turn_purpose"),
            "response_shape": trace.get("response_shape"),
            "posture": trace.get("posture"),
            "trajectory": trace.get("trajectory"),
        },
    }
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
