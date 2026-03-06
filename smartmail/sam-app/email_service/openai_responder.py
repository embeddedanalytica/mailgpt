"""
LLM layer: OpenAI-based reply generation, profile extraction, and intention check.
All model calls and prompts live here so you can improve the LLM flow in one place.
"""
import json
import logging
import os
from typing import Any, Dict, Optional

try:
    import openai  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly via tests
    openai = None  # type: ignore

from config import OPENAI_GENERIC_MODEL, NO_RESPONSE_MODEL, PROFILE_EXTRACTION_MODEL
from email_copy import AICopy, EmailCopy
from ai_extraction_contract import (
    ALLOWED_EXPERIENCE_LEVELS,
    ALLOWED_MAIN_SPORTS,
    ALLOWED_RECENT_ILLNESS,
    ALLOWED_RISK_CANDIDATES,
    ALLOWED_SCHEDULE_VARIABILITY,
    ALLOWED_STRUCTURE_PREFERENCES,
    ALLOWED_TIME_BUCKETS,
    validate_ai_extraction_payload,
)

logger = logging.getLogger(__name__)
if openai is not None:
    openai.api_key = os.getenv("OPENAI_API_KEY")

_SESSION_CHECKIN_NULLABLE_FIELDS = {
    "risk_candidate",
    "event_date",
    "has_upcoming_event",
    "performance_intent_this_week",
    "break_days",
    "main_sport_current",
}


def _preview_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "")
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}..."


def _top_level_type_map(payload: Dict[str, Any]) -> Dict[str, str]:
    type_map: Dict[str, str] = {}
    for key, value in payload.items():
        if isinstance(value, dict):
            nested = ",".join(f"{k}:{type(v).__name__}" for k, v in sorted(value.items()))
            type_map[key] = f"dict[{nested}]"
        elif isinstance(value, list):
            item_types = ",".join(sorted({type(item).__name__ for item in value})) if value else "empty"
            type_map[key] = f"list[{item_types}]"
        else:
            type_map[key] = type(value).__name__
    return type_map


class OpenAIResponder:
    """Handles generating AI responses using OpenAI."""

    SYSTEM_PROMPT = AICopy.REPLY_SYSTEM_PROMPT
    NOT_REGISTERED_SYSTEM_PROMPT = AICopy.INVITE_SYSTEM_PROMPT
    SYSTEM_PROMPT_FOR_INTENTION_CHECK = AICopy.INTENTION_CHECK_SYSTEM_PROMPT

    @staticmethod
    def generate_response(subject: str, body: str, model_name: Optional[str] = None) -> str:
        """Generates an AI-crafted email response based on the original email content."""
        try:
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            selected_model = str(model_name or OPENAI_GENERIC_MODEL).strip() or OPENAI_GENERIC_MODEL
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT},
                    {"role": "user", "content": f"{subject}\n{body}"},
                ],
            )
            ai_reply = response.choices[0].message.content.strip()
            return ai_reply + AICopy.RESPONSE_SIGNATURE_HTML + AICopy.RESPONSE_DISCLAIMER_HTML
        except Exception as e:
            logger.error("Error generating OpenAI response: %s", e)
            return EmailCopy.FALLBACK_AI_ERROR_REPLY

    @staticmethod
    def generate_invite_response(subject: str, body: str) -> str:
        """Generates an AI-crafted email response inviting a user to register."""
        try:
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=NO_RESPONSE_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.NOT_REGISTERED_SYSTEM_PROMPT},
                    {"role": "user", "content": subject},
                ],
            )
            return response.choices[0].message.content.strip() + AICopy.INVITE_SIGNATURE_TEXT
        except Exception as e:
            logger.error("Error generating OpenAI response: %s", e)
            return EmailCopy.FALLBACK_AI_ERROR_REPLY

    @staticmethod
    def should_ai_respond(
        email_body: str, recipient: str, to_recipients: list, cc_recipients: list
    ) -> bool:
        """
        Determines if AI should respond:
        1. Always respond if the only recipient in 'To' is a geniml.com email.
        2. Otherwise, use OpenAI to classify whether the latest message requests a response.
        """
        to_recipients = [e.lower() for e in to_recipients]
        cc_recipients = [e.lower() for e in cc_recipients]
        recipient = recipient.lower()
        is_only_geniml_recipient = (
            len(to_recipients) == 1 and recipient.endswith("@geniml.com")
        )
        if is_only_geniml_recipient:
            logger.info("Only geniml.com recipient found. AI will respond.")
            return True
        try:
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_GENERIC_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT_FOR_INTENTION_CHECK},
                    {"role": "user", "content": email_body},
                ],
            )
            decision = response.choices[0].message.content.strip().lower()
            logger.info("AI decision: %s", decision)
            return decision == "true"
        except Exception as e:
            logger.error("Error checking AI response necessity: %s", e)
            return False


