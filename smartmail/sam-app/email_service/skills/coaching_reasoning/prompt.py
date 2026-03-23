"""Prompt text for the coaching-reasoning workflow."""

from typing import Any, Dict

from prompt_pack_loader import load_coach_reply_prompt_pack
from skills.coaching_reasoning.doctrine import build_doctrine_context_for_brief

_PROMPT_PACK = load_coach_reply_prompt_pack()
_BASE_PROMPT = _PROMPT_PACK["coaching_reasoning"]["base_prompt"]


def build_system_prompt(response_brief: Dict[str, Any]) -> str:
    """Assemble the system prompt with selectively loaded doctrine."""
    doctrine = build_doctrine_context_for_brief(response_brief)
    return f"{_BASE_PROMPT}\n\nCoaching methodology:\n{doctrine}"
