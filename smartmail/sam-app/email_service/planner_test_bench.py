"""Test bench for planner skeleton generation with athlete session preferences.

Sends planner briefs to the live planner LLM and checks whether the output
skeleton respects athlete-stated session preferences over the generic template.

Usage:
    python3 planner_test_bench.py                # run all cases
    python3 planner_test_bench.py --tag runner    # run one category
    python3 planner_test_bench.py --repeat 3      # consistency check
    python3 planner_test_bench.py --pretty        # show full planner output
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from rule_engine import build_weekly_skeleton, build_decision_envelope
from skills.planner.validator import build_planner_brief
from skills.planner.runner import run_planner_workflow


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _profile(
    *,
    time_bucket: str = "4_6h",
    experience_level: str = "intermediate",
    main_sport_current: str = "running",
    structure_preference: str = "structure",
    schedule_variability: str = "low",
) -> Dict[str, Any]:
    return {
        "time_bucket": time_bucket,
        "experience_level": experience_level,
        "main_sport_current": main_sport_current,
        "structure_preference": structure_preference,
        "schedule_variability": schedule_variability,
    }


def _build_brief(
    profile: Dict[str, Any],
    checkin: Dict[str, Any],
    track: str,
    phase: str,
    risk_flag: str,
    rule_state: Dict[str, Any],
    athlete_session_preferences: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Build a planner brief from profile/checkin/track/phase, optionally with preferences."""
    skeleton_data = build_weekly_skeleton(
        profile, checkin, track, phase, risk_flag, False, rule_state,
    )
    envelope = build_decision_envelope(
        profile, checkin, phase, risk_flag, track, False, rule_state,
        fallback_skeleton=skeleton_data["weekly_skeleton"],
        adjustments=skeleton_data["adjustments"],
        plan_update_status="updated",
        today_action="follow_plan",
        routing_context={},
    )
    return build_planner_brief(
        profile, checkin, envelope, rule_state,
        athlete_session_preferences=athlete_session_preferences,
    )


# ---------------------------------------------------------------------------
# Test fixture
# ---------------------------------------------------------------------------

@dataclass
class TestCase:
    tag: str
    description: str
    profile: Dict[str, Any]
    checkin: Dict[str, Any]
    track: str
    phase: str
    risk_flag: str
    rule_state: Dict[str, Any]
    athlete_session_preferences: Optional[List[str]]
    check: Callable[[List[str], str], bool]
    check_description: str
    note: str = ""


def _count_aerobic(skeleton: List[str]) -> int:
    return sum(1 for s in skeleton if s in ("easy_aerobic", "recovery"))


def _has_at_least_n_aerobic(n: int) -> Callable[[List[str], str], bool]:
    def check(skeleton: List[str], rationale: str) -> bool:
        return _count_aerobic(skeleton) >= n
    return check


def _skeleton_len_equals(n: int) -> Callable[[List[str], str], bool]:
    def check(skeleton: List[str], rationale: str) -> bool:
        return len(skeleton) == n
    return check


def _no_change_from_template() -> Callable[[List[str], str], bool]:
    """Expect the planner to produce the standard template (no preferences to override)."""
    def check(skeleton: List[str], rationale: str) -> bool:
        # 4_6h general template: ['easy_aerobic', 'easy_aerobic', 'strength', 'skills']
        return len(skeleton) == 4
    return check


