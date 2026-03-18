"""
DynamoDB-backed rule-state contract and helpers for RE1-FU.2.
"""

from __future__ import annotations

from copy import deepcopy
from decimal import Decimal
import logging
import math
import os
from typing import Any, Dict, List

import boto3
from botocore.exceptions import ClientError

logger = logging.getLogger()

dynamodb = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-west-2"))
RULE_STATE_TABLE = os.getenv("RULE_STATE_TABLE_NAME", "rule_state")


class RuleEngineStateError(ValueError):
    """Raised when rule-state inputs are invalid."""


def _require_athlete_id(athlete_id: Any) -> str:
    if not isinstance(athlete_id, str) or not athlete_id.strip():
        raise RuleEngineStateError("athlete_id must be a non-empty string")
    return athlete_id.strip()


def _coerce_int(value: Any, default: int = 0) -> int:
    if isinstance(value, int):
        return value
    if isinstance(value, float) and value.is_integer():
        return int(value)
    if isinstance(value, str):
        text = value.strip()
        if text.lstrip("-").isdigit():
            return int(text)
    return default


def _coerce_float(value: Any, default: float = 0.0) -> float:
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return default
        try:
            return float(text)
        except ValueError:
            return default
    return default


def _coerce_bool(value: Any, default: bool = False) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in {"1", "true", "yes", "y"}
    if isinstance(value, (int, float)):
        return bool(value)
    return default


def _empty_rule_state(athlete_id: str) -> Dict[str, Any]:
    return {
        "athlete_id": athlete_id,
        "weekly_signals_last_4": [],
        "compliance_last_4": [],
        "phase_risk_time_last_6": [],
        "weeks_since_deload": 0,
        "phase_upgrade_streak": 0,
        "main_sport_transition_weeks_remaining": 0,
        "main_sport_frozen_until_week_start": "",
        "last_main_sport_switch_week_start": "",
        "last_main_sport": None,
        "last_updated_week_start": "",
    }


def _normalized_week_start(
    weekly_inputs: Dict[str, Any],
    decisions: Dict[str, Any],
    current_state: Dict[str, Any],
) -> str:
    week_start = str(
        weekly_inputs.get(
            "week_start",
            decisions.get("week_start", current_state.get("last_updated_week_start", "")),
        )
        or ""
    ).strip()
    return week_start


def _upsert_window(
    current_entries: List[Dict[str, Any]],
    new_entry: Dict[str, Any],
    *,
    max_size: int,
) -> List[Dict[str, Any]]:
    week_start = str(new_entry.get("week_start", "")).strip()
    filtered = [entry for entry in current_entries if str(entry.get("week_start", "")).strip() != week_start]
    filtered.append(new_entry)
    filtered.sort(key=lambda entry: str(entry.get("week_start", "")).strip())
    if len(filtered) > max_size:
        filtered = filtered[-max_size:]
    return filtered


def _latest_phase(current_state: Dict[str, Any]) -> str:
    history = current_state.get("phase_risk_time_last_6", [])
    if not isinstance(history, list) or not history:
        return "base"
    last = history[-1]
    if not isinstance(last, dict):
        return "base"
    return str(last.get("phase", "base")).strip() or "base"


def _normalize_state(state: Dict[str, Any], athlete_id: str) -> Dict[str, Any]:
    base = _empty_rule_state(athlete_id)
    if not isinstance(state, dict):
        return base

    normalized = {
        "athlete_id": athlete_id,
        "weekly_signals_last_4": list(state.get("weekly_signals_last_4", [])),
        "compliance_last_4": list(state.get("compliance_last_4", [])),
        "phase_risk_time_last_6": list(state.get("phase_risk_time_last_6", [])),
        "weeks_since_deload": max(0, _coerce_int(state.get("weeks_since_deload"), 0)),
        "phase_upgrade_streak": max(0, _coerce_int(state.get("phase_upgrade_streak"), 0)),
        "main_sport_transition_weeks_remaining": max(
            0, _coerce_int(state.get("main_sport_transition_weeks_remaining"), 0)
        ),
        "main_sport_frozen_until_week_start": str(
            state.get("main_sport_frozen_until_week_start", "") or ""
        ).strip(),
        "last_main_sport_switch_week_start": str(
            state.get("last_main_sport_switch_week_start", "") or ""
        ).strip(),
        "last_main_sport": (
            str(state.get("last_main_sport")).strip().lower()
            if state.get("last_main_sport") is not None
            else None
        ),
        "last_updated_week_start": str(state.get("last_updated_week_start", "") or "").strip(),
    }

    normalized["weekly_signals_last_4"] = [
        entry for entry in normalized["weekly_signals_last_4"] if isinstance(entry, dict)
    ][-4:]
    normalized["compliance_last_4"] = [
        entry for entry in normalized["compliance_last_4"] if isinstance(entry, dict)
    ][-4:]
    normalized["phase_risk_time_last_6"] = [
        entry for entry in normalized["phase_risk_time_last_6"] if isinstance(entry, dict)
    ][-6:]
    return normalized


def _serialize_dynamodb_payload(value: Any) -> Any:
    if isinstance(value, bool):
        return value
    if isinstance(value, Decimal):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise RuleEngineStateError("rule_state cannot contain NaN or Infinity floats")
        return Decimal(str(value))
    if isinstance(value, dict):
        return {key: _serialize_dynamodb_payload(val) for key, val in value.items()}
    if isinstance(value, list):
        return [_serialize_dynamodb_payload(item) for item in value]
    if isinstance(value, tuple):
        return [_serialize_dynamodb_payload(item) for item in value]
    return value


