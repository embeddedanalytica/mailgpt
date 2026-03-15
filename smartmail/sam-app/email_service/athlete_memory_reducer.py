"""Deterministic AM2 durable-memory reduction helpers."""

from __future__ import annotations

from decimal import Decimal
import re
import time
from typing import Any, Dict, List, Optional

from athlete_memory_contract import (
    ALLOWED_FACT_TYPES,
    ALLOWED_MEMORY_NOTE_IMPORTANCE,
    MAX_MEMORY_NOTES,
    AthleteMemoryContractError,
    MemoryNote,
    filter_active_memory_notes,
    normalize_fact_key,
    validate_memory_note_list,
)


ALLOWED_CANDIDATE_ACTIONS = {"upsert", "confirm", "retire"}
ALLOWED_EVIDENCE_SOURCES = {
    "athlete_email",
    "profile_update",
    "manual_activity",
    "rule_engine_state",
}
ALLOWED_EVIDENCE_STRENGTHS = {"explicit", "strong_inference", "weak_inference"}
ALLOWED_CONSOLIDATION_ACTIONS = {"merge_into"}

_NON_ALNUM = re.compile(r"[^a-z0-9]+")
_WHITESPACE = re.compile(r"\s+")
_TIME_CUTOFF_PATTERN = re.compile(
    r"(?:before|finish before|only before)\s+(\d{1,2})(?::00)?\s*(am|pm)\b"
)
_AFTER_TIME_PATTERN = re.compile(
    r"(?:after)\s+(\d{1,2})(?::00)?\s*(am|pm)\b"
)
_UNDER_MINUTES_PATTERN = re.compile(
    r"(?:under|within|cap(?:ped)?\s+at|limited to)\s+~?(\d{1,3})\s*minutes?\b"
)
_WEEKDAY_COUNT_PATTERN = re.compile(
    r"(\d+|one|two|three|four|five)\s+weekday\s+mornings?"
)
_DAY_ORDER = (
    "monday",
    "tuesday",
    "wednesday",
    "thursday",
    "friday",
    "saturday",
    "sunday",
)
_EQUIPMENT_MARKERS = (
    "indoor trainer",
    "smart trainer",
    "power meter",
    "home wall",
    "reformer",
)

_IMPORTANCE_RANK = {"low": 0, "medium": 1, "high": 2}
_EVIDENCE_RANK = {"weak_inference": 0, "strong_inference": 1, "explicit": 2}


class AthleteMemoryReducerError(ValueError):
    """Raised when the long-term AM2 payload cannot be reduced safely."""


def _normalize_text(value: Any) -> str:
    text = str(value or "").strip().lower()
    text = text.replace("&", " and ")
    text = _WHITESPACE.sub(" ", text)
    return text


def _slugify(value: Any) -> str:
    text = _normalize_text(value)
    text = _NON_ALNUM.sub("_", text)
    text = text.strip("_")
    return text or "fact"


def _first_day(text: str) -> Optional[str]:
    for day in _DAY_ORDER:
        if day in text:
            return day
    return None


def _days_present(text: str) -> List[str]:
    return [day for day in _DAY_ORDER if day in text]


