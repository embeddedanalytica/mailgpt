"""Validation helpers for the response-generation workflow."""

from __future__ import annotations

from typing import Any, Dict

from response_generation_contract import (
    FinalEmailResponse,
    ResponseBrief,
    validate_final_email_response,
    validate_response_brief,
)
from skills.response_generation.errors import ResponseGenerationContractError


def _normalize_optional_memory_artifacts(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Strip empty optional memory artifacts to keep validation idempotent."""
    if not isinstance(payload, dict):
        return payload
    normalized = dict(payload)
    memory_context = normalized.get("memory_context")
    if not isinstance(memory_context, dict):
        return normalized

    cleaned_memory_context = dict(memory_context)
    if cleaned_memory_context.get("continuity_focus") is None:
        cleaned_memory_context.pop("continuity_focus", None)
    if cleaned_memory_context.get("priority_memory_notes") == []:
        cleaned_memory_context.pop("priority_memory_notes", None)
    if cleaned_memory_context.get("supporting_memory_notes") == []:
        cleaned_memory_context.pop("supporting_memory_notes", None)

    normalized["memory_context"] = cleaned_memory_context
    return normalized


def validate_response_generation_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        normalized_payload = _normalize_optional_memory_artifacts(payload)
        validate_response_brief(normalized_payload)
        return ResponseBrief.from_dict(normalized_payload).to_dict()
    except Exception as exc:
        raise ResponseGenerationContractError(str(exc)) from exc


def validate_response_generation_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validate_final_email_response(payload)
        return FinalEmailResponse.from_dict(payload).to_dict()
    except Exception as exc:
        raise ResponseGenerationContractError(str(exc)) from exc
