"""Language rendering boundary for deterministic rule-engine payloads."""

from __future__ import annotations

import json
import logging
from typing import Any, Dict, Optional

try:
    import openai  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    openai = None  # type: ignore

from config import LANGUAGE_RENDER_MODEL

logger = logging.getLogger(__name__)


def _live_llm_enabled() -> bool:
    import os

    return os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"


def _preview_text(value: Any, *, limit: int = 240) -> str:
    text = str(value or "")
    collapsed = " ".join(text.split())
    if len(collapsed) <= limit:
        return collapsed
    return f"{collapsed[:limit]}..."


class LanguageRenderError(Exception):
    """Raised when language-LLM rendering fails."""


class LanguageReplyRenderer:
    """Language LLM boundary for RE4 athlete-facing payload rendering."""

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