def _derive_schedule_or_constraint_key(summary_text: str) -> Optional[str]:
    cutoff_match = _TIME_CUTOFF_PATTERN.search(summary_text)
    if cutoff_match and "weekday" in summary_text:
        hour = cutoff_match.group(1)
        meridiem = cutoff_match.group(2)
        return f"weekday_before_{hour}{meridiem}_cutoff"

    after_match = _AFTER_TIME_PATTERN.search(summary_text)
    if after_match and ("train" in summary_text or "session" in summary_text or "workout" in summary_text):
        hour = after_match.group(1)
        meridiem = after_match.group(2)
        return f"after_{hour}{meridiem}_training_window"

    if "before work" in summary_text or "pre-work" in summary_text:
        if "lane" in summary_text or "swim" in summary_text or "pool" in summary_text:
            return "weekday_morning_lane_access"
        return "before_work_training_window"

    if "early morning" in summary_text or "early mornings" in summary_text or "before sunrise" in summary_text:
        return "early_morning_training_window"

    minute_limit = _UNDER_MINUTES_PATTERN.search(summary_text)
    if minute_limit and "weekday" in summary_text and (
        "ride" in summary_text or "session" in summary_text or "workout" in summary_text
    ):
        return "weekday_session_time_limit"

    if "weekday" in summary_text and (
        "longer" in summary_text or "more time" in summary_text or "extra time" in summary_text
    ) and ("ride" in summary_text or "session" in summary_text or "workout" in summary_text):
        return "weekday_session_time_limit"

    if _WEEKDAY_COUNT_PATTERN.search(summary_text) and (
        "lane" in summary_text or "swim" in summary_text or "pool" in summary_text
    ):
        return "weekday_morning_lane_access"

    day = _first_day(summary_text)
    if "masters" in summary_text:
        return "masters_session_slot"

    if "bike commute" in summary_text or "commuting twice a week" in summary_text:
        return "bike_commute_volume"

    if day and any(marker in summary_text for marker in ("open", "available", "unavailable", "busy")):
        return f"{day}_availability"

    if day and "long run" in summary_text:
        return f"{day}_long_run_anchor"

    days = _days_present(summary_text)
    if "bike" in summary_text and len(days) >= 2:
        return "bike_weekly_windows"

    if "indoor trainer" in summary_text and "weekday" in summary_text:
        return "weekday_indoor_trainer_routine"

    if "smart trainer" in summary_text:
        return "smart_trainer_backup"

    if "power meter" in summary_text:
        return "power_meter_available"

    if "home wall" in summary_text:
        return "home_wall_available"

    if "reformer" in summary_text:
        return "reformer_anchor"

    if day and "strength" in summary_text:
        return f"{day}_strength_slot"

    if day and "mobility" in summary_text:
        return f"{day}_mobility_slot"

    if day and "sparring" in summary_text:
        return f"{day}_sparring_slot"

    if day and "mitt" in summary_text:
        return f"{day}_mitt_slot"

    if day and "fingerboard" in summary_text:
        return f"{day}_fingerboard_slot"

    if day and "ski-erg" in summary_text:
        return f"{day}_ski_erg_slot"

    if day and "roadwork" in summary_text:
        return f"{day}_roadwork_slot"

    if day and "ball-machine" in summary_text:
        return f"{day}_ball_machine_slot"

    if day and ("group" in summary_text or "clinic" in summary_text or "lift" in summary_text):
        activity = "group"
        if "stroke clinic" in summary_text:
            activity = "stroke_clinic"
        elif "easy-run group" in summary_text or "easy run group" in summary_text:
            activity = "easy_run_group"
        elif "team lift" in summary_text:
            activity = "team_lift"
        return f"{day}_{activity}_slot"

    if "swim" in summary_text and "limiter" in summary_text:
        return "swim_limiter"

    return None


def _derive_goal_key(summary_text: str, proposed_key_text: str) -> Optional[str]:
    if proposed_key_text:
        return _slugify(proposed_key_text)
    if "bay crest marathon" in summary_text:
        return "bay_crest_marathon"
    if "olympic tri" in summary_text:
        return "olympic_triathlon"
    if "gravel race" in summary_text:
        return "gravel_race_goal"
    if "marathon" in summary_text:
        return "marathon_goal"
    return None


def _derive_preference_key(summary_text: str, proposed_key_text: str) -> Optional[str]:
    if proposed_key_text:
        return _slugify(proposed_key_text)
    if "concise" in summary_text or "bullets" in summary_text:
        return "reply_format"
    if "explicit priorities" in summary_text:
        return "reply_priorities"
    return None


def _derive_other_key(summary_text: str, proposed_key_text: str) -> Optional[str]:
    if any(marker in summary_text for marker in _EQUIPMENT_MARKERS):
        equipment_key = _derive_schedule_or_constraint_key(summary_text)
        if equipment_key:
            return equipment_key
    if "limiter" in summary_text:
        dayless = summary_text.split("limiter", 1)[0].strip()
        return f"{_slugify(dayless)}_limiter"
    if proposed_key_text:
        return _slugify(proposed_key_text)
    return None


