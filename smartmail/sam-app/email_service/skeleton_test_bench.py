"""Test bench for weekly skeleton generation.

Demonstrates that build_weekly_skeleton generates from generic templates
and has no mechanism to preserve athlete-agreed session structure.

This is deterministic — no LLM calls. It calls build_weekly_skeleton
directly with realistic inputs and checks whether the output reflects
what an athlete would have agreed to.

Usage:
    python3 skeleton_test_bench.py
    python3 skeleton_test_bench.py --tag overwrite
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from rule_engine import build_weekly_skeleton


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


def _checkin(
    *,
    days_available: int = 4,
    time_bucket: str = "",
) -> Dict[str, Any]:
    c: Dict[str, Any] = {"week_start": "2026-03-23"}
    if days_available:
        c["days_available"] = days_available
    if time_bucket:
        c["time_bucket"] = time_bucket
    return c


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
    effective_performance_intent: bool
    rule_state: Dict[str, Any]
    athlete_agreed_sessions: List[str]
    note: str = ""


TEST_CASES: List[TestCase] = [
    # --- Run 1 scenario: athlete agreed 4 runs Mon/Tue/Thu/Sat ---
    TestCase(
        tag="overwrite",
        description="Runner agreed 4 runs/week (Mon/Tue/Thu/Sat) — skeleton ignores this",
        profile=_profile(time_bucket="4_6h", main_sport_current="running"),
        checkin=_checkin(days_available=4),
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        effective_performance_intent=False,
        rule_state={},
        athlete_agreed_sessions=[
            "easy_aerobic_30min_mon",
            "easy_aerobic_25min_plus_mobility_tue",
            "easy_aerobic_35min_thu",
            "long_run_75min_sat",
        ],
        note="athlete negotiated specific days and durations — skeleton has no input for this",
    ),
    TestCase(
        tag="overwrite",
        description="Same runner, second mutate pass — skeleton regenerates from scratch",
        profile=_profile(time_bucket="4_6h", main_sport_current="running"),
        checkin=_checkin(days_available=4),
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        effective_performance_intent=False,
        rule_state={"phase_risk_time_last_6": [{"phase": "base", "risk_flag": "green"}]},
        athlete_agreed_sessions=[
            "easy_aerobic_30min_mon",
            "easy_aerobic_25min_plus_mobility_tue",
            "easy_aerobic_35min_thu",
            "long_run_75min_sat",
        ],
        note="even with prior state, skeleton is regenerated identically — no memory of agreed plan",
    ),

    # --- Run 2 scenario: triathlete agreed specific multi-sport week ---
    TestCase(
        tag="overwrite",
        description="Triathlete agreed Sat 3.5h ride + Sun 75min run + Fri trainer — skeleton ignores",
        profile=_profile(
            time_bucket="7_10h",
            main_sport_current="triathlon",
            experience_level="advanced",
        ),
        checkin=_checkin(days_available=5),
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        effective_performance_intent=False,
        rule_state={},
        athlete_agreed_sessions=[
            "long_ride_3h30_sat",
            "run_75min_sun",
            "easy_trainer_45min_fri",
            "swim_or_trainer_wed",
            "strength_tue",
        ],
        note="multi-sport week with specific session types and days — skeleton knows none of this",
    ),

    # --- Stability test: identical inputs, identical outputs ---
    TestCase(
        tag="stability",
        description="Same inputs always produce same generic skeleton (no randomness)",
        profile=_profile(time_bucket="4_6h"),
        checkin=_checkin(days_available=4),
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        effective_performance_intent=False,
        rule_state={},
        athlete_agreed_sessions=[],
        note="baseline: confirms skeleton is purely template-driven",
    ),

    # --- Session count mismatch ---
    TestCase(
        tag="count_mismatch",
        description="Athlete agreed 4 sessions but 4_6h template produces different count",
        profile=_profile(time_bucket="4_6h"),
        checkin=_checkin(days_available=4),
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        effective_performance_intent=False,
        rule_state={},
        athlete_agreed_sessions=["run_mon", "run_tue", "run_thu", "run_sat"],
        note="check if template session count even matches athlete's agreed frequency",
    ),

    # --- Risk override on agreed plan ---
    TestCase(
        tag="risk_override",
        description="Athlete has agreed plan but risk goes yellow — skeleton replaces everything",
        profile=_profile(time_bucket="4_6h"),
        checkin=_checkin(days_available=4),
        track="general_moderate_time",
        phase="base",
        risk_flag="yellow",
        effective_performance_intent=False,
        rule_state={},
        athlete_agreed_sessions=[
            "easy_aerobic_30min_mon",
            "easy_aerobic_25min_plus_mobility_tue",
            "easy_aerobic_35min_thu",
            "long_run_75min_sat",
        ],
        note="risk change should adjust intensity, not replace the entire session structure",
    ),

    # --- Time bucket change on agreed plan ---
    TestCase(
        tag="time_bucket_change",
        description="Athlete agreed 4 sessions but profile time_bucket shifts — skeleton changes entirely",
        profile=_profile(time_bucket="7_10h"),
        checkin=_checkin(days_available=4),
        track="general_moderate_time",
        phase="base",
        risk_flag="green",
        effective_performance_intent=False,
        rule_state={},
        athlete_agreed_sessions=[
            "easy_aerobic_30min_mon",
            "easy_aerobic_25min_plus_mobility_tue",
            "easy_aerobic_35min_thu",
            "long_run_75min_sat",
        ],
        note="time bucket change produces a completely different skeleton regardless of agreements",
    ),
]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

def _run_case(case: TestCase) -> Dict[str, Any]:
    result = build_weekly_skeleton(
        profile=case.profile,
        checkin=case.checkin,
        track=case.track,
        phase=case.phase,
        risk_flag=case.risk_flag,
        effective_performance_intent=case.effective_performance_intent,
        rule_state=case.rule_state,
    )
    skeleton = result["weekly_skeleton"]
    agreed_count = len(case.athlete_agreed_sessions)
    skeleton_count = len(skeleton)

    # Check: does the skeleton have any awareness of agreed sessions?
    # (It can't — there's no input for it. This documents the gap.)
    has_agreed_input = False  # build_weekly_skeleton has no parameter for agreed sessions

    count_matches = agreed_count == skeleton_count if agreed_count > 0 else True

    return {
        "tag": case.tag,
        "description": case.description,
        "note": case.note,
        "skeleton": skeleton,
        "skeleton_count": skeleton_count,
        "agreed_sessions": case.athlete_agreed_sessions,
        "agreed_count": agreed_count,
        "count_matches": count_matches,
        "has_agreed_input": has_agreed_input,
        "adjustments": result["adjustments"],
        "plan_update_status": result["plan_update_status"],
    }


# ---------------------------------------------------------------------------
# Output
# ---------------------------------------------------------------------------

def _print_summary(results: List[Dict[str, Any]]) -> None:
    print(f"\n{'=' * 80}")
    print(f"  SKELETON TEST BENCH — {len(results)} cases")
    print(f"  build_weekly_skeleton has no input for athlete-agreed sessions.")
    print(f"  Every case below shows what the template produces vs what was agreed.")
    print(f"{'=' * 80}\n")

    tags = sorted(set(r["tag"] for r in results))
    for tag in tags:
        tag_results = [r for r in results if r["tag"] == tag]
        print(f"  [{tag}]")

        for r in tag_results:
            count_icon = "ok" if r["count_matches"] else "!!"
            print(f"    {r['description']}")
            print(f"      skeleton ({r['skeleton_count']}): {r['skeleton']}")
            if r["agreed_sessions"]:
                print(f"      agreed   ({r['agreed_count']}): {r['agreed_sessions']}")
                print(f"      count match: [{count_icon}] {r['skeleton_count']} vs {r['agreed_count']}")
            if r["adjustments"]:
                print(f"      adjustments: {r['adjustments']}")
            if r["note"]:
                print(f"      note: {r['note']}")
            print()

    # Summary of the structural gap
    print(f"{'─' * 80}")
    print("  STRUCTURAL GAP:")
    print()
    print("  build_weekly_skeleton() signature:")
    print("    (profile, checkin, track, phase, risk_flag, effective_performance_intent, rule_state)")
    print()
    print("  Missing inputs:")
    print("    - No parameter for athlete-agreed sessions or locked structure")
    print("    - No parameter for negotiated days (Mon/Tue/Thu/Sat)")
    print("    - No parameter for negotiated durations (30min, 75min, 3.5h)")
    print("    - No parameter for sport-specific session types (long ride, brick run, swim)")
    print()
    print("  Every mutate pass regenerates the skeleton from templates,")
    print("  overwriting whatever the coach and athlete agreed on.")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        description="Test bench for weekly skeleton generation.",
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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
