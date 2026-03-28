"""Validate and normalize obedience evaluation LLM output."""

from typing import Any, Dict

from skills.obedience_eval.errors import ObedienceEvalError

_VALID_VIOLATION_TYPES = {
    "reopened_resolved_topic",
    "ignored_latest_constraint",
    "answered_from_stale_context",
    "exceeded_requested_scope",
    "introduced_unsupported_assumption",
    "missed_exact_instruction",
    "physical_presence_implied",
    "metadata_leak",
}


def validate_obedience_eval(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Validate and normalize an LLM-produced obedience evaluation.

    Returns a clean dict. Raises ObedienceEvalError on invalid input.
    """
    if not isinstance(payload, dict):
        raise ObedienceEvalError(f"Expected dict, got {type(payload).__name__}")

    # --- passed ---
    passed = payload.get("passed")
    if not isinstance(passed, bool):
        raise ObedienceEvalError(f"'passed' must be a boolean, got {type(passed).__name__}")

    # --- reasoning ---
    reasoning = payload.get("reasoning")
    if not isinstance(reasoning, str) or not reasoning.strip():
        raise ObedienceEvalError("'reasoning' must be a non-empty string")

    # --- violations ---
    violations = payload.get("violations")
    if not isinstance(violations, list):
        raise ObedienceEvalError(f"'violations' must be a list, got {type(violations).__name__}")

    normalized_violations = []
    for i, v in enumerate(violations):
        if not isinstance(v, dict):
            raise ObedienceEvalError(f"violations[{i}] must be a dict")
        vtype = v.get("violation_type", "")
        if vtype not in _VALID_VIOLATION_TYPES:
            raise ObedienceEvalError(
                f"violations[{i}].violation_type '{vtype}' not in valid set"
            )
        detail = v.get("detail", "")
        if not isinstance(detail, str) or not detail.strip():
            raise ObedienceEvalError(f"violations[{i}].detail must be a non-empty string")
        normalized_violations.append({
            "violation_type": vtype,
            "detail": detail.strip(),
        })

    # --- corrected_email_body ---
    corrected = payload.get("corrected_email_body")
    if corrected is not None:
        if not isinstance(corrected, str) or not corrected.strip():
            raise ObedienceEvalError("'corrected_email_body' must be a non-empty string or null")
        corrected = corrected.strip()

    # --- consistency checks ---
    if passed:
        if normalized_violations:
            raise ObedienceEvalError(
                f"passed=true but {len(normalized_violations)} violations reported"
            )
        if corrected is not None:
            raise ObedienceEvalError("passed=true but corrected_email_body is not null")
    else:
        if not normalized_violations:
            raise ObedienceEvalError("passed=false but no violations reported")
        if not corrected:
            raise ObedienceEvalError("passed=false but corrected_email_body is empty/null")

    return {
        "passed": passed,
        "violations": normalized_violations,
        "corrected_email_body": corrected,
        "reasoning": reasoning.strip(),
    }
