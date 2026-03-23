#!/usr/bin/env python3
"""Fast prompt quality smoke tests with LLM-as-judge semantic evaluation.

Runs targeted scenarios through real LLM calls (response generation + memory refresh),
then uses an LLM judge to evaluate outputs against semantic criteria.

Usage:
    OPENAI_API_KEY=... python3 tools/prompt_quality_smoketest.py
    OPENAI_API_KEY=... python3 tools/prompt_quality_smoketest.py --scenario RG-NO-INTERROGATION
    OPENAI_API_KEY=... python3 tools/prompt_quality_smoketest.py --verbose
    OPENAI_API_KEY=... python3 tools/prompt_quality_smoketest.py --model gpt-5
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import time
from pathlib import Path
from time import perf_counter
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
EMAIL_SERVICE_PATH = REPO_ROOT / "sam-app" / "email_service"
ARTIFACTS_DIR = Path(__file__).resolve().parent / "artifacts"
if str(EMAIL_SERVICE_PATH) not in sys.path:
    sys.path.insert(0, str(EMAIL_SERVICE_PATH))

# ---------------------------------------------------------------------------
# Judge infrastructure
# ---------------------------------------------------------------------------

JUDGE_SYSTEM_PROMPT = (
    "You are a strict evaluator of an AI coaching system's output.\n"
    "You will receive the scenario context, the input given to the system, "
    "the system's output, and a list of semantic criteria.\n\n"
    "For each criterion, determine if the output PASSES or FAILS.\n"
    "Be strict: if there is any doubt, FAIL.\n"
    "Return JSON matching the provided schema exactly."
)

JUDGE_SCHEMA_NAME = "judge_evaluation"
JUDGE_SCHEMA: dict[str, Any] = {
    "type": "object",
    "additionalProperties": False,
    "required": ["criteria_results"],
    "properties": {
        "criteria_results": {
            "type": "array",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["criterion_index", "passed", "justification"],
                "properties": {
                    "criterion_index": {"type": "integer"},
                    "passed": {"type": "boolean"},
                    "justification": {"type": "string"},
                },
            },
        }
    },
}


def _build_judge_user_message(
    *,
    scenario_name: str,
    system_input: str,
    system_output: str,
    criteria: list[str],
) -> str:
    criteria_block = "\n".join(
        f"{i + 1}. {c}" for i, c in enumerate(criteria)
    )
    return (
        f"Scenario: {scenario_name}\n\n"
        f"Input given to the system:\n{system_input}\n\n"
        f"System output:\n{system_output}\n\n"
        f"Criteria to evaluate:\n{criteria_block}"
    )


def _run_judge(
    *,
    scenario_name: str,
    system_input: str,
    system_output: str,
    criteria: list[str],
    judge_model: str,
) -> list[dict[str, Any]]:
    from skills.runtime import execute_json_schema
    import logging

    logger = logging.getLogger("judge")
    user_msg = _build_judge_user_message(
        scenario_name=scenario_name,
        system_input=system_input,
        system_output=system_output,
        criteria=criteria,
    )
    data, _ = execute_json_schema(
        logger=logger,
        model_name=judge_model,
        system_prompt=JUDGE_SYSTEM_PROMPT,
        user_content=user_msg,
        schema_name=JUDGE_SCHEMA_NAME,
        schema=JUDGE_SCHEMA,
        disabled_message="judge requires live LLM",
        warning_log_name="judge",
    )
    return data["criteria_results"]


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

def _base_brief(*, reply_mode: str = "normal_coaching", inbound_body: str = "") -> dict:
    return {
        "reply_mode": reply_mode,
        "athlete_context": {
            "goal_summary": "Half marathon in 10 weeks",
            "experience_level": "intermediate",
            "structure_preference": "flexibility",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do_planned",
            "clarification_needed": False,
        },
        "validated_plan": {
            "weekly_skeleton": ["easy_aerobic", "tempo", "long_run", "recovery"],
            "plan_summary": "4 days/week: easy, tempo, long, recovery. Building toward half marathon.",
        },
        "delivery_context": {
            "inbound_subject": "Weekly update",
            "inbound_body": inbound_body,
            "selected_model_name": "gpt-5-mini",
            "response_channel": "email",
        },
        "memory_context": {
            "memory_available": True,
            "priority_facts": [],
            "structure_facts": [],
            "context_facts": [],
            "continuity_summary": {
                "summary": "Athlete is in a steady build phase.",
                "last_recommendation": "Continue 4-day rhythm with one quality session.",
                "open_loops": [],
                "updated_at": 1773273600,
            },
            "continuity_focus": "Athlete is in a steady build phase.",
        },
    }


def _base_memory_input(*, hard_constraints: str | None, athlete_message: str) -> dict:
    return {
        "current_backbone": {
            "primary_goal": {"summary": "Half marathon in 10 weeks", "updated_at": 1773100000},
            "weekly_structure": {"summary": "4 days per week: Mon easy, Wed tempo, Sat long, Sun recovery", "updated_at": 1773100000},
            "hard_constraints": {"summary": hard_constraints, "updated_at": 1773100000} if hard_constraints else None,
            "training_preferences": {"summary": "Prefers flexibility over rigid schedules", "updated_at": 1773100000},
        },
        "current_context_notes": [],
        "current_continuity": {
            "summary": "Steady build phase, progressing well.",
            "last_recommendation": "Continue 4-day rhythm.",
            "open_loops": [],
            "updated_at": 1773100000,
        },
        "interaction_context": {
            "athlete_message": athlete_message,
            "coach_reply": "Sounds good — keep the rhythm going this week.",
            "reply_mode": "normal_coaching",
        },
    }


# ---------------------------------------------------------------------------
# Scenario definitions
# ---------------------------------------------------------------------------

SCENARIOS: list[dict[str, Any]] = [
    # --- Response Generation ---
    {
        "id": "RG-NO-INTERROGATION",
        "skill": "response_generation",
        "name": "normal_coaching should not ask questions",
        "input": _base_brief(
            inbound_body="Good week — hit all four sessions, legs felt fresh on the long run. Keeping the same rhythm.",
        ),
        "semantic_criteria": [
            "The reply does NOT ask the athlete any questions (except a single optional sign-off like 'Let me know how it goes')",
            "The reply presents a concrete plan or confirms the current plan directly",
            "The reply does NOT contain numbered lists of questions or 'please confirm' language",
        ],
    },
    {
        "id": "RG-STALE-CONSTRAINT",
        "skill": "response_generation",
        "name": "Coach should not re-emphasize a resolved constraint",
        "input": (lambda: {
            **_base_brief(
                inbound_body="Great news — the hip feels completely normal now. Ran 10 miles yesterday with zero discomfort. Ready to push the pace this week.",
            ),
            "memory_context": {
                "memory_available": True,
                "priority_facts": ["Right hip flexor tightness — avoid speed work"],
                "continuity_summary": {
                    "summary": "Monitoring hip flexor issue, keeping intensity low.",
                    "last_recommendation": "Easy aerobic only until hip settles.",
                    "open_loops": ["How does the hip feel after the long run?"],
                    "updated_at": 1773273600,
                },
                "continuity_focus": "Monitoring hip flexor issue.",
            },
        })(),
        "semantic_criteria": [
            "The reply does NOT warn about, caution about, or emphasize the hip flexor constraint",
            "The reply acknowledges the athlete's positive report about the hip",
            "The reply presents a plan that includes quality/speed work (since the constraint is resolved)",
        ],
    },
    {
        "id": "RG-EMOTIONAL-MATCH",
        "skill": "response_generation",
        "name": "Stressed athlete gets brief acknowledgment, not canned phrase",
        "input": _base_brief(
            inbound_body="Brutal week at work, barely slept, managed one short jog. Feeling pretty defeated about the whole thing.",
        ),
        "semantic_criteria": [
            "The reply opens with a brief, specific acknowledgment of the athlete's stress or difficulty",
            "The opening does NOT use a generic canned phrase like 'Rough week' verbatim",
            "The reply moves to a concrete (likely scaled-back) plan after the acknowledgment",
            "The reply does NOT over-empathize or become therapeutic — keeps it to 1-2 sentences of acknowledgment",
        ],
    },
    {
        "id": "RG-CLARIFICATION-SCOPED",
        "skill": "response_generation",
        "name": "Clarification mode asks only the listed questions",
        "input": {
            "reply_mode": "clarification",
            "athlete_context": {
                "goal_summary": "Get faster at 5k",
                "experience_level": "beginner",
            },
            "decision_context": {
                "clarification_needed": True,
                "clarification_questions": [
                    "What is your target 5k time?",
                    "How many days per week can you train?",
                ],
            },
            "validated_plan": {},
            "delivery_context": {
                "inbound_subject": "Training plan",
                "inbound_body": "I want to get faster at 5k. Can you help?",
                "selected_model_name": "gpt-5-mini",
                "response_channel": "email",
            },
            "memory_context": {
                "memory_available": False,
                "continuity_summary": None,
            },
        },
        "semantic_criteria": [
            "The reply asks about target 5k time (or equivalent phrasing)",
            "The reply asks about available training days (or equivalent phrasing)",
            "The reply does NOT ask additional questions beyond those two topics",
            "The reply does NOT present a training plan or coaching direction",
        ],
    },
    {
        "id": "RG-VARIED-OPENING",
        "skill": "response_generation_pair",
        "name": "Two consecutive replies should have different openings",
        "input": _base_brief(
            inbound_body="Solid week. Four runs, felt good on all of them. Ready for more.",
        ),
        "semantic_criteria": [
            "The two replies start with different opening words/phrases (first 5-10 words differ)",
            "Neither reply starts with 'Hi there'",
            "Neither reply starts with 'Nice work'",
        ],
    },
    # --- Memory Refresh ---
    {
        "id": "MEM-CONSTRAINT-RESOLVED",
        "skill": "memory_refresh",
        "name": "Constraint explicitly resolved by athlete",
        "input": _base_memory_input(
            hard_constraints="Left knee soreness — limit downhill running and plyometrics",
            athlete_message="Knee feels completely normal now. Did a hilly trail run on Saturday, 12 miles, and the knee was rock solid the whole way. No issues at all.",
        ),
        "semantic_criteria": [
            "The output backbone.hard_constraints is either null or does NOT mention knee soreness",
            "The output does NOT invent new constraints that weren't in the input",
        ],
    },
    {
        "id": "MEM-CONSTRAINT-RETAINED-SILENCE",
        "skill": "memory_refresh",
        "name": "Constraint retained when athlete doesn't mention it",
        "input": _base_memory_input(
            hard_constraints="Left knee soreness — limit downhill running and plyometrics",
            athlete_message="Good week overall. Hit all four sessions, the tempo run felt strong. Ready to build more.",
        ),
        "semantic_criteria": [
            "The output backbone.hard_constraints still mentions knee soreness or knee-related limitation",
            "The constraint is NOT dropped just because the athlete didn't mention the knee",
        ],
    },
    {
        "id": "MEM-CONSTRAINT-RETAINED-AMBIGUOUS",
        "skill": "memory_refresh",
        "name": "Constraint retained on general positivity without naming the issue",
        "input": _base_memory_input(
            hard_constraints="Left knee soreness — limit downhill running and plyometrics",
            athlete_message="Everything felt fantastic this week! Best training week in months, nothing hurts, body feels great.",
        ),
        "semantic_criteria": [
            "The output backbone.hard_constraints still mentions knee soreness or knee-related limitation",
            "General positivity ('nothing hurts', 'feels great') did NOT cause the specific knee constraint to be dropped",
        ],
    },
]


# ---------------------------------------------------------------------------
# Runners
# ---------------------------------------------------------------------------

def _run_response_generation(brief: dict, *, model_name: str | None) -> dict:
    from skills.response_generation import run_response_generation_workflow
    return run_response_generation_workflow(brief, model_name=model_name)


def _run_memory_refresh(payload: dict) -> dict:
    from skills.memory.unified.runner import run_candidate_memory_refresh
    return run_candidate_memory_refresh(
        current_memory_notes=payload.get("current_memory_notes", []),
        current_continuity=payload.get("current_continuity"),
        interaction_context=payload["interaction_context"],
    )


def _preview(text: str, max_len: int = 200) -> str:
    collapsed = " ".join(str(text or "").split())
    return collapsed[:max_len] + "..." if len(collapsed) > max_len else collapsed


def _format_output_for_judge(skill: str, output: Any) -> str:
    if skill in ("response_generation", "response_generation_pair"):
        if isinstance(output, list):
            parts = []
            for i, o in enumerate(output):
                parts.append(f"Reply {i + 1}:\n{o.get('final_email_body', '')}")
            return "\n\n".join(parts)
        return str(output.get("final_email_body", ""))
    if skill == "memory_refresh":
        return json.dumps(output, indent=2)
    return json.dumps(output, indent=2)


def _format_input_for_judge(skill: str, inp: Any) -> str:
    if skill in ("response_generation", "response_generation_pair"):
        parts = []
        dc = inp.get("delivery_context", {})
        if dc.get("inbound_body"):
            parts.append(f"Athlete message: {dc['inbound_body']}")
        parts.append(f"Reply mode: {inp.get('reply_mode')}")
        mc = inp.get("memory_context", {})
        if mc.get("priority_facts"):
            parts.append(f"Priority facts: {json.dumps(mc['priority_facts'])}")
        if mc.get("continuity_focus"):
            parts.append(f"Continuity focus: {mc['continuity_focus']}")
        dctx = inp.get("decision_context", {})
        if dctx.get("clarification_questions"):
            parts.append(f"Clarification questions: {json.dumps(dctx['clarification_questions'])}")
        return "\n".join(parts)
    if skill == "memory_refresh":
        parts = []
        bb = inp.get("current_backbone", {})
        hc = bb.get("hard_constraints")
        if hc:
            parts.append(f"Current hard_constraints: {hc.get('summary', hc)}")
        ic = inp.get("interaction_context", {})
        if ic.get("athlete_message"):
            parts.append(f"Athlete message: {ic['athlete_message']}")
        return "\n".join(parts)
    return json.dumps(inp, indent=2)


def _run_single(
    scenario: dict[str, Any],
    *,
    model_name: str | None,
    judge_model: str,
) -> dict[str, Any]:
    """Execute one scenario run: skill call + judge call. Returns a raw single-run dict."""
    skill = scenario["skill"]
    criteria = scenario["semantic_criteria"]

    t0 = perf_counter()
    try:
        if skill == "response_generation":
            output = _run_response_generation(scenario["input"], model_name=model_name)
        elif skill == "response_generation_pair":
            output = [
                _run_response_generation(scenario["input"], model_name=model_name),
                _run_response_generation(scenario["input"], model_name=model_name),
            ]
        elif skill == "memory_refresh":
            output = _run_memory_refresh(scenario["input"])
        else:
            return {"error": f"Unknown skill: {skill}"}
    except Exception as exc:
        return {"error": str(exc)}
    skill_duration = round(perf_counter() - t0, 2)

    t1 = perf_counter()
    try:
        judge_results = _run_judge(
            scenario_name=scenario["name"],
            system_input=_format_input_for_judge(skill, scenario["input"]),
            system_output=_format_output_for_judge(skill, output),
            criteria=criteria,
            judge_model=judge_model,
        )
    except Exception as exc:
        return {"error": f"Judge failed: {exc}"}
    judge_duration = round(perf_counter() - t1, 2)

    return {
        "error": None,
        "output": output,
        "criteria_results": judge_results,
        "skill_duration": skill_duration,
        "judge_duration": judge_duration,
    }


def _consolidate(runs: list[dict[str, Any]], criteria: list[str]) -> list[dict[str, Any]]:
    """Majority-vote consolidation across N runs per criterion index."""
    # Gather all criterion indices seen
    all_indices: set[int] = set()
    for run in runs:
        for cr in run.get("criteria_results", []):
            all_indices.add(cr["criterion_index"])

    consolidated = []
    for idx in sorted(all_indices):
        votes: list[dict[str, Any]] = []
        for run in runs:
            for cr in run.get("criteria_results", []):
                if cr["criterion_index"] == idx:
                    votes.append(cr)
                    break

        pass_count = sum(1 for v in votes if v["passed"])
        fail_count = len(votes) - pass_count
        majority_passed = pass_count > fail_count

        # Justification: collect from failing runs when majority failed, else from passing runs.
        # Always include non-unanimous justifications so the reader can spot disagreement.
        minority_justifications = [
            f"Run {i + 1}: {v['justification']}"
            for i, v in enumerate(votes)
            if v["passed"] != majority_passed
        ]
        representative_justification = (
            "; ".join(minority_justifications) if minority_justifications
            else next((v["justification"] for v in votes), "")
        )

        consolidated.append({
            "criterion_index": idx,
            "passed": majority_passed,
            "votes": {"passed": pass_count, "failed": fail_count},
            "justification": representative_justification,
        })

    return consolidated


def run_scenario(
    scenario: dict[str, Any],
    *,
    runs: int,
    model_name: str | None,
    judge_model: str,
    verbose: bool,
) -> dict[str, Any]:
    skill = scenario["skill"]
    sid = scenario["id"]
    criteria = scenario["semantic_criteria"]
    base = {"id": sid, "name": scenario["name"], "skill": skill, "input": scenario["input"], "criteria": criteria}

    raw_runs = []
    for i in range(runs):
        raw = _run_single(scenario, model_name=model_name, judge_model=judge_model)
        raw_runs.append(raw)
        if raw.get("error"):
            # Surface first hard error immediately
            return {**base, "error": raw["error"], "runs": raw_runs, "criteria_results": []}

    consolidated = _consolidate(raw_runs, criteria)

    return {
        **base,
        "error": None,
        "runs": raw_runs,
        "criteria_results": consolidated,
        "total_skill_duration": round(sum(r["skill_duration"] for r in raw_runs), 2),
        "total_judge_duration": round(sum(r["judge_duration"] for r in raw_runs), 2),
        "verbose": verbose,
    }


# ---------------------------------------------------------------------------
# CLI + reporting
# ---------------------------------------------------------------------------

def print_results(results: list[dict[str, Any]], *, verbose: bool) -> int:
    print("\n=== Prompt Quality Smoke Test ===\n")

    total_criteria = 0
    total_passed = 0
    any_failure = False

    for r in results:
        sid = r["id"]
        name = r.get("name", "")
        print(f"{sid}: {name}")

        if r.get("error"):
            print(f"  [ERROR] {r['error']}")
            any_failure = True
            print()
            continue

        criteria = r.get("criteria", [])
        raw_runs = r.get("runs", [])
        n_runs = len(raw_runs)

        for cr in r["criteria_results"]:
            idx = cr["criterion_index"]
            passed = cr["passed"]
            justification = cr["justification"]
            total_criteria += 1

            criterion_text = criteria[idx] if idx < len(criteria) else f"criterion {idx}"
            votes = cr.get("votes")
            if votes and n_runs > 1:
                vote_tag = f" {votes['passed']}/{n_runs}"
            else:
                vote_tag = ""

            if passed:
                total_passed += 1
                print(f"  [PASS{vote_tag}] {criterion_text}")
                # Show minority justifications even on pass so reader can spot disagreement
                if justification and votes and votes["failed"] > 0:
                    print(f"    ~ {justification}")
            else:
                any_failure = True
                print(f"  [FAIL{vote_tag}] {criterion_text}")
                if justification:
                    print(f"    -> {justification}")

        if verbose and raw_runs:
            for i, run in enumerate(raw_runs):
                output = run.get("output", {})
                label = f"Run {i + 1}" if n_runs > 1 else "Output"
                if isinstance(output, list):
                    for j, o in enumerate(output):
                        print(f"  {label} reply {j + 1}: {_preview(o.get('final_email_body', ''))}")
                elif isinstance(output, dict):
                    if "final_email_body" in output:
                        print(f"  {label}: {_preview(output['final_email_body'])}")
                    elif "backbone" in output:
                        hc = output.get("backbone", {}).get("hard_constraints")
                        print(f"  {label} hard_constraints: {hc}")

        durations = []
        if r.get("total_skill_duration") is not None:
            durations.append(f"skill={r['total_skill_duration']}s")
        if r.get("total_judge_duration") is not None:
            durations.append(f"judge={r['total_judge_duration']}s")
        if n_runs > 1:
            durations.append(f"runs={n_runs}")
        if durations:
            print(f"  ({', '.join(durations)})")
        print()

    print(f"OVERALL: {total_passed}/{total_criteria} passed", end="")
    if any_failure:
        print(" (SOME FAILED)")
    else:
        print(" (ALL PASSED)")

    return 0 if not any_failure else 1


def write_artifact(results: list[dict[str, Any]], run_id: str) -> Path:
    """Write a JSONL artifact with full input/output/judge details for each scenario."""
    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ARTIFACTS_DIR / f"smoketest_{run_id}.jsonl"

    with path.open("w") as f:
        # Header record
        f.write(json.dumps({"phase": "run_start", "run_id": run_id}) + "\n")

        for r in results:
            sid = r["id"]

            if r.get("error"):
                f.write(json.dumps({
                    "phase": "scenario_error",
                    "scenario_id": sid,
                    "scenario_name": r.get("name", ""),
                    "error": r["error"],
                }) + "\n")
                continue

            skill = r.get("skill", "")
            criteria = r.get("criteria", [])
            raw_runs = r.get("runs", [])

            def _flatten_output(output: Any) -> Any:
                if isinstance(output, list):
                    return {f"reply_{i+1}": o.get("final_email_body", "") for i, o in enumerate(output)}
                if isinstance(output, dict) and "final_email_body" in output:
                    return output["final_email_body"]
                return output  # memory refresh — full dict

            def _annotate_criteria(criteria_results: list[dict]) -> list[dict]:
                annotated = []
                for cr in criteria_results:
                    idx = cr["criterion_index"]
                    entry = {
                        "criterion_index": idx,
                        "criterion_text": criteria[idx] if idx < len(criteria) else f"<unknown index {idx}>",
                        "passed": cr["passed"],
                        "justification": cr["justification"],
                    }
                    if "votes" in cr:
                        entry["votes"] = cr["votes"]
                    annotated.append(entry)
                return annotated

            # Individual run records (one per run, with its own raw output + judge)
            for i, run in enumerate(raw_runs):
                run_annotated = _annotate_criteria(run.get("criteria_results", []))
                run_passed = sum(1 for c in run_annotated if c["passed"])
                f.write(json.dumps({
                    "phase": "scenario_run",
                    "scenario_id": sid,
                    "scenario_name": r.get("name", ""),
                    "run_index": i + 1,
                    "run_total": len(raw_runs),
                    "skill": skill,
                    "input_summary": _format_input_for_judge(skill, r.get("input", {})),
                    "llm_output": _flatten_output(run.get("output", {})),
                    "judge_assessment": run_annotated,
                    "summary": f"{run_passed}/{len(run_annotated)} passed",
                    "skill_duration_s": run.get("skill_duration"),
                    "judge_duration_s": run.get("judge_duration"),
                }) + "\n")

            # Consolidated record (majority vote across all runs)
            consolidated_annotated = _annotate_criteria(r.get("criteria_results", []))
            passed_count = sum(1 for c in consolidated_annotated if c["passed"])
            f.write(json.dumps({
                "phase": "scenario_result",
                "scenario_id": sid,
                "scenario_name": r.get("name", ""),
                "skill": skill,
                "input_summary": _format_input_for_judge(skill, r.get("input", {})),
                "consolidated_judge_assessment": consolidated_annotated,
                "summary": f"{passed_count}/{len(consolidated_annotated)} passed (majority of {len(raw_runs)} runs)",
                "total_skill_duration_s": r.get("total_skill_duration"),
                "total_judge_duration_s": r.get("total_judge_duration"),
            }) + "\n")

        # Footer record
        total = sum(len(r.get("criteria_results", [])) for r in results if not r.get("error"))
        passed = sum(
            sum(1 for c in r.get("criteria_results", []) if c["passed"])
            for r in results if not r.get("error")
        )
        f.write(json.dumps({"phase": "run_end", "run_id": run_id, "overall": f"{passed}/{total}"}) + "\n")

    return path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Prompt quality smoke tests with LLM-as-judge.")
    parser.add_argument(
        "--scenario",
        action="append",
        default=[],
        help="Scenario ID filter (repeatable). Runs all if omitted.",
    )
    parser.add_argument(
        "--model",
        help="Model override for the skill under test (not the judge).",
    )
    parser.add_argument(
        "--judge-model",
        default=None,
        help="Model for the LLM judge (defaults to OPENAI_CLASSIFICATION_MODEL).",
    )
    parser.add_argument(
        "--runs",
        type=int,
        default=1,
        metavar="N",
        help="Run each scenario N times and consolidate by majority vote (default: 1).",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Show full LLM output for each scenario.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if not os.getenv("OPENAI_API_KEY", "").strip():
        print("ERROR: OPENAI_API_KEY is required.", file=sys.stderr)
        return 1

    os.environ["ENABLE_LIVE_LLM_CALLS"] = "true"

    ts = int(time.time())
    run_hash = hashlib.md5(str(ts).encode()).hexdigest()[:8]
    run_id = f"{ts}-{run_hash}"

    # Suppress noisy logging from skill runtime
    import logging
    logging.basicConfig(level=logging.WARNING)

    from config import OPENAI_CLASSIFICATION_MODEL
    judge_model = args.judge_model or OPENAI_CLASSIFICATION_MODEL

    # Filter scenarios
    selected = SCENARIOS
    if args.scenario:
        wanted = {s.strip().upper() for s in args.scenario}
        selected = [s for s in SCENARIOS if s["id"].upper() in wanted]
        if not selected:
            print(f"ERROR: No scenarios matched: {args.scenario}", file=sys.stderr)
            return 1

    runs = max(1, args.runs)
    run_label = f"{runs} run{'s' if runs > 1 else ''}"
    print(f"Running {len(selected)} scenario(s) × {run_label}...")

    results = []
    for i, scenario in enumerate(selected, 1):
        print(f"[{i}/{len(selected)}] {scenario['id']}  ({scenario['name']})...", flush=True)
        result = run_scenario(
            scenario,
            runs=runs,
            model_name=args.model,
            judge_model=judge_model,
            verbose=args.verbose,
        )
        if result.get("error"):
            print(f"         ERROR: {result['error']}")
        else:
            crs = result.get("criteria_results", [])
            passed = sum(1 for c in crs if c["passed"])
            skill_t = result.get("total_skill_duration")
            judge_t = result.get("total_judge_duration")
            print(f"         {passed}/{len(crs)} criteria passed  (skill={skill_t}s, judge={judge_t}s, {run_label})")
        results.append(result)

    artifact_path = write_artifact(results, run_id)
    print(f"\nArtifact: {artifact_path}")

    return print_results(results, verbose=args.verbose)


if __name__ == "__main__":
    raise SystemExit(main())
