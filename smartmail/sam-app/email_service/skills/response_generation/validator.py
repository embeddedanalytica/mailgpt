"""Validation helpers for the response-generation workflow."""

from __future__ import annotations

from typing import Any, Dict

from response_generation_contract import (
    FinalEmailResponse,
    ResponseBrief,
    WriterBrief,
    is_directive_input,
    validate_final_email_response,
    validate_response_brief,
    validate_writer_brief,
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

    normalized["memory_context"] = cleaned_memory_context
    return normalized


def validate_response_generation_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        if is_directive_input(payload):
            validate_writer_brief(payload)
            return WriterBrief.from_dict(payload).to_dict()
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
