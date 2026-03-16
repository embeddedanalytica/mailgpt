"""Response-generation benchmark fixture loader."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from skills.response_generation.validator import validate_response_generation_brief


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH_PATH = REPO_ROOT / "response_generation_quality_bench.md"

REQUIRED_FIELDS = {
    "id",
    "name",
    "response_brief",
}
ALLOWED_FIELDS = REQUIRED_FIELDS | {"review_focus", "notes"}


def extract_json_block(markdown_text: str) -> str:
    match = re.search(r"```json\s*(.*?)```", markdown_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON block found in response-generation benchmark fixture.")
    return str(match.group(1))


def _require_non_empty_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _normalize_review_focus(raw: Any, *, scenario_id: str) -> List[str]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{scenario_id}.review_focus must be a list.")
    normalized = []
    for index, item in enumerate(raw, start=1):
        normalized.append(
            _require_non_empty_string(
                item,
                field_name=f"{scenario_id}.review_focus[{index}]",
            )
        )
    return normalized


def normalize_scenario(raw: Any, *, seen_ids: set[str], index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario {index} must be an object.")

    unknown_fields = sorted(set(raw.keys()) - ALLOWED_FIELDS)
    if unknown_fields:
        raise ValueError(
            f"Scenario {index} has unknown fields: {', '.join(unknown_fields)}"
        )

    missing = sorted(REQUIRED_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(f"Scenario {index} is missing fields: {', '.join(missing)}")

    scenario_id = _require_non_empty_string(raw.get("id"), field_name=f"scenario[{index}].id")
    if scenario_id in seen_ids:
        raise ValueError(f"Duplicate scenario id: {scenario_id}")
    seen_ids.add(scenario_id)

    scenario_name = _require_non_empty_string(
        raw.get("name"),
        field_name=f"{scenario_id}.name",
    )

    response_brief = raw.get("response_brief")
    if not isinstance(response_brief, dict):
        raise ValueError(f"{scenario_id}.response_brief must be an object.")
    try:
        normalized_response_brief = validate_response_generation_brief(response_brief)
    except Exception as exc:
        raise ValueError(f"{scenario_id}.response_brief invalid: {exc}") from exc

    notes = raw.get("notes")
    normalized_notes = None
    if notes is not None:
        normalized_notes = _require_non_empty_string(notes, field_name=f"{scenario_id}.notes")

    return {
        "id": scenario_id,
        "name": scenario_name,
        "response_brief": normalized_response_brief,
        "review_focus": _normalize_review_focus(raw.get("review_focus"), scenario_id=scenario_id),
        "notes": normalized_notes,
    }


def load_response_generation_bench_scenarios(
    bench_path: Path | str = DEFAULT_BENCH_PATH,
) -> List[Dict[str, Any]]:
    path = Path(bench_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Response-generation benchmark fixture not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    json_blob = extract_json_block(markdown)
    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError as exc:
        raise ValueError(
            f"Invalid JSON block in response-generation benchmark fixture: {exc}"
        ) from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Response-generation benchmark JSON block must be a non-empty array.")

    seen_ids: set[str] = set()
    return [
        normalize_scenario(item, seen_ids=seen_ids, index=index)
        for index, item in enumerate(payload, start=1)
    ]
