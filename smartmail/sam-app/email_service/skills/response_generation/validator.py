"""Validation helpers for the response-generation workflow."""

from __future__ import annotations

from typing import Any, Dict

from response_generation_contract import (
    FinalEmailResponse,
    WriterBrief,
    validate_final_email_response,
    validate_writer_brief,
)
from skills.response_generation.errors import ResponseGenerationContractError


def validate_response_generation_brief(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validate_writer_brief(payload)
        return WriterBrief.from_dict(payload).to_dict()
    except Exception as exc:
        raise ResponseGenerationContractError(str(exc)) from exc


def validate_response_generation_output(payload: Dict[str, Any]) -> Dict[str, Any]:
    try:
        validate_final_email_response(payload)
        return FinalEmailResponse.from_dict(payload).to_dict()
    except Exception as exc:
        raise ResponseGenerationContractError(str(exc)) from exc