class ProfileExtractionError(Exception):
    """Raised when the LLM-based profile extraction fails."""


class SessionCheckinExtractionError(Exception):
    """Raised when the LLM-based session check-in extraction fails."""


class ProfileExtractor:
    """
    Uses an LLM to extract structured coaching profile fields from an email body.

    The model is expected to return a JSON object with these keys when available:
    - primary_goal: string | null
    - time_availability: object | null
      - sessions_per_week: integer | null
      - hours_per_week: number | null
    - experience_level: one of beginner|intermediate|advanced|unknown
    - experience_level_note: string | null
    - constraints: array | null
      - each item: {type, summary, severity, active}
    """

    SYSTEM_PROMPT = AICopy.PROFILE_EXTRACTION_SYSTEM_PROMPT

    @staticmethod
    def extract_profile_fields(email_body: str) -> Dict[str, Any]:
        """
        Call the LLM to extract profile fields as a raw dict.

        This is intentionally light on business logic; deeper validation and
        normalization is handled by the profile module.
        """
        try:
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=PROFILE_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": ProfileExtractor.SYSTEM_PROMPT},
                    {"role": "user", "content": email_body},
                ],
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or ""
            data = json.loads(raw_content)
            if not isinstance(data, dict):
                raise ValueError("Profile extraction response is not a JSON object")
            logger.info("Profile extraction response: %s", data)
            return data
        except Exception as e:
            logger.error("Error during OpenAI profile extraction: %s", e)
            raise ProfileExtractionError("LLM profile extraction failed") from e


class SessionCheckinExtractor:
    """
    Uses an LLM to extract structured session check-in fields for the rule engine.
    Output is validated against ai_extraction_contract before returning.
    """

    SYSTEM_PROMPT = (
        f"{AICopy.SESSION_CHECKIN_EXTRACTION_SYSTEM_PROMPT}\n\n"
        "Allowed enums:\n"
        f"- risk_candidate: {sorted(ALLOWED_RISK_CANDIDATES)}\n"
        f"- experience_level: {sorted(ALLOWED_EXPERIENCE_LEVELS)}\n"
        f"- time_bucket: {sorted(ALLOWED_TIME_BUCKETS)}\n"
        f"- main_sport_current: {sorted(ALLOWED_MAIN_SPORTS)} or null\n"
        f"- recent_illness: {sorted(ALLOWED_RECENT_ILLNESS)}\n"
        f"- structure_preference: {sorted(ALLOWED_STRUCTURE_PREFERENCES)}\n"
        f"- schedule_variability: {sorted(ALLOWED_SCHEDULE_VARIABILITY)}\n"
    )

    @staticmethod
    def extract_session_checkin_fields(email_body: str) -> Dict[str, Any]:
        raw_content = ""
        try:
            logger.info(
                "Session check-in extraction request: body_chars=%s body_preview=%s",
                len(str(email_body or "")),
                _preview_text(email_body),
            )
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=PROFILE_EXTRACTION_MODEL,
                messages=[
                    {"role": "system", "content": SessionCheckinExtractor.SYSTEM_PROMPT},
                    {"role": "user", "content": email_body},
                ],
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or ""
            logger.info(
                "Session check-in extraction raw response: chars=%s preview=%s",
                len(raw_content),
                _preview_text(raw_content),
            )
            data = json.loads(raw_content)
            if not isinstance(data, dict):
                raise ValueError("Session check-in extraction response is not a JSON object")
            dropped_none_keys = sorted(
                key
                for key, value in data.items()
                if value is None and key not in _SESSION_CHECKIN_NULLABLE_FIELDS
            )
            if dropped_none_keys:
                data = {
                    key: value
                    for key, value in data.items()
                    if key not in dropped_none_keys
                }
                logger.info(
                    "Session check-in extraction sanitized null keys: dropped=%s",
                    dropped_none_keys,
                )
            logger.info(
                "Session check-in extraction parsed payload: keys=%s field_types=%s",
                sorted(data.keys()),
                _top_level_type_map(data),
            )
            validate_ai_extraction_payload(data)
            logger.info("Session check-in extraction response: %s", data)
            return data
        except Exception as e:
            logger.error(
                "Error during session check-in extraction: %s (raw_response_preview=%s)",
                e,
                _preview_text(raw_content),
            )
            raise SessionCheckinExtractionError(
                "LLM session check-in extraction failed"
            ) from e
