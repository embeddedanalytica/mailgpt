"""Fixture loader for the athlete memory benchmark."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_BENCH_PATH = REPO_ROOT / "test_bench" / "athlete_memory_test_bench.md"

REQUIRED_SCENARIO_FIELDS = {
    "id",
    "athlete_name",
    "sport",
    "profile_hint",
    "messages",
    "final_assertions",
}
REQUIRED_MESSAGE_FIELDS = {
    "step",
    "email",
    "synthetic_coach_reply",
    "durable_truths",
    "active_context",
    "retired_truths",
    "routine_noise",
    "coach_should_adjust_for",
    "coach_should_not_do",
}
ALLOWED_FACT_FIELDS = {
    "label",
    "signals",
    "aliases",
    "semantic_signals",
    "importance",
}
ALLOWED_MESSAGE_FIELDS = REQUIRED_MESSAGE_FIELDS | {
    "active_context_mode",
    "message_intent",
}
ALLOWED_FINAL_ASSERTION_FIELDS = {
    "final_durable_truths",
    "final_retrieval_support",
    "final_retired_truths",
}
ALLOWED_IMPORTANCE_VALUES = {"high", "medium", "low"}
ALLOWED_ACTIVE_CONTEXT_MODES = {"required", "acceptable", "expired"}
ALLOWED_MESSAGE_INTENTS = {"routine_checkin", "durable_change", "temporary_disruption", "retirement", "general"}


def extract_json_block(markdown_text: str) -> str:
    match = re.search(r"```json\s*(.*?)```", markdown_text, flags=re.DOTALL)
    if not match:
        raise ValueError("No JSON block found in athlete memory benchmark fixture.")
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
    raw_aliases = raw.get("aliases", [])
    if raw_aliases is None:
        raw_aliases = []
    if not isinstance(raw_aliases, list):
        raise ValueError(f"{field_name}.aliases must be a list.")
    aliases = [
        _normalize_signal(alias, field_name=f"{field_name}.aliases[{index}]")
        for index, alias in enumerate(raw_aliases, start=1)
    ]
    raw_semantic = raw.get("semantic_signals", [])
    if raw_semantic is None:
        raw_semantic = []
    if not isinstance(raw_semantic, list):
        raise ValueError(f"{field_name}.semantic_signals must be a list.")
    semantic_signals = [
        _normalize_signal(signal, field_name=f"{field_name}.semantic_signals[{index}]")
        for index, signal in enumerate(raw_semantic, start=1)
    ]
    importance = str(raw.get("importance", "medium")).strip().lower()
    if importance not in ALLOWED_IMPORTANCE_VALUES:
        raise ValueError(
            f"{field_name}.importance must be one of: {', '.join(sorted(ALLOWED_IMPORTANCE_VALUES))}"
        )
    return {
        "label": label,
        "signals": signals,
        "aliases": aliases,
        "semantic_signals": semantic_signals,
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
    }


def normalize_message(raw: Any, *, scenario_id: str, index: int) -> Dict[str, Any]:
    if not isinstance(raw, dict):
        raise ValueError(f"{scenario_id}.messages[{index}] must be an object.")
    unknown = sorted(set(raw.keys()) - ALLOWED_MESSAGE_FIELDS)
    if unknown:
        raise ValueError(
            f"{scenario_id}.messages[{index}] contains unknown fields: {', '.join(unknown)}"
        )
    missing = sorted(REQUIRED_MESSAGE_FIELDS - set(raw.keys()))
    if missing:
        raise ValueError(
            f"{scenario_id}.messages[{index}] is missing fields: {', '.join(missing)}"
        )
    step = raw.get("step")
    if not isinstance(step, int):
        raise ValueError(f"{scenario_id}.messages[{index}].step must be an integer.")
    active_context = _normalize_fact_list(
        raw.get("active_context"),
        field_name=f"{scenario_id}.messages[{index}].active_context",
    )
    active_context_mode = str(
        raw.get("active_context_mode", "required" if active_context else "acceptable")
    ).strip().lower()
    if active_context_mode not in ALLOWED_ACTIVE_CONTEXT_MODES:
        raise ValueError(
            f"{scenario_id}.messages[{index}].active_context_mode must be one of: {', '.join(sorted(ALLOWED_ACTIVE_CONTEXT_MODES))}"
        )
    message_intent = str(raw.get("message_intent", "general")).strip().lower()
    if message_intent not in ALLOWED_MESSAGE_INTENTS:
        raise ValueError(
            f"{scenario_id}.messages[{index}].message_intent must be one of: {', '.join(sorted(ALLOWED_MESSAGE_INTENTS))}"
        )
    return {
        "step": step,
        "email": _require_string(raw.get("email"), field_name=f"{scenario_id}.messages[{index}].email"),
        "synthetic_coach_reply": _require_string(
            raw.get("synthetic_coach_reply"),
            field_name=f"{scenario_id}.messages[{index}].synthetic_coach_reply",
        ),
        "durable_truths": _normalize_fact_list(
            raw.get("durable_truths"),
            field_name=f"{scenario_id}.messages[{index}].durable_truths",
        ),
        "active_context": active_context,
        "active_context_mode": active_context_mode,
        "retired_truths": _normalize_fact_list(
            raw.get("retired_truths"),
            field_name=f"{scenario_id}.messages[{index}].retired_truths",
        ),
        "routine_noise": _normalize_fact_list(
            raw.get("routine_noise"),
            field_name=f"{scenario_id}.messages[{index}].routine_noise",
        ),
        "coach_should_adjust_for": _normalize_fact_list(
            raw.get("coach_should_adjust_for"),
            field_name=f"{scenario_id}.messages[{index}].coach_should_adjust_for",
        ),
        "coach_should_not_do": _normalize_fact_list(
            raw.get("coach_should_not_do"),
            field_name=f"{scenario_id}.messages[{index}].coach_should_not_do",
        ),
        "message_intent": message_intent,
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

    raw_messages = raw.get("messages")
    if not isinstance(raw_messages, list):
        raise ValueError(f"{scenario_id}.messages must be a list.")
    messages = [
        normalize_message(item, scenario_id=scenario_id, index=item_index)
        for item_index, item in enumerate(raw_messages, start=1)
    ]
    if len(messages) != 5:
        raise ValueError(f"{scenario_id} must contain exactly 5 messages.")
    steps = [message["step"] for message in messages]
    if steps != [1, 2, 3, 4, 5]:
        raise ValueError(f"{scenario_id} messages must use steps [1, 2, 3, 4, 5].")

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
        "messages": messages,
        "final_assertions": _normalize_final_assertions(
            raw.get("final_assertions"),
            field_name=f"{scenario_id}.final_assertions",
        ),
    }


def load_athlete_memory_bench_scenarios(
    bench_path: Path | str = DEFAULT_BENCH_PATH,
) -> List[Dict[str, Any]]:
    path = Path(bench_path).expanduser().resolve()
    if not path.exists():
        raise ValueError(f"Athlete memory benchmark fixture not found: {path}")

    markdown = path.read_text(encoding="utf-8")
    json_blob = extract_json_block(markdown)
    try:
        payload = json.loads(json_blob)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON block in athlete memory benchmark fixture: {exc}") from exc

    if not isinstance(payload, list) or not payload:
        raise ValueError("Athlete memory benchmark JSON block must be a non-empty array.")

    seen_ids: set[str] = set()
    return [
        normalize_scenario(item, seen_ids=seen_ids, index=index)
        for index, item in enumerate(payload, start=1)
    ]
