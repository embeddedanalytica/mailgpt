"""Prompt text for the response-generation workflow."""

from prompt_pack_loader import load_coach_reply_prompt_pack


_PROMPT_PACK = load_coach_reply_prompt_pack()
SYSTEM_PROMPT = _PROMPT_PACK["response_generation"]["system_prompt"]
DIRECTIVE_SYSTEM_PROMPT = _PROMPT_PACK["response_generation"]["directive_system_prompt"]