def _normalize_sport(value: Any) -> str:
    text = str(value or "").strip().lower()
    if text in {"", "none", "null"}:
        return ""
    return text


def _sports_minutes_by_sport(weekly_inputs: Dict[str, Any]) -> Dict[str, int]:
    result: Dict[str, int] = {}
    sports_last_week = weekly_inputs.get("sports_last_week", [])
    if not isinstance(sports_last_week, list):
        return result
    for item in sports_last_week:
        if not isinstance(item, dict):
            continue
        sport = _normalize_sport(item.get("sport"))
        if not sport:
            continue
        minutes = max(0, _coerce_int(item.get("minutes"), 0))
        result[sport] = result.get(sport, 0) + minutes
    return result


def load_rule_state(athlete_id: str) -> Dict[str, Any]:
    normalized_athlete_id = _require_athlete_id(athlete_id)
    default_state = _empty_rule_state(normalized_athlete_id)
    try:
        table = dynamodb.Table(RULE_STATE_TABLE)
        response = table.get_item(Key={"athlete_id": normalized_athlete_id})
        item = response.get("Item")
        if not isinstance(item, dict):
            return default_state
        normalized = _normalize_state(item, normalized_athlete_id)
        return deepcopy(normalized)
    except ClientError as exc:
        logger.error("Error loading rule_state athlete_id=%s: %s", normalized_athlete_id, exc)
        return default_state


def update_rule_state(
    athlete_id: str,
    weekly_inputs: Dict[str, Any],
    decisions: Dict[str, Any],
) -> Dict[str, Any]:
    normalized_athlete_id = _require_athlete_id(athlete_id)
    if not isinstance(weekly_inputs, dict):
        raise RuleEngineStateError("weekly_inputs must be a dict")
    if not isinstance(decisions, dict):
        raise RuleEngineStateError("decisions must be a dict")

    current = load_rule_state(normalized_athlete_id)
    week_start = _normalized_week_start(weekly_inputs, decisions, current)
    current["last_updated_week_start"] = week_start

    weekly_signal = {
        "week_start": week_start,
        "pain_score": _coerce_float(weekly_inputs.get("pain_score"), 0.0),
        "energy_score": _coerce_float(weekly_inputs.get("energy_score"), 0.0),
        "sleep_score": _coerce_float(weekly_inputs.get("sleep_score"), 0.0),
        "stress_score": _coerce_float(weekly_inputs.get("stress_score"), 0.0),
        "pain_affects_form": _coerce_bool(weekly_inputs.get("pain_affects_form"), False),
        "sports_minutes_by_sport": _sports_minutes_by_sport(weekly_inputs),
    }
    current["weekly_signals_last_4"] = _upsert_window(
        current.get("weekly_signals_last_4", []),
        weekly_signal,
        max_size=4,
    )

    compliance = {
        "week_start": week_start,
        "planned_sessions_count": max(0, _coerce_int(weekly_inputs.get("planned_sessions_count"), 0)),
        "completed_sessions_count": max(
            0, _coerce_int(weekly_inputs.get("completed_sessions_count"), 0)
        ),
    }
    current["compliance_last_4"] = _upsert_window(
        current.get("compliance_last_4", []),
        compliance,
        max_size=4,
    )

    phase_risk_time = {
        "week_start": week_start,
        "phase": str(decisions.get("phase", _latest_phase(current))).strip() or "base",
        "risk_flag": str(decisions.get("risk_flag", "green")).strip() or "green",
        "time_bucket": str(weekly_inputs.get("time_bucket", decisions.get("time_bucket", ""))).strip(),
    }
    current["phase_risk_time_last_6"] = _upsert_window(
        current.get("phase_risk_time_last_6", []),
        phase_risk_time,
        max_size=6,
    )

    current["weeks_since_deload"] = max(0, _coerce_int(decisions.get("weeks_since_deload"), current.get("weeks_since_deload", 0)))
    current["phase_upgrade_streak"] = max(
        0, _coerce_int(decisions.get("phase_upgrade_streak"), current.get("phase_upgrade_streak", 0))
    )

    switch_applied = _coerce_bool(decisions.get("main_sport_switched"))
    if switch_applied:
        current["last_main_sport"] = _normalize_sport(
            decisions.get("previous_main_sport", current.get("last_main_sport"))
        ) or None
        current["last_main_sport_switch_week_start"] = week_start
        current["main_sport_transition_weeks_remaining"] = 2
        current["main_sport_frozen_until_week_start"] = week_start
    else:
        transition_weeks = max(
            0,
            _coerce_int(
                decisions.get(
                    "main_sport_transition_weeks_remaining",
                    current.get("main_sport_transition_weeks_remaining", 0),
                ),
                0,
            ),
        )
        if transition_weeks > 0:
            transition_weeks -= 1
        current["main_sport_transition_weeks_remaining"] = transition_weeks
        current["main_sport_frozen_until_week_start"] = str(
            decisions.get(
                "main_sport_frozen_until_week_start",
                current.get("main_sport_frozen_until_week_start", ""),
            )
            or ""
        ).strip()

    normalized = _normalize_state(current, normalized_athlete_id)
    try:
        table = dynamodb.Table(RULE_STATE_TABLE)
        table.put_item(Item=_serialize_dynamodb_payload(deepcopy(normalized)))
    except ClientError as exc:
        logger.error("Error updating rule_state athlete_id=%s: %s", normalized_athlete_id, exc)
        raise RuleEngineStateError("failed to persist rule_state to DynamoDB") from exc

    return deepcopy(normalized)
