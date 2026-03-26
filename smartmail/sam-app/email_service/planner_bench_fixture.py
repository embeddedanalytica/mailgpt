"""Planner benchmark fixture loading and planner brief construction."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

from rule_engine import build_decision_envelope
from skills.planner import build_planner_brief

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH_PATH = REPO_ROOT / "test_bench" / "plan_test_bench.md"

REQUIRED_FIELDS = {
    "id",
    "name",
    "profile",
    "checkin",
    "phase",
    "risk_flag",
    "track",
    "effective_performance_intent",
    "fallback_skeleton",
    "required_goal_tokens",
}


def extract_json_block(markdown_text: str) -> str:
    match = re.search(r"```json\s*(.*?)```", markdown_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON block found in planner benchmark fixture.")
    return str(match.group(1))


def _validate_string_list(values: Any, *, field_name: str, required: bool = True) -> List[str]:
    if not isinstance(values, list):
        raise ValueError(f"{field_name} must be a list.")
    normalized = [str(item).strip() for item in values if str(item).strip()]
    if required and not normalized:
        raise ValueError(f"{field_name} must include at least one value.")
    return normalized


def normalize_scenario(raw: Any, *, seen_ids: set[str], index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario {index} must be an object.")
    missing = [field for field in REQUIRED_FIELDS if field not in raw]
    if missing:
        raise ValueError(f"Scenario {index} is missing fields: {', '.join(sorted(missing))}")

    scenario_id = str(raw["id"]).strip()
    if not scenario_id:
        raise ValueError(f"Scenario {index} has empty id.")
    if scenario_id in seen_ids:
        raise ValueError(f"Duplicate scenario id: {scenario_id}")
    seen_ids.add(scenario_id)

    scenario_name = str(raw["name"]).strip()
    if not scenario_name:
        raise ValueError(f"Scenario {index} has empty name.")

    profile = raw["profile"]
    checkin = raw["checkin"]
    if not isinstance(profile, dict):
        raise ValueError(f"Scenario {scenario_id} profile must be an object.")
    if not isinstance(checkin, dict):
        raise ValueError(f"Scenario {scenario_id} checkin must be an object.")

    fallback_skeleton = _validate_string_list(
        raw["fallback_skeleton"], field_name=f"{scenario_id}.fallback_skeleton"
    )
    required_goal_tokens = _validate_string_list(
        raw["required_goal_tokens"], field_name=f"{scenario_id}.required_goal_tokens"
    )

    effective_performance_intent = raw["effective_performance_intent"]
    if not isinstance(effective_performance_intent, bool):
        raise ValueError(f"Scenario {scenario_id} effective_performance_intent must be a boolean.")

    adjustments = _validate_string_list(
        raw.get("adjustments", []),
        field_name=f"{scenario_id}.adjustments",
        required=False,
    )
    routing_context = raw.get("routing_context", {})
    if not isinstance(routing_context, dict):
        raise ValueError(f"Scenario {scenario_id} routing_context must be an object.")

    return {
        "id": scenario_id,
        "name": scenario_name,
        "profile": dict(profile),
        "checkin": dict(checkin),
        "phase": str(raw["phase"]).strip(),
        "risk_flag": str(raw["risk_flag"]).strip(),
        "track": str(raw["track"]).strip(),
        "effective_performance_intent": effective_performance_intent,
        "fallback_skeleton": fallback_skeleton,
        "required_goal_tokens": required_goal_tokens,
        "adjustments": adjustments,
        "today_action": str(raw.get("today_action", "do_planned_but_conservative")).strip()
        or "do_planned_but_conservative",
        "routing_context": dict(routing_context),
    }


def load_plan_bench_scenarios(bench_path: Path | str = DEFAULT_BENCH_PATH) -> List[Dict[str, Any]]:
    path = Path(bench_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Planner benchmark fixture not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    json_blob = extract_json_block(markdown)
    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON block in planner benchmark fixture: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Planner benchmark JSON block must be a non-empty array.")

    seen_ids: set[str] = set()
    return [
        normalize_scenario(item, seen_ids=seen_ids, index=index)
        for index, item in enumerate(payload, start=1)
    ]


def build_scenario_brief(scenario: Dict[str, Any]) -> Dict[str, Any]:
    """Build planner brief from a normalized planner benchmark scenario."""
    decision_envelope = build_decision_envelope(
        scenario["profile"],
        scenario["checkin"],
        scenario["phase"],
        scenario["risk_flag"],
        scenario["track"],
        scenario["effective_performance_intent"],
        {},
        fallback_skeleton=scenario["fallback_skeleton"],
        adjustments=list(scenario.get("adjustments", [])),
        plan_update_status="updated",
        today_action=scenario.get("today_action", "do_planned_but_conservative"),
        routing_context=dict(scenario.get("routing_context", {})),
    )
    return build_planner_brief(
        scenario["profile"],
        scenario["checkin"],
        decision_envelope,
        {},
    )
