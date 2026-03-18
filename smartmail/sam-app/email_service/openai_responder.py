"""Compatibility shims for legacy imports.

Active LLM workflows now live in skills/planner and skills/response_generation.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from skills.planner import (
    ProfileExtractionProposalError,
    SessionCheckinExtractionProposalError,
    run_profile_extraction_workflow,
    run_session_checkin_extraction_workflow,
)
from skills.response_generation import LanguageRenderError, LanguageReplyRenderer


class ProfileExtractionError(Exception):
    """Backward-compatible alias for profile extraction failures."""


class SessionCheckinExtractionError(Exception):
    """Backward-compatible alias for session check-in extraction failures."""


class ProfileExtractor:
    """Legacy compatibility wrapper around planner skill workflow."""

    @staticmethod
    def extract_profile_fields(email_body: str) -> Dict[str, Any]:
        try:
            return run_profile_extraction_workflow(email_body)
        except ProfileExtractionProposalError as exc:
            raise ProfileExtractionError("LLM profile extraction failed") from exc


class SessionCheckinExtractor:
    """Legacy compatibility wrapper around planner skill workflow."""

    @staticmethod
    def extract_session_checkin_fields(email_body: str) -> Dict[str, Any]:
        try:
            return run_session_checkin_extraction_workflow(email_body)
        except SessionCheckinExtractionProposalError as exc:
            raise SessionCheckinExtractionError("LLM session check-in extraction failed") from exc


class OpenAIResponder:
    """Retired legacy surface kept only to fail fast if called."""

    @staticmethod
    def generate_response(subject: str, body: str, model_name: Optional[str] = None) -> str:
        del subject, body, model_name
        raise RuntimeError("OpenAIResponder.generate_response is retired; use skills.response_generation")

    @staticmethod
    def generate_invite_response(subject: str, body: str) -> str:
        del subject, body
        raise RuntimeError("OpenAIResponder.generate_invite_response is retired; use transactional reply copy")

    @staticmethod
    def should_ai_respond(
        email_body: str,
        recipient: str,
        to_recipients: list,
        cc_recipients: list,
    ) -> bool:
        del email_body, recipient, to_recipients, cc_recipients
        raise RuntimeError("OpenAIResponder.should_ai_respond is retired")
