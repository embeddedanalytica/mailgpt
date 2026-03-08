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

from config import (
    OPENAI_GENERIC_MODEL,
    NO_RESPONSE_MODEL,
    PROFILE_EXTRACTION_MODEL,
    PLANNING_LLM_MODEL,
    LANGUAGE_RENDER_MODEL,
)
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


def _live_llm_enabled() -> bool:
    return os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"


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


class PlannerProposalError(Exception):
    """Raised when planning-LLM proposal generation fails."""


class LanguageRenderError(Exception):
    """Raised when language-LLM rendering fails."""


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


class PlanningLLM:
    """
    Planning LLM boundary for RE4.
    Input is bounded planner_brief only; no raw state authority.
    """

    SYSTEM_PROMPT = (
        "You are an expert endurance coach that builds a high-quality weekly training skeleton.\n"
        "\n"
        "The user message is a planner_brief JSON object. Treat it as the authoritative planning contract for this week.\n"
        "Return strict JSON only.\n"
        "\n"
        "Your job:\n"
        "- Produce the strongest realistic weekly_skeleton supported by the planner_brief.\n"
        "- Optimize for quality, coherence, realism, safety posture, and goal fit.\n"
        "- Use the contract intelligently instead of mirroring it mechanically.\n"
        "- Do not invent needs, constraints, goals, or session types that are not supported by the planner_brief.\n"
        "\n"
        "Priority order:\n"
        "1. Safety and risk management\n"
        "2. Feasibility within the available session budget\n"
        "3. Coherent week structure\n"
        "4. Goal and track alignment\n"
        "5. Simplicity and believability\n"
        "\n"
        "How to use planner_brief fields:\n"
        "- phase: shapes the level of progression. Base favors durable consistency, build favors purposeful quality, peak_taper favors specificity with restraint, return_to_training favors re-entry and control.\n"
        "- track: defines the strategic context. main_build and main_peak_taper support more goal-specific structure; general_* tracks should stay simpler; return_or_risk_managed should be conservative.\n"
        "- risk_flag: green can support fuller progression, yellow should reduce ambition and complexity, red_a/red_b should strongly favor low-risk simple weeks.\n"
        "- plan_update_status: if the week is unstable or constrained, prefer a conservative and easy-to-execute shape instead of trying to force progression.\n"
        "- weekly_targets.session_mix: the intended training flavor for the week. Use it as directional guidance, not as a mandatory copy task.\n"
        "- track_specific_objective: the main outcome to protect when choosing between plausible weeks.\n"
        "- priority_sessions: preserve these whenever the session budget is tight, unless doing so would create an implausible or risky week.\n"
        "- structure_preference: structure means more predictable sequencing, flexibility means simpler interchangeable sessions, mixed is between the two.\n"
        "- fallback_skeleton: acceptable safe default when the brief does not support a meaningfully better proposal.\n"
        "\n"
        "Planning heuristics:\n"
        "- Prefer one believable coherent week over an ambitious one.\n"
        "- Keep hard sessions scarce and earned.\n"
        "- When risk, disruption, or uncertainty is elevated, reduce complexity before reducing usefulness.\n"
        "- Protect anchor sessions first, then fill the rest with supportive work.\n"
        "- Use easier supporting sessions to create separation around demanding sessions.\n"
        "- If multiple good plans are possible, choose the simpler one.\n"
        "- If the brief is restrictive, close to fallback_skeleton is often the best answer.\n"
        "\n"
        "Valid weekly_skeleton session tokens:\n"
        "- easy_aerobic\n"
        "- recovery\n"
        "- skills\n"
        "- mobility\n"
        "- strength\n"
        "- quality\n"
        "- intervals\n"
        "- tempo\n"
        "- threshold\n"
        "- vo2\n"
        "- race_sim\n"
        "- hills_hard\n"
        "\n"
        "Output contract:\n"
        "- Return exactly one JSON object with keys plan_proposal, rationale, non_binding_state_suggestions.\n"
        "- plan_proposal must contain weekly_skeleton only.\n"
        "- weekly_skeleton must be an ordered list of valid session tokens.\n"
        "- rationale must be short, practical, and explain the main planning choice in one sentence.\n"
        "- non_binding_state_suggestions must be a list of brief optional coaching or state notes, not hard requirements.\n"
        "- Do not include markdown, prose outside JSON, or extra keys.\n"
        "\n"
        "Output example:\n"
        "{"
        '"plan_proposal":{"weekly_skeleton":["easy_aerobic","strength"]},'
        '"rationale":"Short practical reason.",'
        '"non_binding_state_suggestions":["Optional advisory note."]'
        "}"
    )

    @staticmethod
    def propose_plan(
        planner_brief: Dict[str, Any],
        *,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(planner_brief, dict):
            raise PlannerProposalError("planner_brief must be a dict")
        raw_content = ""
        try:
            if not _live_llm_enabled():
                raise RuntimeError("live planner LLM calls are disabled")
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is not configured")
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            selected_model = str(model_name or PLANNING_LLM_MODEL).strip() or PLANNING_LLM_MODEL
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": PlanningLLM.SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": json.dumps(planner_brief, separators=(",", ":"), ensure_ascii=True),
                    },
                ],
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or ""
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict):
                raise ValueError("planner response must be a JSON object")

            plan_proposal = parsed.get("plan_proposal")
            if not isinstance(plan_proposal, dict):
                raise ValueError("plan_proposal must be an object")
            weekly_skeleton = plan_proposal.get("weekly_skeleton")
            if not isinstance(weekly_skeleton, list):
                raise ValueError("plan_proposal.weekly_skeleton must be a list")
            for idx, token in enumerate(weekly_skeleton):
                if not isinstance(token, str) or not token.strip():
                    raise ValueError(f"plan_proposal.weekly_skeleton[{idx}] must be non-empty string")

            rationale = str(parsed.get("rationale", "")).strip()
            suggestions = parsed.get("non_binding_state_suggestions", [])
            if suggestions is None:
                suggestions = []
            if not isinstance(suggestions, list):
                raise ValueError("non_binding_state_suggestions must be a list")
            normalized_suggestions = [str(item).strip() for item in suggestions if str(item).strip()]

            return {
                "plan_proposal": {
                    "weekly_skeleton": [str(item).strip().lower() for item in weekly_skeleton if str(item).strip()],
                },
                "rationale": rationale,
                "non_binding_state_suggestions": normalized_suggestions,
                "model_name": selected_model,
            }
        except Exception as e:
            logger.error(
                "Planning LLM proposal failed: %s (raw_response_preview=%s)",
                e,
                _preview_text(raw_content),
            )
            raise PlannerProposalError("planning llm proposal failed") from e


