"""Eval helpers for the planner workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from skills.planner.runner import run_planner_workflow


def evaluate_cases(
    cases: Iterable[Dict[str, Any]],
    *,
    evaluator: Callable[[Dict[str, Any]], Dict[str, Any]] = run_planner_workflow,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"planner case[{index}] must be a dict")
        planner_brief = case.get("planner_brief")
        if not isinstance(planner_brief, dict):
            raise ValueError(f"planner case[{index}] planner_brief must be a dict")

        expected = case.get("expected")
        if expected is not None and not isinstance(expected, dict):
            raise ValueError(f"planner case[{index}] expected must be a dict when provided")

        actual = evaluator(planner_brief)
        mismatches = {}
        if isinstance(expected, dict):
            for field in ("status", "source", "failure_reason", "weekly_skeleton"):
                if field in expected and actual.get(field) != expected[field]:
                    mismatches[field] = {
                        "expected": expected[field],
                        "actual": actual.get(field),
                    }

        results.append(
            {
                "case_id": str(case.get("case_id", index)),
                "actual": actual,
                "matched": not mismatches,
                "mismatches": mismatches,
            }
        )
    return results
