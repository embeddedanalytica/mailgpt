"""Fixture loader for the live athlete simulator benchmark."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH_PATH = REPO_ROOT / "test_bench" / "athlete_agent_bench.md"

REQUIRED_FIELDS = {
    "id",
    "name",
    "athlete_brief",
    "judge_brief",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {
    "opening_message",
    "evaluation_focus",
    "communication_style_preferences",
    "min_turns",
    "max_turns",
}


def extract_json_block(markdown_text: str) -> str:
    match = re.search(r"```json\s*(.*?)```", markdown_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON block found in athlete-agent benchmark fixture.")
    return str(match.group(1))


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _normalize_optional_non_empty_string(value: Any, *, field_name: str) -> str | None:
    if value is None:
        return None
    return _require_non_empty_string(value, field_name=field_name)


def _normalize_string_list(value: Any, *, field_name: str) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list.")
    return [
        _require_non_empty_string(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(value, start=1)
    ]


def _normalize_turn_bound(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer.")
    if value < 1:
        raise ValueError(f"{field_name} must be >= 1.")
    return value


def normalize_scenario(raw: Any, *, seen_ids: set[str], index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario {index} must be an object.")

    unknown_fields = sorted(set(raw.keys()) - ALLOWED_FIELDS)
    if unknown_fields:
        raise ValueError(f"Scenario {index} has unknown fields: {', '.join(unknown_fields)}")

    missing = sorted(REQUIRED_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(f"Scenario {index} is missing fields: {', '.join(missing)}")

    scenario_id = _require_non_empty_string(raw.get("id"), field_name=f"scenario[{index}].id")
    if scenario_id in seen_ids:
        raise ValueError(f"Duplicate scenario id: {scenario_id}")
    seen_ids.add(scenario_id)

    min_turns = _normalize_turn_bound(raw.get("min_turns"), field_name=f"{scenario_id}.min_turns")
    max_turns = _normalize_turn_bound(raw.get("max_turns"), field_name=f"{scenario_id}.max_turns")
    if min_turns is not None and max_turns is not None and min_turns > max_turns:
        raise ValueError(f"{scenario_id} min_turns cannot be greater than max_turns.")

    return {
        "id": scenario_id,
        "name": _require_non_empty_string(raw.get("name"), field_name=f"{scenario_id}.name"),
        "athlete_brief": _require_non_empty_string(
            raw.get("athlete_brief"),
            field_name=f"{scenario_id}.athlete_brief",
        ),
        "judge_brief": _require_non_empty_string(
            raw.get("judge_brief"),
            field_name=f"{scenario_id}.judge_brief",
        ),
        "opening_message": _normalize_optional_non_empty_string(
            raw.get("opening_message"),
            field_name=f"{scenario_id}.opening_message",
        ),
        "evaluation_focus": _normalize_string_list(
            raw.get("evaluation_focus"),
            field_name=f"{scenario_id}.evaluation_focus",
        ),
        "communication_style_preferences": _normalize_string_list(
            raw.get("communication_style_preferences"),
            field_name=f"{scenario_id}.communication_style_preferences",
        ),
        "min_turns": min_turns,
        "max_turns": max_turns,
    }


def load_athlete_agent_bench_scenarios(
    bench_path: Path | str = DEFAULT_BENCH_PATH,
) -> List[Dict[str, Any]]:
    path = Path(bench_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Athlete-agent benchmark fixture not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    json_blob = extract_json_block(markdown)
    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON block in athlete-agent benchmark fixture: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Athlete-agent benchmark JSON block must be a non-empty array.")

    seen_ids: set[str] = set()
    return [
        normalize_scenario(item, seen_ids=seen_ids, index=index)
        for index, item in enumerate(payload, start=1)
    ]
