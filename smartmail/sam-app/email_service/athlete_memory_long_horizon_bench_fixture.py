"""Fixture loader for the long-horizon athlete memory benchmark."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_LONG_HORIZON_BENCH_PATH = REPO_ROOT / "test_bench" / "athlete_memory_long_horizon_bench.md"

REQUIRED_SCENARIO_FIELDS = {
    "id",
    "athlete_name",
    "sport",
    "profile_hint",
    "phases",
    "final_assertions",
}
REQUIRED_PHASE_FIELDS = {
    "phase_id",
    "phase_goal",
    "messages",
    "checkpoint_assertions",
}
REQUIRED_MESSAGE_FIELDS = {
    "step",
    "email",
    "synthetic_coach_reply",
}
REQUIRED_CHECKPOINT_FIELDS = {
    "label",
    "durable_truths",
    "active_context",
    "retired_truths",
    "routine_noise",
    "coach_should_adjust_for",
    "coach_should_not_do",
}
OPTIONAL_CHECKPOINT_FIELDS = {
    "expected_active_storage",
    "expected_retired_storage",
    "expected_compiled_prompt",
    "expected_rejections",
}
ALLOWED_FACT_FIELDS = {
    "label",
    "signals",
    "importance",
}
ALLOWED_IMPORTANCE_VALUES = {"high", "medium", "low"}
ALLOWED_EVENT_TAGS = {
    "routine_checkin",
    "temporary_disruption",
    "durable_change",
    "retirement",
    "memory_pressure",
}
ALLOWED_FINAL_ASSERTION_FIELDS = {
    "final_durable_truths",
    "final_retrieval_support",
    "final_retired_truths",
    "final_active_storage",
    "final_retired_storage",
    "final_compiled_prompt",
    "final_rejections",
}
ALLOWED_STORAGE_ASSERTION_FIELDS = {
    "must_include",
    "must_exclude",
    "max_active_counts",
    "max_retired_counts",
}
ALLOWED_COMPILED_ASSERTION_FIELDS = {
    "must_include",
    "must_exclude",
}
ALLOWED_REJECTION_FIELDS = {
    "label",
    "signals",
    "reason",
}


def extract_json_block(markdown_text: str) -> str:
    match = re.search(r"```json\s*(.*?)```", markdown_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON block found in long-horizon athlete memory benchmark fixture.")
    return str(match.group(1))


def _require_string(value: Any, *, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string.")
    return value.strip()


def _normalize_signal(value: Any, *, field_name: str) -> str:
    if isinstance(value, list):
        normalized = " ".join(str(item).strip().lower() for item in value if str(item).strip())
    else:
        normalized = str(value or "").strip().lower()
    normalized = " ".join(normalized.split())
    if not normalized:
        raise ValueError(f"{field_name} must include non-empty text.")
    return normalized


def _normalize_fact(raw: Any, *, field_name: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    unknown = sorted(set(raw.keys()) - ALLOWED_FACT_FIELDS)
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {', '.join(unknown)}")
    label = _require_string(raw.get("label"), field_name=f"{field_name}.label")
    raw_signals = raw.get("signals")
    if not isinstance(raw_signals, list) or not raw_signals:
        raise ValueError(f"{field_name}.signals must be a non-empty list.")
    signals = [
        _normalize_signal(signal, field_name=f"{field_name}.signals[{index}]")
        for index, signal in enumerate(raw_signals, start=1)
    ]
    importance = str(raw.get("importance", "medium")).strip().lower()
    if importance not in ALLOWED_IMPORTANCE_VALUES:
        raise ValueError(
            f"{field_name}.importance must be one of: {', '.join(sorted(ALLOWED_IMPORTANCE_VALUES))}"
        )
    return {
        "label": label,
        "signals": signals,
        "importance": importance,
    }


def _normalize_fact_list(raw: Any, *, field_name: str) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list.")
    return [
        _normalize_fact(item, field_name=f"{field_name}[{index}]")
        for index, item in enumerate(raw, start=1)
    ]


def _normalize_count_map(
    raw: Any,
    *,
    field_name: str,
) -> Dict[str, int]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    normalized: Dict[str, int] = {}
    for key, value in raw.items():
        name = _require_string(key, field_name=f"{field_name}.key")
        if not isinstance(value, int) or value < 0:
            raise ValueError(f"{field_name}.{name} must be a non-negative integer.")
        normalized[name] = value
    return normalized


def _normalize_storage_assertion(raw: Any, *, field_name: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    unknown = sorted(set(raw.keys()) - ALLOWED_STORAGE_ASSERTION_FIELDS)
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {', '.join(unknown)}")
    return {
        "must_include": _normalize_fact_list(raw.get("must_include", []), field_name=f"{field_name}.must_include"),
        "must_exclude": _normalize_fact_list(raw.get("must_exclude", []), field_name=f"{field_name}.must_exclude"),
        "max_active_counts": _normalize_count_map(raw.get("max_active_counts"), field_name=f"{field_name}.max_active_counts"),
        "max_retired_counts": _normalize_count_map(raw.get("max_retired_counts"), field_name=f"{field_name}.max_retired_counts"),
    }


def _normalize_compiled_prompt_assertion(raw: Any, *, field_name: str) -> Dict[str, Any]:
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    unknown = sorted(set(raw.keys()) - ALLOWED_COMPILED_ASSERTION_FIELDS)
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {', '.join(unknown)}")
    return {
        "must_include": _normalize_fact_list(raw.get("must_include", []), field_name=f"{field_name}.must_include"),
        "must_exclude": _normalize_fact_list(raw.get("must_exclude", []), field_name=f"{field_name}.must_exclude"),
    }


def _normalize_rejections(raw: Any, *, field_name: str) -> List[Dict[str, Any]]:
    if raw is None:
        return []
    if not isinstance(raw, list):
        raise ValueError(f"{field_name} must be a list.")
    normalized: List[Dict[str, Any]] = []
    for index, item in enumerate(raw, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"{field_name}[{index}] must be an object.")
        unknown = sorted(set(item.keys()) - ALLOWED_REJECTION_FIELDS)
        if unknown:
            raise ValueError(f"{field_name}[{index}] contains unknown fields: {', '.join(unknown)}")
        normalized.append(
            {
                "label": _require_string(item.get("label"), field_name=f"{field_name}[{index}].label"),
                "signals": [
                    _normalize_signal(signal, field_name=f"{field_name}[{index}].signals[{signal_index}]")
                    for signal_index, signal in enumerate(item.get("signals", []), start=1)
                ],
                "reason": _require_string(item.get("reason"), field_name=f"{field_name}[{index}].reason"),
            }
        )
    return normalized


def _normalize_checkpoint(raw: Any, *, field_name: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    missing = sorted(REQUIRED_CHECKPOINT_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(f"{field_name} is missing fields: {', '.join(missing)}")
    unknown = sorted(set(raw.keys()) - REQUIRED_CHECKPOINT_FIELDS - OPTIONAL_CHECKPOINT_FIELDS)
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {', '.join(unknown)}")
    return {
        "label": _require_string(raw.get("label"), field_name=f"{field_name}.label"),
        "durable_truths": _normalize_fact_list(
            raw.get("durable_truths"),
            field_name=f"{field_name}.durable_truths",
        ),
        "active_context": _normalize_fact_list(
            raw.get("active_context"),
            field_name=f"{field_name}.active_context",
        ),
        "retired_truths": _normalize_fact_list(
            raw.get("retired_truths"),
            field_name=f"{field_name}.retired_truths",
        ),
        "routine_noise": _normalize_fact_list(
            raw.get("routine_noise"),
            field_name=f"{field_name}.routine_noise",
        ),
        "coach_should_adjust_for": _normalize_fact_list(
            raw.get("coach_should_adjust_for"),
            field_name=f"{field_name}.coach_should_adjust_for",
        ),
        "coach_should_not_do": _normalize_fact_list(
            raw.get("coach_should_not_do"),
            field_name=f"{field_name}.coach_should_not_do",
        ),
        "expected_active_storage": _normalize_storage_assertion(
            raw.get("expected_active_storage"),
            field_name=f"{field_name}.expected_active_storage",
        ),
        "expected_retired_storage": _normalize_storage_assertion(
            raw.get("expected_retired_storage"),
            field_name=f"{field_name}.expected_retired_storage",
        ),
        "expected_compiled_prompt": _normalize_compiled_prompt_assertion(
            raw.get("expected_compiled_prompt"),
            field_name=f"{field_name}.expected_compiled_prompt",
        ),
        "expected_rejections": _normalize_rejections(
            raw.get("expected_rejections"),
            field_name=f"{field_name}.expected_rejections",
        ),
    }


def _normalize_message(raw: Any, *, scenario_id: str, phase_id: str, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{scenario_id}.{phase_id}.messages[{index}] must be an object.")
    missing = sorted(REQUIRED_MESSAGE_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(
            f"{scenario_id}.{phase_id}.messages[{index}] is missing fields: {', '.join(missing)}"
        )
    step = raw.get("step")
    if not isinstance(step, int):
        raise ValueError(f"{scenario_id}.{phase_id}.messages[{index}].step must be an integer.")
    event_tags = raw.get("event_tags", [])
    if not isinstance(event_tags, list):
        raise ValueError(f"{scenario_id}.{phase_id}.messages[{index}].event_tags must be a list.")
    normalized_tags = [str(tag).strip().lower() for tag in event_tags if str(tag).strip()]
    unknown_tags = sorted(set(normalized_tags) - ALLOWED_EVENT_TAGS)
    if unknown_tags:
        raise ValueError(
            f"{scenario_id}.{phase_id}.messages[{index}].event_tags contains unknown values: {', '.join(unknown_tags)}"
        )
    return {
        "step": step,
        "email": _require_string(
            raw.get("email"),
            field_name=f"{scenario_id}.{phase_id}.messages[{index}].email",
        ),
        "synthetic_coach_reply": _require_string(
            raw.get("synthetic_coach_reply"),
            field_name=f"{scenario_id}.{phase_id}.messages[{index}].synthetic_coach_reply",
        ),
        "event_tags": normalized_tags,
    }


def _normalize_phase(raw: Any, *, scenario_id: str, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{scenario_id}.phases[{index}] must be an object.")
    missing = sorted(REQUIRED_PHASE_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(f"{scenario_id}.phases[{index}] is missing fields: {', '.join(missing)}")
    phase_id = _require_string(raw.get("phase_id"), field_name=f"{scenario_id}.phases[{index}].phase_id")
    messages_raw = raw.get("messages")
    if not isinstance(messages_raw, list) or not messages_raw:
        raise ValueError(f"{scenario_id}.{phase_id}.messages must be a non-empty list.")
    messages = [
        _normalize_message(item, scenario_id=scenario_id, phase_id=phase_id, index=message_index)
        for message_index, item in enumerate(messages_raw, start=1)
    ]
    return {
        "phase_id": phase_id,
        "phase_goal": _require_string(
            raw.get("phase_goal"),
            field_name=f"{scenario_id}.{phase_id}.phase_goal",
        ),
        "messages": messages,
        "checkpoint_assertions": _normalize_checkpoint(
            raw.get("checkpoint_assertions"),
            field_name=f"{scenario_id}.{phase_id}.checkpoint_assertions",
        ),
    }


def _normalize_final_assertions(raw: Any, *, field_name: str) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{field_name} must be an object.")
    unknown = sorted(set(raw.keys()) - ALLOWED_FINAL_ASSERTION_FIELDS)
    if unknown:
        raise ValueError(f"{field_name} contains unknown fields: {', '.join(unknown)}")
    return {
        "final_durable_truths": _normalize_fact_list(
            raw.get("final_durable_truths", []),
            field_name=f"{field_name}.final_durable_truths",
        ),
        "final_retrieval_support": _normalize_fact_list(
            raw.get("final_retrieval_support", []),
            field_name=f"{field_name}.final_retrieval_support",
        ),
        "final_retired_truths": _normalize_fact_list(
            raw.get("final_retired_truths", []),
            field_name=f"{field_name}.final_retired_truths",
        ),
        "final_active_storage": _normalize_storage_assertion(
            raw.get("final_active_storage"),
            field_name=f"{field_name}.final_active_storage",
        ),
        "final_retired_storage": _normalize_storage_assertion(
            raw.get("final_retired_storage"),
            field_name=f"{field_name}.final_retired_storage",
        ),
        "final_compiled_prompt": _normalize_compiled_prompt_assertion(
            raw.get("final_compiled_prompt"),
            field_name=f"{field_name}.final_compiled_prompt",
        ),
        "final_rejections": _normalize_rejections(
            raw.get("final_rejections"),
            field_name=f"{field_name}.final_rejections",
        ),
    }


def normalize_scenario(raw: Any, *, seen_ids: set[str], index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"Scenario {index} must be an object.")
    missing = sorted(REQUIRED_SCENARIO_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(f"Scenario {index} is missing fields: {', '.join(missing)}")

    scenario_id = _require_string(raw.get("id"), field_name=f"scenario[{index}].id")
    if scenario_id in seen_ids:
        raise ValueError(f"Duplicate scenario id: {scenario_id}")
    seen_ids.add(scenario_id)

    raw_phases = raw.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise ValueError(f"{scenario_id}.phases must be a non-empty list.")
    phases = [
        _normalize_phase(item, scenario_id=scenario_id, index=phase_index)
        for phase_index, item in enumerate(raw_phases, start=1)
    ]

    steps: List[int] = []
    for phase in phases:
        steps.extend(message["step"] for message in phase["messages"])
    expected_steps = list(range(1, len(steps) + 1))
    if steps != expected_steps:
        raise ValueError(
            f"{scenario_id} messages must use monotonic steps {expected_steps}, got {steps}"
        )
    if len(steps) < 20 or len(steps) > 25:
        raise ValueError(f"{scenario_id} must contain between 20 and 25 total messages.")

    return {
        "id": scenario_id,
        "athlete_name": _require_string(
            raw.get("athlete_name"),
            field_name=f"{scenario_id}.athlete_name",
        ),
        "sport": _require_string(raw.get("sport"), field_name=f"{scenario_id}.sport"),
        "profile_hint": _require_string(
            raw.get("profile_hint"),
            field_name=f"{scenario_id}.profile_hint",
        ),
        "phases": phases,
        "final_assertions": _normalize_final_assertions(
            raw.get("final_assertions"),
            field_name=f"{scenario_id}.final_assertions",
        ),
    }


def load_athlete_memory_long_horizon_bench_scenarios(
    bench_path: Path | str = DEFAULT_LONG_HORIZON_BENCH_PATH,
) -> List[Dict[str, Any]]:
    path = Path(bench_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Long-horizon athlete memory benchmark fixture not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    json_blob = extract_json_block(markdown)
    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON block in long-horizon athlete memory benchmark fixture: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Long-horizon athlete memory benchmark JSON block must be a non-empty array.")

    seen_ids: set[str] = set()
    return [
        normalize_scenario(item, seen_ids=seen_ids, index=index)
        for index, item in enumerate(payload, start=1)
    ]