def derive_canonical_fact_key(
    *,
    fact_type: str,
    proposed_key: Any,
    summary: Any,
) -> str:
    normalized_fact_type = str(fact_type).strip().lower()
    if normalized_fact_type not in ALLOWED_FACT_TYPES:
        raise AthleteMemoryReducerError(
            f"fact_type must be one of {sorted(ALLOWED_FACT_TYPES)}"
        )

    summary_text = _normalize_text(summary)
    proposed_key_text = _normalize_text(proposed_key)

    derived: Optional[str] = None
    if normalized_fact_type in {"schedule", "constraint"}:
        derived = _derive_schedule_or_constraint_key(summary_text)
    elif normalized_fact_type == "goal":
        derived = _derive_goal_key(summary_text, proposed_key_text)
    elif normalized_fact_type == "preference":
        derived = _derive_preference_key(summary_text, proposed_key_text)
    else:
        derived = _derive_other_key(summary_text, proposed_key_text)

    if not derived:
        derived = _slugify(proposed_key_text or summary_text)
    return derived


def _normalize_candidate(raw_candidate: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_candidate, dict):
        raise AthleteMemoryReducerError("candidate must be a dict")

    action = str(raw_candidate.get("action", "")).strip().lower()
    if action not in ALLOWED_CANDIDATE_ACTIONS:
        raise AthleteMemoryReducerError(
            f"candidate.action must be one of {sorted(ALLOWED_CANDIDATE_ACTIONS)}"
        )

    evidence_source = str(raw_candidate.get("evidence_source", "")).strip().lower()
    if evidence_source not in ALLOWED_EVIDENCE_SOURCES:
        raise AthleteMemoryReducerError(
            "candidate.evidence_source must be one of "
            + ", ".join(sorted(ALLOWED_EVIDENCE_SOURCES))
        )

    evidence_strength = str(raw_candidate.get("evidence_strength", "")).strip().lower()
    if evidence_strength not in ALLOWED_EVIDENCE_STRENGTHS:
        raise AthleteMemoryReducerError(
            "candidate.evidence_strength must be one of "
            + ", ".join(sorted(ALLOWED_EVIDENCE_STRENGTHS))
        )

    memory_note_id = raw_candidate.get("memory_note_id")
    if action == "upsert":
        importance = str(raw_candidate.get("importance", "")).strip().lower()
        memory_note_id = _coerce_memory_note_id(memory_note_id, allow_zero=True)
        fact_type = str(raw_candidate.get("fact_type", "")).strip().lower()
        if fact_type not in ALLOWED_FACT_TYPES:
            raise AthleteMemoryReducerError(
                f"candidate.fact_type must be one of {sorted(ALLOWED_FACT_TYPES)}"
            )
        summary = str(raw_candidate.get("summary", "")).strip()
        if not summary:
            raise AthleteMemoryReducerError("candidate.summary must be a non-empty string")
        if importance not in ALLOWED_MEMORY_NOTE_IMPORTANCE:
            raise AthleteMemoryReducerError(
                "candidate.importance must be one of "
                + ", ".join(sorted(ALLOWED_MEMORY_NOTE_IMPORTANCE))
            )
        fact_key = normalize_fact_key(raw_candidate.get("fact_key", ""))
        return {
            "action": action,
            "memory_note_id": memory_note_id or None,
            "fact_type": fact_type,
            "fact_key": fact_key,
            "summary": summary,
            "importance": importance or "medium",
            "evidence_source": evidence_source,
            "evidence_strength": evidence_strength,
        }

    memory_note_id = _coerce_memory_note_id(memory_note_id, allow_zero=False)

    if action == "confirm":
        return {
            "action": action,
            "memory_note_id": memory_note_id,
            "evidence_source": evidence_source,
            "evidence_strength": evidence_strength,
        }

    reason = str(raw_candidate.get("reason", "")).strip()
    if not reason:
        raise AthleteMemoryReducerError("candidate.reason must be a non-empty string for retire")
    if evidence_strength != "explicit":
        raise AthleteMemoryReducerError("candidate.retire evidence_strength must be explicit")
    return {
        "action": action,
        "memory_note_id": memory_note_id,
        "reason": reason,
        "evidence_source": evidence_source,
        "evidence_strength": evidence_strength,
    }


