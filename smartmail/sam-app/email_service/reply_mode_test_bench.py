"""Test bench for reply-mode resolution.

Tests the mapping from classification + routing output to the reply_mode
that drives coaching reasoning and response generation.

This is deterministic — no LLM calls. It calls _resolve_reply_mode directly
with realistic router decision dicts and checks the output.

Usage:
    python3 reply_mode_test_bench.py
    python3 reply_mode_test_bench.py --tag confirmations
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from coaching import _resolve_reply_mode


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    tag: str
    description: str
    missing_profile_fields: List[str]
    rule_engine_decision: Optional[Dict[str, Any]]
    expected_reply_mode: str
    note: str = ""


def _router_decision(
    *,
    intent: str = "coaching",
    requested_action: str = "checkin_ack",
    mode: str = "read_only",
    reply_strategy: str = "rule_engine_guided",
    clarification_needed: bool = False,
    engine_output: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """Build a realistic router decision dict."""
    return {
        "intent": intent,
        "requested_action": requested_action,
        "mode": mode,
        "reply_strategy": reply_strategy,
        "clarification_needed": clarification_needed,
        "rule_engine_ran": mode in ("mutate", "read_only"),
        "engine_output": engine_output or {},
        "plan_update_result": None,
        "rule_engine_status": "ok" if mode in ("mutate", "read_only") else "not_applicable",
        "missing_or_low_confidence": [],
    }


TEST_CASES: List[TestCase] = [
    # --- confirmations (the failure mode we identified) ---
    TestCase(
        tag="confirmations",
        description="Simple plan confirmation: checkin_ack + coaching intent",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="checkin_ack",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
        note="currently returns normal_coaching — this is the bug",
    ),
    TestCase(
        tag="confirmations",
        description="Terse acknowledgment: checkin_ack + coaching intent",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="checkin_ack",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
    ),

    # --- training reports (also checkin_ack but with real data) ---
    TestCase(
        tag="training_reports",
        description="Training check-in with data: checkin_ack + coaching intent",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="checkin_ack",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
        note="athlete reported training data, expects ack not full plan rewrite",
    ),

    # --- plan changes (must stay normal_coaching) ---
    TestCase(
        tag="plan_changes",
        description="Explicit plan change: plan_update + coaching intent",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="plan_update",
            mode="mutate",
        ),
        expected_reply_mode="normal_coaching",
        note="this should stay normal_coaching — full plan presentation needed",
    ),

    # --- questions (already works via intent=question) ---
    TestCase(
        tag="questions",
        description="Question: answer_question + question intent",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="question",
            requested_action="answer_question",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
        note="already correct — intent=question hits _READ_ONLY_REPLY_INTENTS",
    ),

    # --- clarifications ---
    TestCase(
        tag="clarifications",
        description="Clarification: clarify_only + coaching intent",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="clarify_only",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
        note="athlete answered a question — should be lightweight, not full plan",
    ),

    # --- special modes (should be unaffected) ---
    TestCase(
        tag="special",
        description="Safety concern",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="safety_concern",
            requested_action="",
            mode="skip",
            reply_strategy="safety_concern",
        ),
        expected_reply_mode="safety_risk_managed",
    ),
    TestCase(
        tag="special",
        description="Off topic",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="off_topic",
            requested_action="",
            mode="skip",
            reply_strategy="off_topic",
        ),
        expected_reply_mode="off_topic_redirect",
    ),
    TestCase(
        tag="special",
        description="Clarification needed (extraction failed)",
        missing_profile_fields=[],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="checkin_ack",
            mode="skip",
            reply_strategy="clarification",
            clarification_needed=True,
        ),
        expected_reply_mode="clarification",
    ),

    # --- intake (profile incomplete) ---
    TestCase(
        tag="intake",
        description="Missing profile fields with coaching intent",
        missing_profile_fields=["primary_goal", "experience_level"],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="plan_update",
            mode="mutate",
        ),
        expected_reply_mode="intake",
    ),
    TestCase(
        tag="intake",
        description="No rule engine decision + missing fields",
        missing_profile_fields=["primary_goal"],
        rule_engine_decision=None,
        expected_reply_mode="intake",
    ),

    # --- injury follow-up edge case ---
    TestCase(
        tag="injury_followup",
        description="Only injury_status missing + question intent → lightweight",
        missing_profile_fields=["injury_status"],
        rule_engine_decision=_router_decision(
            intent="question",
            requested_action="answer_question",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
    ),
    TestCase(
        tag="injury_followup",
        description="Only injury_status missing + coaching/checkin_ack",
        missing_profile_fields=["injury_status"],
        rule_engine_decision=_router_decision(
            intent="coaching",
            requested_action="checkin_ack",
            mode="read_only",
        ),
        expected_reply_mode="lightweight_non_planning",
        note="currently returns normal_coaching — same bug as confirmations",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_case(case: TestCase) -> Dict[str, Any]:
    actual = _resolve_reply_mode(
        missing_profile_fields=case.missing_profile_fields,
        rule_engine_decision=case.rule_engine_decision,
    )
    return {
        "tag": case.tag,
        "description": case.description,
        "note": case.note,
        "expected": case.expected_reply_mode,
        "actual": actual,
        "passed": actual == case.expected_reply_mode,
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

    tags = sorted(set(r["tag"] for r in results))
    for tag in tags:
        tag_results = [r for r in results if r["tag"] == tag]
        tag_passed = sum(1 for r in tag_results if r["passed"])
        status = "PASS" if tag_passed == len(tag_results) else "FAIL"
        print(f"  [{status}] {tag} ({tag_passed}/{len(tag_results)})")

        for r in tag_results:
            icon = "  ok" if r["passed"] else "FAIL"
            actual_str = r["actual"]
            if not r["passed"]:
                actual_str = f"{r['actual']} (expected {r['expected']})"
            print(f"    {icon}  {r['description']:<55}  → {actual_str}")

        print()

    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"{'─' * 80}")
        print("  FAILURES:\n")
        for r in failures:
            print(f"  [{r['tag']}] {r['description']}")
            if r["note"]:
                print(f"    note: {r['note']}")
            print(f"    expected: {r['expected']}")
            print(f"    actual:   {r['actual']}")
            print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test bench for reply-mode resolution.",
    )
    parser.add_argument("--tag", help="Run only cases with this tag.")
    args = parser.parse_args(argv)

    cases = TEST_CASES
    if args.tag:
        cases = [c for c in cases if c.tag == args.tag]
        if not cases:
            available = sorted(set(c.tag for c in TEST_CASES))
            print(f"No cases for tag '{args.tag}'. Available: {', '.join(available)}", file=sys.stderr)
            return 2

    print(f"Running {len(cases)} cases...\n")
    results = [_run_case(c) for c in cases]
    _print_summary(results)

    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