TEST_CASES: List[TestCase] = [
    # --- baseline: no preferences, should match template ---
    TestCase(
        tag="baseline",
        description="No preferences — planner should stay close to template",
        profile=_profile(time_bucket="4_6h"),
        checkin={"days_available": 4, "week_start": "2026-03-23"},
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        rule_state={},
        athlete_session_preferences=None,
        check=_no_change_from_template(),
        check_description="4 sessions total (template default)",
    ),

    # --- runner: 4 runs/week ---
    TestCase(
        tag="runner",
        description="Runner prefers 4 runs/week — planner should produce >= 3 aerobic",
        profile=_profile(time_bucket="4_6h", main_sport_current="running"),
        checkin={"days_available": 4, "week_start": "2026-03-23"},
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        rule_state={},
        athlete_session_preferences=[
            "Prefers 4 runs per week. Weekday runs must finish by 6:45 AM. Usual long run on Saturday morning.",
        ],
        check=_has_at_least_n_aerobic(3),
        check_description="at least 3 aerobic sessions (vs template's 2)",
        note="template produces 2 easy_aerobic + strength + skills; preferences say 4 runs",
    ),
    TestCase(
        tag="runner",
        description="Runner prefers 4 runs/week with Achilles constraint",
        profile=_profile(time_bucket="4_6h", main_sport_current="running"),
        checkin={"days_available": 4, "week_start": "2026-03-23"},
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        rule_state={},
        athlete_session_preferences=[
            "Prefers 4 runs per week. Weekday runs must finish by 6:45 AM.",
            "Achilles tendon history — avoid sudden volume jumps.",
        ],
        check=_has_at_least_n_aerobic(3),
        check_description="at least 3 aerobic sessions even with constraint",
        note="constraint should keep things easy, not reduce session count",
    ),

    # --- triathlete: multi-sport week ---
    TestCase(
        tag="triathlete",
        description="Triathlete prefers 5-session multi-sport week",
        profile=_profile(time_bucket="7_10h", main_sport_current="triathlon", experience_level="advanced"),
        checkin={"days_available": 5, "week_start": "2026-03-23"},
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        rule_state={},
        athlete_session_preferences=[
            "5 sessions per week: long ride Saturday, run Sunday, easy trainer Friday, swim or trainer Wednesday, strength Tuesday.",
        ],
        check=_skeleton_len_equals(5),
        check_description="5 sessions matching athlete's stated structure",
        note="template produces 6 generic sessions; athlete agreed to 5 specific ones",
    ),

    # --- risk override: preferences present but yellow risk ---
    TestCase(
        tag="safety",
        description="Yellow risk with 4-run preference — safety should reduce intensity not count",
        profile=_profile(time_bucket="4_6h", main_sport_current="running"),
        checkin={"days_available": 4, "week_start": "2026-03-23"},
        track="general_moderate_time",
        phase="base",
        risk_flag="yellow",
        rule_state={},
        athlete_session_preferences=[
            "Prefers 4 runs per week.",
        ],
        check=lambda skeleton, _: len(skeleton) == 4 and all(
            s not in ("intervals", "tempo", "threshold", "vo2", "race_sim", "hills_hard")
            for s in skeleton
        ),
        check_description="4 sessions, no hard sessions (yellow risk)",
        note="planner should honor session count but respect risk by keeping everything easy",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_case(case: TestCase, repeats: int) -> Dict[str, Any]:
    results = []
    for _ in range(repeats):
        brief = _build_brief(
            profile=case.profile,
            checkin=case.checkin,
            track=case.track,
            phase=case.phase,
            risk_flag=case.risk_flag,
            rule_state=case.rule_state,
            athlete_session_preferences=case.athlete_session_preferences,
        )
        started = time.perf_counter()
        plan = run_planner_workflow(brief)
        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        skeleton = plan.get("weekly_skeleton", [])
        rationale = plan.get("planner_rationale", "")
        passed = case.check(skeleton, rationale)
        results.append({
            "skeleton": skeleton,
            "rationale": rationale,
            "elapsed_ms": elapsed_ms,
            "passed": passed,
            "source": plan.get("source", "?"),
        })

    all_passed = all(r["passed"] for r in results)
    return {
        "tag": case.tag,
        "description": case.description,
        "note": case.note,
        "check_description": case.check_description,
        "passed": all_passed,
        "runs": results,
        "fallback_skeleton": brief.get("fallback_skeleton", []),
        "athlete_session_preferences": case.athlete_session_preferences,
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict[str, Any]], pretty: bool) -> None:
    passed = sum(1 for r in results if r["passed"])
    total = len(results)

    print(f"\n{'=' * 80}")
    print(f"  PLANNER TEST BENCH: {passed}/{total} passed")
    print(f"{'=' * 80}\n")

    tags = sorted(set(r["tag"] for r in results))
    for tag in tags:
        tag_results = [r for r in results if r["tag"] == tag]
        tag_passed = sum(1 for r in tag_results if r["passed"])
        status = "PASS" if tag_passed == len(tag_results) else "FAIL"
        print(f"  [{status}] {tag} ({tag_passed}/{len(tag_results)})")

        for r in tag_results:
            icon = "  ok" if r["passed"] else "FAIL"
            print(f"    {icon}  {r['description']}")
            print(f"          check: {r['check_description']}")
            print(f"          template:    {r['fallback_skeleton']}")
            for i, run in enumerate(r["runs"]):
                prefix = f"          run {i+1}:" if len(r["runs"]) > 1 else "          planner:"
                run_icon = "ok" if run["passed"] else "!!"
                print(f"          [{run_icon}] {run['skeleton']}  ({run['elapsed_ms']}ms, {run['source']})")
                if pretty and run["rationale"]:
                    print(f"          rationale: {run['rationale'][:200]}")
            if r["athlete_session_preferences"]:
                print(f"          preferences: {r['athlete_session_preferences']}")
            if r["note"]:
                print(f"          note: {r['note']}")
            print()

    failures = [r for r in results if not r["passed"]]
    if failures:
        print(f"{'─' * 80}")
        print("  FAILURES:\n")
        for r in failures:
            print(f"  [{r['tag']}] {r['description']}")
            print(f"    check: {r['check_description']}")
            for i, run in enumerate(r["runs"]):
                if not run["passed"]:
                    print(f"    run {i+1}: {run['skeleton']}")
                    if run["rationale"]:
                        print(f"    rationale: {run['rationale'][:200]}")
            print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test bench for planner skeleton with athlete preferences.",
    )
    parser.add_argument("--tag", help="Run only cases with this tag.")
    parser.add_argument("--repeat", type=int, default=1, help="Repeat each case N times.")
    parser.add_argument("--pretty", action="store_true", help="Show rationale for each run.")
    args = parser.parse_args(argv)

    if not os.getenv("OPENAI_API_KEY"):
        print("OPENAI_API_KEY is required.", file=sys.stderr)
        return 2

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
        sys.stdout.write(f"  [{i}/{len(cases)}] {case.description}...")
        sys.stdout.flush()
        r = _run_case(case, args.repeat)
        results.append(r)
        icon = "ok" if r["passed"] else "FAIL"
        avg_ms = round(sum(run["elapsed_ms"] for run in r["runs"]) / len(r["runs"]), 1)
        print(f" {icon} ({avg_ms}ms)")

    _print_summary(results, pretty=args.pretty)
    return 1 if any(not r["passed"] for r in results) else 0


if __name__ == "__main__":
    raise SystemExit(main())