def _normalize_consolidation_op(raw_op: Dict[str, Any]) -> Dict[str, Any]:
    if not isinstance(raw_op, dict):
        raise AthleteMemoryReducerError("consolidation op must be a dict")
    action = str(raw_op.get("action", "")).strip().lower()
    if action not in ALLOWED_CONSOLIDATION_ACTIONS:
        raise AthleteMemoryReducerError(
            f"consolidation action must be one of {sorted(ALLOWED_CONSOLIDATION_ACTIONS)}"
        )
    source_memory_note_id = raw_op.get("source_memory_note_id")
    target_memory_note_id = raw_op.get("target_memory_note_id")
    summary = str(raw_op.get("summary", "")).strip()
    if (
        isinstance(source_memory_note_id, bool)
        or not isinstance(source_memory_note_id, int)
        or source_memory_note_id < 1
        or isinstance(target_memory_note_id, bool)
        or not isinstance(target_memory_note_id, int)
        or target_memory_note_id < 1
        or not summary
    ):
        raise AthleteMemoryReducerError(
            "merge_into requires source_memory_note_id, target_memory_note_id, and summary"
        )
    return {
        "action": action,
        "source_memory_note_id": source_memory_note_id,
        "target_memory_note_id": target_memory_note_id,
        "summary": summary,
    }


def validate_long_term_candidate_payload(data: Any) -> Dict[str, Any]:
    if not isinstance(data, dict):
        raise AthleteMemoryReducerError("long-term payload must be a JSON object")

    allowed_keys = {"candidates", "consolidation_ops"}
    unknown_keys = sorted(set(data.keys()) - allowed_keys)
    if unknown_keys:
        raise AthleteMemoryReducerError(
            "long-term payload contains unknown keys: " + ", ".join(unknown_keys)
        )

    candidates_raw = data.get("candidates")
    if not isinstance(candidates_raw, list):
        raise AthleteMemoryReducerError("candidates must be a list")

    normalized_candidates = [_normalize_candidate(item) for item in candidates_raw]
    normalized_ops = [
        _normalize_consolidation_op(item)
        for item in data.get("consolidation_ops", []) or []
    ]
    return {
        "candidates": normalized_candidates,
        "consolidation_ops": normalized_ops,
    }


