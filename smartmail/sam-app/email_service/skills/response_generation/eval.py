"""Eval helpers for the response-generation workflow."""

from __future__ import annotations

from typing import Any, Callable, Dict, Iterable, List

from skills.response_generation.runner import run_response_generation_workflow


def evaluate_cases(
    cases: Iterable[Dict[str, Any]],
    *,
    evaluator: Callable[[Dict[str, Any]], Dict[str, Any]] = run_response_generation_workflow,
) -> List[Dict[str, Any]]:
    results: List[Dict[str, Any]] = []
    for index, case in enumerate(cases):
        if not isinstance(case, dict):
            raise ValueError(f"response_generation case[{index}] must be a dict")
        response_brief = case.get("response_brief")
        if not isinstance(response_brief, dict):
            raise ValueError(f"response_generation case[{index}] response_brief must be a dict")

        expected = case.get("expected")
        if expected is not None and not isinstance(expected, dict):
            raise ValueError(
                f"response_generation case[{index}] expected must be a dict when provided"
            )

        actual = evaluator(response_brief)
        if not isinstance(actual, dict):
            raise ValueError(f"response_generation case[{index}] evaluator must return a dict")

        body = str(actual.get("final_email_body", "") or "")
        mismatches: Dict[str, Any] = {}
        if isinstance(expected, dict):
            required_phrases = expected.get("required_phrases", [])
            for phrase in required_phrases:
                if phrase not in body:
                    mismatches.setdefault("required_phrases", []).append(phrase)

            forbidden_phrases = expected.get("forbidden_phrases", [])
            forbidden_hits = [phrase for phrase in forbidden_phrases if phrase in body]
            if forbidden_hits:
                mismatches["forbidden_phrases"] = forbidden_hits

            max_lines = expected.get("max_lines")
            if isinstance(max_lines, int) and len([line for line in body.splitlines() if line.strip()]) > max_lines:
                mismatches["max_lines"] = {
                    "expected_max": max_lines,
                    "actual": len([line for line in body.splitlines() if line.strip()]),
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
