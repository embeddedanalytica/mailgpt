"""Test bench for conversation-intelligence classification.

Runs curated messages against the live LLM and validates that
requested_action and brevity_preference match expectations.

Usage:
    python3 ci_test_bench.py                    # run all cases
    python3 ci_test_bench.py --tag confirmations # run one category
    python3 ci_test_bench.py --repeat 3          # consistency check
    python3 ci_test_bench.py --message "text"    # ad-hoc (no expected value)
    python3 ci_test_bench.py --pretty            # full JSON per case
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from conversation_intelligence import analyze_conversation_intelligence


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    tag: str
    message: str
    expected_action: str
    expected_brevity: Optional[str] = None
    note: str = ""


# Organized by failure mode, not by label.
TEST_CASES: List[TestCase] = [
    # --- confirmations (the bug we fixed) ---
    TestCase(
        tag="confirmations",
        message="Confirmed. Plan stays. I'll send the check-in next week.",
        expected_action="checkin_ack",
        expected_brevity="brief",
        note="simple plan confirmation",
    ),
    TestCase(
        tag="confirmations",
        message="Sounds good — I'll start Monday.",
        expected_action="checkin_ack",
        expected_brevity="brief",
    ),
    TestCase(
        tag="confirmations",
        message="Got it, I'll check in next week.",
        expected_action="checkin_ack",
        expected_brevity="brief",
    ),
    TestCase(
        tag="confirmations",
        message="Thanks — plan confirmed and I'll send the Week-2 check-in as agreed.",
        expected_action="checkin_ack",
        expected_brevity="brief",
    ),
    TestCase(
        tag="confirmations",
        message=(
            "Confirmed — I got your note. We stay on the 4-run/week two-week rebuild "
            "(Mon/Tue/Thu/Sat), weekday runs finish by 6:45 AM, and anchors are protected. "
            "I'll send the Week-2 check-in next week."
        ),
        expected_action="checkin_ack",
        note="long confirmation restating the plan without requesting changes",
    ),

    # --- training reports ---
    TestCase(
        tag="training_reports",
        message="Did my tempo run today, felt good. Legs a bit heavy but manageable.",
        expected_action="checkin_ack",
    ),
    TestCase(
        tag="training_reports",
        message=(
            "Week 1 check-in:\n"
            "Mon: Y — 30 min easy\n"
            "Tue: Y — 25 min easy + 10 min mobility\n"
            "Thu: Y — 35 min easy\n"
            "Sat: Y — 75 min long run\n"
            "Sleep: 7 hrs avg. Energy: 7/10. No niggles."
        ),
        expected_action="checkin_ack",
        note="structured check-in with data",
    ),
    TestCase(
        tag="training_reports",
        message="Hit a PR on my 5k! 22:30, felt strong the whole way.",
        expected_action="checkin_ack",
    ),

    # --- explicit plan changes (must be plan_update) ---
    TestCase(
        tag="plan_changes",
        message="Can we add a swim day? I have pool access on Wednesdays now.",
        expected_action="plan_update",
    ),
    TestCase(
        tag="plan_changes",
        message="I need to move my long run to Saturday. Sundays don't work anymore.",
        expected_action="plan_update",
    ),
    TestCase(
        tag="plan_changes",
        message="My availability changed — I can only do 3 days now instead of 4.",
        expected_action="plan_update",
    ),
    TestCase(
        tag="plan_changes",
        message=(
            "Please update the 2-week rebuild to include four runs/week instead of three. "
            "Keep everything easy and finishable by 6:45 AM."
        ),
        expected_action="plan_update",
    ),

    # --- questions ---
    TestCase(
        tag="questions",
        message="Why do I do strides after easy runs? Seems counterintuitive.",
        expected_action="answer_question",
    ),
    TestCase(
        tag="questions",
        message="Is this pace too fast for recovery? I averaged 8:30/mi on my easy run.",
        expected_action="answer_question",
    ),
    TestCase(
        tag="questions",
        message="What should I eat before a long ride?",
        expected_action="answer_question",
    ),

    # --- clarifications ---
    TestCase(
        tag="clarifications",
        message="Yes, 4 days works.",
        expected_action="clarify_only",
        expected_brevity="brief",
    ),
    TestCase(
        tag="clarifications",
        message="No injuries right now.",
        expected_action="clarify_only",
        expected_brevity="brief",
    ),
    TestCase(
        tag="clarifications",
        message="I meant Thursday not Tuesday.",
        expected_action="clarify_only",
        expected_brevity="brief",
    ),

    # --- mixed signals (the hard cases) ---
    TestCase(
        tag="mixed",
        message=(
            "Week went well, hit all sessions. But can we make Thursday 35 minutes "
            "instead of 30? I have a bit more time that morning."
        ),
        expected_action="plan_update",
        note="check-in + plan change request → plan_update",
    ),
    TestCase(
        tag="mixed",
        message=(
            "Confirmed the plan for next week. Also, is this pace okay for my "
            "easy runs? I've been running around 9:00/mi."
        ),
        expected_action="answer_question",
        note="confirmation + question → answer_question",
    ),
    TestCase(
        tag="mixed",
        message=(
            "I'll keep the plan as-is. One thing — I tweaked Tuesday to 30s holds "
            "instead of 45s on the mobility routine. Hope that's fine."
        ),
        expected_action="checkin_ack|answer_question",
        note="confirmation with minor self-adjustment — either label is fine, both route read_only",
    ),

    # --- brevity edge cases ---
    TestCase(
        tag="brevity",
        message="Yes.",
        expected_action="clarify_only|checkin_ack",
        expected_brevity="brief",
    ),
    TestCase(
        tag="brevity",
        message="Got it, thanks.",
        expected_action="checkin_ack",
        expected_brevity="brief",
    ),
    TestCase(
        tag="brevity",
        message=(
            "I've been thinking about this and I want to restructure my week. "
            "Right now I run Mon/Wed/Fri/Sun but I'd like to shift to Tue/Thu/Sat "
            "with a long run on Sunday. The reason is my work schedule is changing "
            "next month and mornings on MWF won't work. I also want to add a "
            "30-minute strength session on Wednesday if that fits."
        ),
        expected_action="plan_update",
        expected_brevity="normal",
        note="detailed change request should be normal brevity",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _classify(message: str) -> Dict[str, Any]:
    started = time.perf_counter()
    result = analyze_conversation_intelligence(message)
    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    result["elapsed_ms"] = elapsed_ms
    return result


def _run_case(case: TestCase, repeats: int) -> Dict[str, Any]:
    results = [_classify(case.message) for _ in range(repeats)]
    actions = [r.get("requested_action") for r in results]
    brevities = [r.get("brevity_preference") for r in results]

    allowed_actions = set(case.expected_action.split("|"))
    action_pass = all(a in allowed_actions for a in actions)
    brevity_pass = (
        case.expected_brevity is None
        or all(b == case.expected_brevity for b in brevities)
    )

    return {
        "tag": case.tag,
        "message": case.message[:80],
        "note": case.note,
        "expected_action": case.expected_action,
        "expected_brevity": case.expected_brevity,
        "actual_actions": actions,
        "actual_brevities": brevities,
        "action_pass": action_pass,
        "brevity_pass": brevity_pass,
        "passed": action_pass and brevity_pass,
        "avg_ms": round(sum(r["elapsed_ms"] for r in results) / len(results), 1),
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict[str, Any]]) -> None:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n{'=' * 80}")
    print(f"  RESULTS: {passed}/{total} passed")
    print(f"{'=' * 80}\n")

    # Group by tag
    tags = sorted(set(r["tag"] for r in results))
    for tag in tags:
        tag_results = [r for r in results if r["tag"] == tag]
        tag_passed = sum(1 for r in tag_results if r["passed"])
        status = "PASS" if tag_passed == len(tag_results) else "FAIL"
        print(f"  [{status}] {tag} ({tag_passed}/{len(tag_results)})")

        for r in tag_results:
            icon = "  ok" if r["passed"] else "FAIL"
            msg = r["message"][:60]
            action_str = "/".join(sorted(set(r["actual_actions"])))
            brevity_str = "/".join(sorted(set(r["actual_brevities"])))

            parts = [f"action={action_str}"]
            if not r["action_pass"]:
                parts.append(f"(expected {r['expected_action']})")
            if r["expected_brevity"]:
                parts.append(f"brevity={brevity_str}")
                if not r["brevity_pass"]:
                    parts.append(f"(expected {r['expected_brevity']})")

            detail = " ".join(parts)
            print(f"    {icon}  {msg:<60}  {detail}")

        print()

    # Failures detail
    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"{'─' * 80}")
        print("  FAILURES:\n")
        for r in failures:
            print(f"  [{r['tag']}] {r['message']}")
            if r["note"]:
                print(f"    note: {r['note']}")
            print(f"    expected: action={r['expected_action']}, brevity={r['expected_brevity']}")
            print(f"    actual:   action={r['actual_actions']}, brevity={r['actual_brevities']}")
            print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Test bench for conversation-intelligence classification.",
    )
    parser.add_argument(
        "--tag",
        help="Run only cases with this tag.",
    )
    parser.add_argument(
        "--repeat",
        type=int,
        default=1,
        help="Repeat each case N times (consistency check).",
    )
    parser.add_argument(
        "--message",
        help="Ad-hoc message (no expected value, just shows classification).",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Print full JSON per case.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required.", file=sys.stderr)
        return 2

    # Ad-hoc mode
    if args.message:
        for i in range(args.repeat):
            result = _classify(args.message)
            result["run"] = i + 1
            if args.pretty:
                print(json.dumps(result, indent=2, sort_keys=True))
            else:
                print(json.dumps(result, separators=(",", ":"), sort_keys=True))
        return 0

    # Fixture mode
    cases = TEST_CASES
    if args.tag:
        cases = [c for c in cases if c.tag == args.tag]
        if not cases:
            available = sorted(set(c.tag for c in TEST_CASES))
            print(f"No cases for tag '{args.tag}'. Available: {', '.join(available)}", file=sys.stderr)
            return 2

    print(f"Running {len(cases)} cases x {args.repeat} repeat(s)...\n")
    results = []
    for i, case in enumerate(cases, 1):
        sys.stdout.write(f"  [{i}/{len(cases)}] {case.message[:60]}...")
        sys.stdout.flush()
        r = _run_case(case, args.repeat)
        results.append(r)
        icon = "ok" if r["passed"] else "FAIL"
        print(f" {icon} ({r['avg_ms']}ms)")

        if args.pretty:
            print(json.dumps(r, indent=2, sort_keys=True))

    _print_summary(results)

    failures = sum(1 for r in results if not r["passed"])
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
