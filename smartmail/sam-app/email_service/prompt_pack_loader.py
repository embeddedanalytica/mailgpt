"""Helpers for loading versioned prompt-pack artifacts."""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict


PROMPT_PACKS_ROOT = Path(__file__).resolve().parent / "prompt_packs"
DEFAULT_COACH_REPLY_PROMPT_PACK_VERSION = "v1"
ACTIVE_VERSION_FILE_NAME = "ACTIVE_VERSION"


class PromptPackError(RuntimeError):
    """Raised when a prompt-pack artifact cannot be loaded."""


def get_active_coach_reply_prompt_pack_version() -> str:
    raw = os.getenv("COACH_REPLY_PROMPT_PACK_VERSION", "").strip()
    if raw:
        return raw
    active_version_path = PROMPT_PACKS_ROOT / "coach_reply" / ACTIVE_VERSION_FILE_NAME
    if active_version_path.exists():
        value = active_version_path.read_text(encoding="utf-8").strip()
        if value:
            return value
    return DEFAULT_COACH_REPLY_PROMPT_PACK_VERSION


def _load_json(path: Path) -> Dict[str, Any]:
    if not path.exists():
        raise PromptPackError(f"prompt-pack artifact missing: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PromptPackError(f"prompt-pack artifact invalid JSON: {path}: {exc.msg}") from exc
    if not isinstance(payload, dict):
        raise PromptPackError(f"prompt-pack artifact must be a JSON object: {path}")
    return payload


def _require_string_list(payload: Dict[str, Any], *, key: str, path: Path) -> list[str]:
    value = payload.get(key)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PromptPackError(f"prompt-pack field {key!r} must be a string list: {path}")
    return value


def _join_lines(payload: Dict[str, Any], *, key: str, path: Path) -> str:
    return "\n".join(_require_string_list(payload, key=key, path=path))


def _load_split_coaching_reasoning(base: Path) -> Dict[str, Any]:
    """Load the three-tier split prompt files for coaching reasoning.

    Returns empty strings/dicts when split files are absent (backward compat).
    """
    result: Dict[str, Any] = {
        "constitution": "",
        "operational_rules": "",
        "reply_mode_rules": {},
    }

    constitution_path = base / "constitution.json"
    operational_path = base / "operational_rules.json"
    reply_mode_path = base / "reply_mode_rules.json"

    if not constitution_path.exists():
        return result

    constitution = _load_json(constitution_path)
    result["constitution"] = _join_lines(constitution, key="lines", path=constitution_path)

    if operational_path.exists():
        operational = _load_json(operational_path)
        result["operational_rules"] = "\n".join([
            _join_lines(operational, key="decision_rules_lines", path=operational_path),
            "",
            _join_lines(operational, key="avoid_list_lines", path=operational_path),
            "",
            _join_lines(operational, key="week_block_lines", path=operational_path),
        ])

    if reply_mode_path.exists():
        reply_modes = _load_json(reply_mode_path)
        result["reply_mode_rules"] = {
            "normal_coaching": _join_lines(reply_modes, key="normal_coaching_lines", path=reply_mode_path),
            "intake": _join_lines(reply_modes, key="intake_lines", path=reply_mode_path),
            "clarification": _join_lines(reply_modes, key="clarification_lines", path=reply_mode_path),
            "lightweight_non_planning": _join_lines(reply_modes, key="lightweight_non_planning_lines", path=reply_mode_path),
        }

    return result


@lru_cache(maxsize=None)
def load_coach_reply_prompt_pack(*, version: str | None = None) -> Dict[str, Any]:
    resolved_version = version or get_active_coach_reply_prompt_pack_version()
    base = PROMPT_PACKS_ROOT / "coach_reply" / resolved_version
    manifest = _load_json(base / "manifest.json")
    response_generation = _load_json(base / "response_generation.json")
    coaching_reasoning = _load_json(base / "coaching_reasoning.json")

    split = _load_split_coaching_reasoning(base)

    return {
        "version": resolved_version,
        "manifest": manifest,
        "response_generation": {
            "directive_system_prompt": _join_lines(
                response_generation,
                key="directive_system_prompt_lines",
                path=base / "response_generation.json",
            ),
        },
        "coaching_reasoning": {
            "base_prompt": _join_lines(
                coaching_reasoning,
                key="base_prompt_lines",
                path=base / "coaching_reasoning.json",
            ),
            **split,
        },
    }
