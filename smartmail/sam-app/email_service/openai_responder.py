"""
LLM layer: OpenAI-based reply generation, profile extraction, and intention check.
All model calls and prompts live here so you can improve the LLM flow in one place.
"""
import json
import logging
import os
from typing import Any, Dict

try:
    import openai  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - exercised indirectly via tests
    openai = None  # type: ignore

from config import OPENAI_GENERIC_MODEL, NO_RESPONSE_MODEL, PROFILE_EXTRACTION_MODEL

logger = logging.getLogger(__name__)
if openai is not None:
    openai.api_key = os.getenv("OPENAI_API_KEY")


class OpenAIResponder:
    """Handles generating AI responses using OpenAI."""

    SYSTEM_PROMPT = (
        "You are an AI assistant that writes natural, friendly, and conversational replies to user emails as part of an ongoing email thread. "
        "The emails are shown in reverse-chronological order (latest message at the top). To understand the conversation correctly, "
        "**you must read the messages from bottom to top** (oldest to newest). Your primary task is to identify the latest user question or intent "
        "and craft a warm, concise, and helpful response that continues the conversation fluidly.\n\n"
        "DO:\n"
        "- Focus on the most recent message at the top while using the full context below to inform your reply.\n"
        "- Match the tone of the sender: keep it casual for informal emails, and provide more structure and depth for serious or high-stakes inquiries.\n"
        "- Acknowledge the user's intent naturally—avoid repeating their message, and instead build on it to move the conversation forward.\n"
        "- Keep responses short, clear, and engaging—like a thoughtful human assistant would.\n"
        "- Ask for clarification if the user's message is vague or ambiguous.\n\n"
        "DO NOT:\n"
        "- Greet the user again (e.g., 'Hi there,' 'Hope you're well')—this is a thread.\n"
        "- Summarize previous messages or repeat earlier context unless asked explicitly.\n"
        "- Use robotic, formal, or overly verbose language.\n"
        "- Use phrases like 'Extracted Question' or 'Here is your response.'\n\n"
        "Your tone should be warm and conversational. Focus on clarity, empathy, and being genuinely helpful while respecting the context of an ongoing thread."
    )

    NOT_REGISTERED_SYSTEM_PROMPT = (
        "You must inform the user that they are not registered and cannot receive a response. "
        "Be polite, acknowledge their email, and direct them to register at [https://geniml.com]. "
        "Do not repeat the link more than once. End the response by inviting them to ask again after registration."
    )

    SYSTEM_PROMPT_FOR_INTENTION_CHECK = (
        "You are an intelligent email assistant analyzing the latest email in a thread to determine if an AI-generated "
        "response is necessary. Only evaluate content **until the first occurrence of common delimiters** such as `---`, `FROM`, `TO`, or `SUBJECT`, "
        "which indicate the start of previous messages. Do not analyze the full thread.\n\n"
        "Reply with ONLY `true` (if AI should respond) or `false` (if AI should NOT respond). No explanations.\n\n"
        "**Respond `true` if the latest email:**\n"
        "- Contains a clear, AI-answerable question.\n"
        "- Explicitly requests AI's help, advice, or factual input.\n"
        "- Introduces a new topic or request that AI has not yet addressed.\n\n"
        "**Respond `false` if the latest email:**\n"
        "- Is part of a human-to-human conversation without requesting AI input.\n"
        "- Replies to AI's previous response without adding a new question or request.\n"
        "- Mentions AI but does not ask for assistance.\n"
        "- Is a confirmation, acknowledgment, or casual remark (e.g., 'Thanks!', 'Got it!').\n"
        "- Is redundant, meaning AI has already answered a similar query in one of the last three messages."
    )

    @staticmethod
    def generate_response(subject: str, body: str) -> str:
        """Generates an AI-crafted email response based on the original email content."""
        try:
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_GENERIC_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT},
                    {"role": "user", "content": f"{subject}\n{body}"},
                ],
            )
            ai_reply = response.choices[0].message.content.strip()
            signature = (
                "<br><br>Truly yours,<br>"
                "GeniML<br>"
                '<a href="https://geniml.com">geniml.com</a>'
            )
            disclaimer = (
                "<br><br><hr><small>"
                "Disclaimer: This response is AI-generated and may contain errors. "
                "Please verify all information provided. For feedback, email "
                '<a href="mailto:feedback@geniml.com">feedback@geniml.com</a>.'
                "</small><hr>"
            )
            return ai_reply + signature + disclaimer
        except Exception as e:
            logger.error("Error generating OpenAI response: %s", e)
            return "I'm sorry, but I couldn't generate a response at this time."

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
            return response.choices[0].message.content.strip() + "\n\nTruly yours,\nGeniML\nhttps://geniml.com"
        except Exception as e:
            logger.error("Error generating OpenAI response: %s", e)
            return "I'm sorry, but I couldn't generate a response at this time."

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
                temperature=0,
            )
            decision = response.choices[0].message.content.strip().lower()
            logger.info("AI decision: %s", decision)
            return decision == "true"
        except Exception as e:
            logger.error("Error checking AI response necessity: %s", e)
            return False


class ProfileExtractionError(Exception):
    """Raised when the LLM-based profile extraction fails."""


class ProfileExtractor:
    """
    Uses an LLM to extract structured coaching profile fields from an email body.

    The model is expected to return a JSON object with the following optional keys:
    - goal: string
    - weekly_time_budget_minutes: integer (positive)
    - sports: list of strings
    - goal_unknown: boolean
    - weekly_time_budget_unknown: boolean
    - sports_unknown: boolean
    """

    SYSTEM_PROMPT = (
        "You are a personal coach assistant that reads user's email and extracts ONLY the user's "
        "training context needed for coaching. The email may contain a thread in reverse chronological order. You must read the thread from bottom to top to best capture the user's training goal and intent.\n\n"
        "Return a single JSON object with up to these keys:\n"
        "- goal: string | null\n"
        "- weekly_time_budget_minutes: integer | null (total minutes per week)\n"
        "- sports: array of strings | null (each sport name, e.g., \"running\")\n"
        "- goal_unknown: boolean\n"
        "- weekly_time_budget_unknown: boolean\n"
        "- sports_unknown: boolean\n\n"
        "Rules:\n"
        "- If the user explicitly indicates \"unknown\", \"not sure\", \"skip\", or similar for a field, "
        "  set the corresponding *_unknown flag to true.\n"
        "- Do NOT infer details that are not clearly stated.\n"
        "- If a field is not mentioned, either omit it or set it to null.\n"
        "- The response MUST be valid JSON and MUST NOT contain any explanatory text."
    )

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