def _find_note_for_fact_key(
    notes: List[Dict[str, Any]],
    fact_key: str,
    *,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    matches = [
        note
        for note in notes
        if note["fact_key"] == fact_key and (not active_only or note["status"] == "active")
    ]
    if not matches:
        return None
    matches.sort(key=lambda item: (item["status"] == "active", item["updated_at"]), reverse=True)
    return matches[0]


def _coerce_memory_note_id(value: Any, *, allow_zero: bool) -> int:
    if value is None and allow_zero:
        return 0
    if isinstance(value, bool):
        raise AthleteMemoryReducerError("candidate.memory_note_id must be an integer")
    original_value = value
    try:
        value = int(value)
    except (TypeError, ValueError):
        try:
            value = int(str(original_value).strip())
        except (TypeError, ValueError) as exc:
            raise AthleteMemoryReducerError("candidate.memory_note_id must be an integer") from exc

    if isinstance(original_value, float) and not original_value.is_integer():
        raise AthleteMemoryReducerError("candidate.memory_note_id must be an integer")
    if isinstance(original_value, Decimal) and original_value != value:
        raise AthleteMemoryReducerError("candidate.memory_note_id must be an integer")

    minimum = 0 if allow_zero else 1
    if value < minimum:
        if allow_zero:
            raise AthleteMemoryReducerError(
                "candidate.memory_note_id must be 0 or an integer >= 1 for upsert"
            )
        raise AthleteMemoryReducerError("candidate.memory_note_id must be an integer >= 1")
    return value


def _find_note_for_memory_note_id(
    notes: List[Dict[str, Any]],
    memory_note_id: int,
    *,
    active_only: bool = False,
) -> Optional[Dict[str, Any]]:
    for note in notes:
        if note["memory_note_id"] != memory_note_id:
            continue
        if active_only and note["status"] != "active":
            continue
        return note
    return None


def _dedupe_conflicting_candidates(
    candidates: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    by_key: Dict[str, List[Dict[str, Any]]] = {}
    for candidate in candidates:
        if candidate["action"] == "upsert" and candidate.get("memory_note_id") is None:
            identity = f"new:{candidate['fact_key']}"
        else:
            identity = f"id:{candidate['memory_note_id']}"
        by_key.setdefault(identity, []).append(candidate)

    accepted: List[Dict[str, Any]] = []
    for _, items in by_key.items():
        if len(items) != 1:
            continue
        accepted.append(items[0])
    return accepted


def _next_memory_note_id(notes: List[Dict[str, Any]]) -> int:
    return max((note["memory_note_id"] for note in notes), default=0) + 1


def _apply_single_candidate(
    *,
    notes: List[Dict[str, Any]],
    candidate: Dict[str, Any],
    now_epoch: int,
    added_note_meta: Dict[int, Dict[str, Any]],
) -> None:
    if candidate["action"] == "confirm":
        existing_active = _find_note_for_memory_note_id(
            notes, candidate["memory_note_id"], active_only=True
        )
        if existing_active is None:
            return
        existing_active["updated_at"] = now_epoch
        existing_active["last_confirmed_at"] = now_epoch
        return

    if candidate["action"] == "retire":
        existing_active = _find_note_for_memory_note_id(
            notes, candidate["memory_note_id"], active_only=True
        )
        if existing_active is None:
            return
        existing_active["status"] = "inactive"
        existing_active["updated_at"] = now_epoch
        return

    existing_any = None
    if candidate["memory_note_id"] is not None:
        existing_any = _find_note_for_memory_note_id(notes, candidate["memory_note_id"])
    if existing_any is None:
        existing_any = _find_note_for_fact_key(notes, candidate["fact_key"], active_only=False)

    if existing_any is not None:
        existing_any["fact_type"] = candidate["fact_type"]
        existing_any["fact_key"] = candidate["fact_key"]
        existing_any["summary"] = candidate["summary"]
        existing_any["importance"] = candidate["importance"]
        existing_any["status"] = "active"
        existing_any["updated_at"] = now_epoch
        existing_any["last_confirmed_at"] = now_epoch
        return

    memory_note_id = _next_memory_note_id(notes)
    new_note = MemoryNote(
        memory_note_id=memory_note_id,
        fact_type=candidate["fact_type"],
        fact_key=candidate["fact_key"],
        summary=candidate["summary"],
        importance=candidate["importance"],
        status="active",
        created_at=now_epoch,
        updated_at=now_epoch,
        last_confirmed_at=now_epoch,
    ).to_dict()
    notes.append(new_note)
    added_note_meta[memory_note_id] = {
        "importance": candidate["importance"],
        "evidence_strength": candidate["evidence_strength"],
        "fact_key": candidate["fact_key"],
    }


def _apply_consolidation_ops(
    *,
    notes: List[Dict[str, Any]],
    consolidation_ops: List[Dict[str, Any]],
    now_epoch: int,
) -> None:
    for op in consolidation_ops:
        if op["action"] != "merge_into":
            continue
        if op["source_memory_note_id"] == op["target_memory_note_id"]:
            continue
        source = _find_note_for_memory_note_id(
            notes, op["source_memory_note_id"], active_only=True
        )
        target = _find_note_for_memory_note_id(
            notes, op["target_memory_note_id"], active_only=True
        )
        if source is None or target is None:
            continue
        target["summary"] = op["summary"]
        target["updated_at"] = now_epoch
        target["last_confirmed_at"] = now_epoch
        source["status"] = "inactive"
        source["updated_at"] = now_epoch


def _dedupe_active_fact_keys(notes: List[Dict[str, Any]], now_epoch: int) -> None:
    seen: Dict[str, Dict[str, Any]] = {}
    active_notes = [
        note for note in notes if note["status"] == "active"
    ]
    active_notes.sort(
        key=lambda note: (
            _IMPORTANCE_RANK.get(note["importance"], 0),
            note["updated_at"],
            note["memory_note_id"],
        ),
        reverse=True,
    )
    for note in active_notes:
        winner = seen.get(note["fact_key"])
        if winner is None:
            seen[note["fact_key"]] = note
            continue
        note["status"] = "inactive"
        note["updated_at"] = now_epoch


def _drop_lowest_priority_active_note(
    notes: List[Dict[str, Any]],
    *,
    removable_ids: List[int],
    added_note_meta: Dict[int, Dict[str, Any]],
    now_epoch: int,
) -> bool:
    removable = [
        note
        for note in notes
        if note["status"] == "active" and note["memory_note_id"] in removable_ids
    ]
    if not removable:
        return False
    removable.sort(
        key=lambda note: (
            _IMPORTANCE_RANK.get(
                added_note_meta.get(note["memory_note_id"], {}).get("importance", note["importance"]),
                0,
            ),
            _EVIDENCE_RANK.get(
                added_note_meta.get(note["memory_note_id"], {}).get("evidence_strength", "weak_inference"),
                0,
            ),
            note["fact_key"],
        )
    )
    removable[0]["status"] = "inactive"
    removable[0]["updated_at"] = now_epoch
    return True


def _enforce_active_budget(
    *,
    notes: List[Dict[str, Any]],
    added_note_meta: Dict[int, Dict[str, Any]],
    now_epoch: int,
) -> None:
    _dedupe_active_fact_keys(notes, now_epoch)
    active_notes = filter_active_memory_notes(notes)
    if len(active_notes) <= MAX_MEMORY_NOTES:
        return

    added_ids = sorted(added_note_meta.keys())
    while len(filter_active_memory_notes(notes)) > MAX_MEMORY_NOTES and added_ids:
        if not _drop_lowest_priority_active_note(
            notes,
            removable_ids=added_ids,
            added_note_meta=added_note_meta,
            now_epoch=now_epoch,
        ):
            break

    existing_ids = [note["memory_note_id"] for note in notes if note["status"] == "active"]
    while len(filter_active_memory_notes(notes)) > MAX_MEMORY_NOTES and existing_ids:
        if not _drop_lowest_priority_active_note(
            notes,
            removable_ids=existing_ids,
            added_note_meta=added_note_meta,
            now_epoch=now_epoch,
        ):
            break


def reduce_long_term_memory(
    *,
    stored_memory_notes: List[Dict[str, Any]],
    candidate_payload: Dict[str, Any],
    now_epoch: Optional[int] = None,
) -> List[Dict[str, Any]]:
    normalized_notes = [dict(note) for note in validate_memory_note_list(stored_memory_notes)]
    normalized_payload = validate_long_term_candidate_payload(candidate_payload)
    current_epoch = int(now_epoch or time.time())
    added_note_meta: Dict[int, Dict[str, Any]] = {}

    accepted_candidates = _dedupe_conflicting_candidates(normalized_payload["candidates"])
    for candidate in accepted_candidates:
        _apply_single_candidate(
            notes=normalized_notes,
            candidate=candidate,
            now_epoch=current_epoch,
            added_note_meta=added_note_meta,
        )

    _apply_consolidation_ops(
        notes=normalized_notes,
        consolidation_ops=normalized_payload["consolidation_ops"],
        now_epoch=current_epoch,
    )
    _enforce_active_budget(
        notes=normalized_notes,
        added_note_meta=added_note_meta,
        now_epoch=current_epoch,
    )

    normalized_notes.sort(key=lambda note: note["memory_note_id"])
    try:
        return validate_memory_note_list(normalized_notes)
    except AthleteMemoryContractError as exc:
        raise AthleteMemoryReducerError(str(exc)) from exc
