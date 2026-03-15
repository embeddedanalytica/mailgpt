"""Eval helpers for the memory refresh eligibility workflow."""

from typing import Any, Callable, Dict, Iterable, List

from skills.memory.eligibility.runner import run_memory_refresh_eligibility


def evaluate_cases(
    cases: Iterable[Dict[str, Any]],
    *,
    evaluator: Callable[[Dict[str, Any]], Dict[str, Any]] = run_memory_refresh_eligibility,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"eligibility case[{index}] must be a dict")
        interaction_context = case.get("interaction_context")
        if not isinstance(interaction_context, dict):
            raise ValueError(f"eligibility case[{index}] interaction_context must be a dict")

        expected = case.get("expected")
        if expected is not None and not isinstance(expected, dict):
            raise ValueError(f"eligibility case[{index}] expected must be a dict when provided")

        actual = evaluator(interaction_context)
        mismatches = {}
        if isinstance(expected, dict):
            for field in ("should_refresh", "reason"):
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