class LanguageReplyRenderer:
    """
    Language LLM boundary for RE4 athlete-facing payload rendering.
    """

    SYSTEM_PROMPT = (
        "Render athlete-facing coaching copy from validated plan and deterministic guardrails.\n"
        "Return strict JSON only with keys:\n"
        "subject_hint, summary, sessions, plan_focus_line, technique_cue, "
        "recovery_target, if_then_rules, disclaimer_short, safety_note.\n"
        "Never contradict risk constraints or safety notes."
    )

    @staticmethod
    def render_reply(
        validated_plan: Dict[str, Any],
        decision_envelope: Dict[str, Any],
        *,
        model_name: Optional[str] = None,
    ) -> Dict[str, Any]:
        if not isinstance(validated_plan, dict):
            raise LanguageRenderError("validated_plan must be a dict")
        if not isinstance(decision_envelope, dict):
            raise LanguageRenderError("decision_envelope must be a dict")
        raw_content = ""
        try:
            if not _live_llm_enabled():
                raise RuntimeError("live language-render LLM calls are disabled")
            if not os.getenv("OPENAI_API_KEY"):
                raise RuntimeError("OPENAI_API_KEY is not configured")
            if openai is None:
                raise RuntimeError("openai package is not installed")
            client = openai.OpenAI()
            selected_model = str(model_name or LANGUAGE_RENDER_MODEL).strip() or LANGUAGE_RENDER_MODEL
            payload = {
                "validated_plan": validated_plan,
                "decision_envelope": decision_envelope,
            }
            response = client.chat.completions.create(
                model=selected_model,
                messages=[
                    {"role": "system", "content": LanguageReplyRenderer.SYSTEM_PROMPT},
                    {"role": "user", "content": json.dumps(payload, separators=(",", ":"), ensure_ascii=True)},
                ],
                response_format={"type": "json_object"},
            )
            raw_content = response.choices[0].message.content or ""
            parsed = json.loads(raw_content)
            if not isinstance(parsed, dict):
                raise ValueError("rendered payload must be a JSON object")
            return parsed
        except Exception as e:
            logger.error(
                "Language render failed: %s (raw_response_preview=%s)",
                e,
                _preview_text(raw_content),
            )
            raise LanguageRenderError("language render failed") from e
