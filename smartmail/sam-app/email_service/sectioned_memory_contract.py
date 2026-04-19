"""
Sectioned durable memory contract (PR 1 — additive alongside flat athlete memory).

Storage is grouped by section with active + retired buckets per section.
See ../../archive/memory-redesign-implementation-plan.md.
"""

from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Dict, FrozenSet, List, Mapping, Optional, Tuple

MAX_OPEN_LOOPS = 3
MAX_OPEN_LOOP_CHARS = 300

# ---------------------------------------------------------------------------
# Enums (string constants)
# ---------------------------------------------------------------------------

SECTION_GOAL = "goal"
SECTION_CONSTRAINT = "constraint"
SECTION_SCHEDULE_ANCHOR = "schedule_anchor"
SECTION_PREFERENCE = "preference"
SECTION_CONTEXT = "context"

VALID_SECTIONS: FrozenSet[str] = frozenset(
    {
        SECTION_GOAL,
        SECTION_CONSTRAINT,
        SECTION_SCHEDULE_ANCHOR,
        SECTION_PREFERENCE,
        SECTION_CONTEXT,
    }
)

# section -> allowed subtypes (each section has its own subtype set)
SUBTYPES_BY_SECTION: Mapping[str, FrozenSet[str]] = {
    SECTION_GOAL: frozenset({"primary", "secondary"}),
    SECTION_CONSTRAINT: frozenset({"injury", "logistics", "soft_limit", "other"}),
    SECTION_SCHEDULE_ANCHOR: frozenset(
        {"hard_blocker", "recurring_anchor", "soft_preference", "other"}
    ),
    SECTION_PREFERENCE: frozenset({"communication", "planning_style", "other"}),
    SECTION_CONTEXT: frozenset({"equipment", "life_context", "training_baseline", "other"}),
}

STATUS_ACTIVE = "active"
STATUS_RETIRED = "retired"

VALID_STATUSES: FrozenSet[str] = frozenset({STATUS_ACTIVE, STATUS_RETIRED})

RETIREMENT_REPLACED = "replaced_by_newer_active_fact"
RETIREMENT_COMPLETED = "completed"
RETIREMENT_RESOLVED = "resolved"
RETIREMENT_NO_LONGER_RELEVANT = "no_longer_relevant"

VALID_RETIREMENT_REASONS: FrozenSet[str] = frozenset(
    {
        RETIREMENT_REPLACED,
        RETIREMENT_COMPLETED,
        RETIREMENT_RESOLVED,
        RETIREMENT_NO_LONGER_RELEVANT,
    }
)

# Top-level persisted keys (DynamoDB memory_notes JSON)
BUCKET_GOALS = "goals"
BUCKET_CONSTRAINTS = "constraints"
BUCKET_SCHEDULE_ANCHORS = "schedule_anchors"
BUCKET_PREFERENCES = "preferences"
BUCKET_CONTEXT_NOTES = "context_notes"

VALID_STORAGE_BUCKETS: Tuple[str, ...] = (
    BUCKET_GOALS,
    BUCKET_CONSTRAINTS,
    BUCKET_SCHEDULE_ANCHORS,
    BUCKET_PREFERENCES,
    BUCKET_CONTEXT_NOTES,
)

SECTION_FOR_BUCKET: Mapping[str, str] = {
    BUCKET_GOALS: SECTION_GOAL,
    BUCKET_CONSTRAINTS: SECTION_CONSTRAINT,
    BUCKET_SCHEDULE_ANCHORS: SECTION_SCHEDULE_ANCHOR,
    BUCKET_PREFERENCES: SECTION_PREFERENCE,
    BUCKET_CONTEXT_NOTES: SECTION_CONTEXT,
}

BUCKET_FOR_SECTION: Mapping[str, str] = {v: k for k, v in SECTION_FOR_BUCKET.items()}

# Active caps per storage bucket
ACTIVE_CAP_GOALS = 4
ACTIVE_CAP_CONSTRAINTS = 8
ACTIVE_CAP_SCHEDULE_ANCHORS = 8
ACTIVE_CAP_PREFERENCES = 4
ACTIVE_CAP_CONTEXT_NOTES = 4

ACTIVE_CAP_BY_BUCKET: Mapping[str, int] = {
    BUCKET_GOALS: ACTIVE_CAP_GOALS,
    BUCKET_CONSTRAINTS: ACTIVE_CAP_CONSTRAINTS,
    BUCKET_SCHEDULE_ANCHORS: ACTIVE_CAP_SCHEDULE_ANCHORS,
    BUCKET_PREFERENCES: ACTIVE_CAP_PREFERENCES,
    BUCKET_CONTEXT_NOTES: ACTIVE_CAP_CONTEXT_NOTES,
}

RETIRED_CAP_PER_SECTION = 5


class SectionedMemoryContractError(ValueError):
    """Raised when sectioned memory violates the contract."""


def _require_non_empty_str(field_name: str, value: Any) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SectionedMemoryContractError(f"{field_name} must be a non-empty string")
    return value.strip()


def _validate_unix_timestamp(field_name: str, value: Any) -> int:
    if isinstance(value, Decimal):
        if value != int(value):
            raise SectionedMemoryContractError(
                f"{field_name} must be a whole number (got Decimal with fractional part)"
            )
        value = int(value)
    if not isinstance(value, int) or value <= 0:
        raise SectionedMemoryContractError(
            f"{field_name} must be a positive unix timestamp"
        )
    return value


def normalize_fact_key(section: str, raw_key: str) -> str:
    """Return ``"{section}:{slug}"`` using the same slug rules as flat memory.

    Slug: lowercased, stripped, whitespace to hyphens, non-alphanumeric removed,
    truncated to 64 chars.
    """
    if section not in VALID_SECTIONS:
        raise SectionedMemoryContractError(f"invalid section: {section!r}")
    slug = raw_key.strip().lower()
    slug = re.sub(r"\s+", "-", slug)
    slug = re.sub(r"[^a-z0-9\-]", "", slug)
    slug = re.sub(r"-{2,}", "-", slug).strip("-")
    slug = slug[:64]
    if not slug:
        raise SectionedMemoryContractError(
            f"fact_key normalizes to empty string from raw key: {raw_key!r}"
        )
    return f"{section}:{slug}"


def empty_sectioned_memory() -> Dict[str, Any]:
    """Empty persisted shape: all buckets with empty active/retired lists."""
    return {
        bucket: {"active": [], "retired": []} for bucket in VALID_STORAGE_BUCKETS
    }


@dataclass(frozen=True)
class MemoryFact:
    """A durable fact in the sectioned store."""

    memory_id: str
    section: str
    subtype: str
    fact_key: str
    summary: str
    status: str
    supersedes: List[str]
    retirement_reason: Optional[str]
    created_at: int
    updated_at: int
    last_confirmed_at: int
    retired_at: Optional[int]

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "memory_id": self.memory_id,
            "section": self.section,
            "subtype": self.subtype,
            "fact_key": self.fact_key,
            "summary": self.summary,
            "status": self.status,
            "supersedes": list(self.supersedes),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "last_confirmed_at": self.last_confirmed_at,
        }
        if self.retirement_reason is not None:
            d["retirement_reason"] = self.retirement_reason
        if self.retired_at is not None:
            d["retired_at"] = self.retired_at
        return d

    @classmethod
    def from_dict(cls, payload: Any, *, label: str = "fact") -> "MemoryFact":
        if not isinstance(payload, dict):
            raise SectionedMemoryContractError(f"{label} must be a dict")
        memory_id = _require_non_empty_str(f"{label}.memory_id", payload.get("memory_id"))
        try:
            uuid.UUID(memory_id)
        except ValueError as exc:
            raise SectionedMemoryContractError(
                f"{label}.memory_id must be a valid UUID string"
            ) from exc
        section = _require_non_empty_str(f"{label}.section", payload.get("section"))
        if section not in VALID_SECTIONS:
            raise SectionedMemoryContractError(
                f"{label}.section must be one of {sorted(VALID_SECTIONS)}, got {section!r}"
            )
        subtype = _require_non_empty_str(f"{label}.subtype", payload.get("subtype"))
        allowed = SUBTYPES_BY_SECTION.get(section, frozenset())
        if subtype not in allowed:
            raise SectionedMemoryContractError(
                f"{label}.subtype {subtype!r} is not valid for section {section!r}"
            )
        fact_key = _require_non_empty_str(f"{label}.fact_key", payload.get("fact_key"))
        summary = _require_non_empty_str(f"{label}.summary", payload.get("summary"))
        status = _require_non_empty_str(f"{label}.status", payload.get("status"))
        if status not in VALID_STATUSES:
            raise SectionedMemoryContractError(
                f"{label}.status must be one of {sorted(VALID_STATUSES)}, got {status!r}"
            )
        supersedes = _validate_supersedes(f"{label}.supersedes", payload.get("supersedes"))
        created_at = _validate_unix_timestamp(f"{label}.created_at", payload.get("created_at"))
        updated_at = _validate_unix_timestamp(f"{label}.updated_at", payload.get("updated_at"))
        last_confirmed_at = _validate_unix_timestamp(
            f"{label}.last_confirmed_at", payload.get("last_confirmed_at")
        )
        retirement_reason: Optional[str]
        retired_at: Optional[int]
        rr_raw = payload.get("retirement_reason")
        ra_raw = payload.get("retired_at")
        if status == STATUS_ACTIVE:
            if rr_raw is not None:
                raise SectionedMemoryContractError(
                    f"{label}.retirement_reason must be absent or null for active facts"
                )
            if ra_raw is not None:
                raise SectionedMemoryContractError(
                    f"{label}.retired_at must be absent or null for active facts"
                )
            retirement_reason = None
            retired_at = None
        else:
            retirement_reason = _require_non_empty_str(
                f"{label}.retirement_reason", rr_raw
            )
            if retirement_reason not in VALID_RETIREMENT_REASONS:
                raise SectionedMemoryContractError(
                    f"{label}.retirement_reason must be one of "
                    f"{sorted(VALID_RETIREMENT_REASONS)}, got {retirement_reason!r}"
                )
            retired_at = _validate_unix_timestamp(f"{label}.retired_at", ra_raw)
        return cls(
            memory_id=memory_id,
            section=section,
            subtype=subtype,
            fact_key=fact_key,
            summary=summary,
            status=status,
            supersedes=supersedes,
            retirement_reason=retirement_reason,
            created_at=created_at,
            updated_at=updated_at,
            last_confirmed_at=last_confirmed_at,
            retired_at=retired_at,
        )


def _validate_supersedes(label: str, value: Any) -> List[str]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise SectionedMemoryContractError(f"{label} must be a list")
    out: List[str] = []
    for i, item in enumerate(value):
        s = _require_non_empty_str(f"{label}[{i}]", item)
        try:
            uuid.UUID(s)
        except ValueError as exc:
            raise SectionedMemoryContractError(
                f"{label}[{i}] must be a valid UUID string"
            ) from exc
        out.append(s)
    return out


def validate_memory_fact(fact_dict: Any) -> Dict[str, Any]:
    """Validate a single persisted MemoryFact dict; return normalized dict."""
    fact = MemoryFact.from_dict(fact_dict, label="memory_fact")
    return fact.to_dict()


def validate_sectioned_memory(memory_dict: Any) -> Dict[str, Any]:
    """Validate full sectioned structure, caps, and global id / per-section key rules."""
    if not isinstance(memory_dict, dict):
        raise SectionedMemoryContractError("sectioned memory must be a dict")
    keys = set(memory_dict.keys())
    expected = set(VALID_STORAGE_BUCKETS)
    if keys != expected:
        missing = sorted(expected - keys)
        extra = sorted(keys - expected)
        parts = []
        if missing:
            parts.append(f"missing keys: {missing}")
        if extra:
            parts.append(f"unexpected keys: {extra}")
        raise SectionedMemoryContractError(
            "sectioned memory must have exactly the storage bucket keys: "
            + "; ".join(parts)
        )

    seen_ids: set[str] = set()
    out: Dict[str, Any] = {}

    for bucket in VALID_STORAGE_BUCKETS:
        section = SECTION_FOR_BUCKET[bucket]
        raw_bucket = memory_dict[bucket]
        if not isinstance(raw_bucket, dict):
            raise SectionedMemoryContractError(f"{bucket} must be a dict")
        if set(raw_bucket.keys()) != {"active", "retired"}:
            raise SectionedMemoryContractError(
                f"{bucket} must have exactly 'active' and 'retired' keys"
            )
        active_list = raw_bucket["active"]
        retired_list = raw_bucket["retired"]
        if not isinstance(active_list, list):
            raise SectionedMemoryContractError(f"{bucket}.active must be a list")
        if not isinstance(retired_list, list):
            raise SectionedMemoryContractError(f"{bucket}.retired must be a list")

        active_cap = ACTIVE_CAP_BY_BUCKET[bucket]
        retired_cap = RETIRED_CAP_PER_SECTION
        if len(active_list) > active_cap:
            raise SectionedMemoryContractError(
                f"{bucket}.active exceeds cap {active_cap} (got {len(active_list)})"
            )
        if len(retired_list) > retired_cap:
            raise SectionedMemoryContractError(
                f"{bucket}.retired exceeds cap {retired_cap} (got {len(retired_list)})"
            )

        seen_active_keys: set[str] = set()
        norm_active: List[Dict[str, Any]] = []
        for i, item in enumerate(active_list):
            label = f"{bucket}.active[{i}]"
            fact = MemoryFact.from_dict(item, label=label)
            if fact.section != section:
                raise SectionedMemoryContractError(
                    f"{label} has section {fact.section!r}, expected {section!r} for bucket {bucket!r}"
                )
            if fact.status != STATUS_ACTIVE:
                raise SectionedMemoryContractError(
                    f"{label} in active list must have status {STATUS_ACTIVE!r}, got {fact.status!r}"
                )
            if fact.memory_id in seen_ids:
                raise SectionedMemoryContractError(
                    f"duplicate memory_id across sectioned memory: {fact.memory_id!r}"
                )
            seen_ids.add(fact.memory_id)
            if fact.fact_key in seen_active_keys:
                raise SectionedMemoryContractError(
                    f"{bucket}.active contains duplicate fact_key: {fact.fact_key!r}"
                )
            seen_active_keys.add(fact.fact_key)
            norm_active.append(fact.to_dict())

        norm_retired: List[Dict[str, Any]] = []
        for i, item in enumerate(retired_list):
            label = f"{bucket}.retired[{i}]"
            fact = MemoryFact.from_dict(item, label=label)
            if fact.section != section:
                raise SectionedMemoryContractError(
                    f"{label} has section {fact.section!r}, expected {section!r} for bucket {bucket!r}"
                )
            if fact.status != STATUS_RETIRED:
                raise SectionedMemoryContractError(
                    f"{label} in retired list must have status {STATUS_RETIRED!r}, got {fact.status!r}"
                )
            if fact.memory_id in seen_ids:
                raise SectionedMemoryContractError(
                    f"duplicate memory_id across sectioned memory: {fact.memory_id!r}"
                )
            seen_ids.add(fact.memory_id)
            norm_retired.append(fact.to_dict())

        out[bucket] = {"active": norm_active, "retired": norm_retired}

    return out


# ---------------------------------------------------------------------------
# Continuity summary (shared with DynamoDB continuity_summary field)
# ---------------------------------------------------------------------------


def format_unix_timestamp_for_prompt(epoch: int) -> str:
    """Converts a unix epoch to a human-readable UTC string for LLM prompts."""
    return datetime.fromtimestamp(epoch, tz=timezone.utc).strftime("%Y-%m-%d %H:%M UTC")


@dataclass(frozen=True)
class ContinuitySummary:
    """Short-lived coaching state for the next 1-2 exchanges."""

    summary: str
    last_recommendation: str
    open_loops: list
    updated_at: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "summary": self.summary,
            "last_recommendation": self.last_recommendation,
            "open_loops": list(self.open_loops),
            "updated_at": self.updated_at,
        }

    @classmethod
    def from_dict(cls, payload: Any) -> "ContinuitySummary":
        if not isinstance(payload, dict):
            raise SectionedMemoryContractError("continuity_summary must be a dict")
        required = {"summary", "last_recommendation", "open_loops", "updated_at"}
        missing = sorted(required - set(payload.keys()))
        if missing:
            raise SectionedMemoryContractError(
                f"continuity_summary is missing required fields: {', '.join(missing)}"
            )
        return cls(
            summary=_require_non_empty_str("continuity_summary.summary", payload["summary"]),
            last_recommendation=_require_non_empty_str(
                "continuity_summary.last_recommendation", payload["last_recommendation"]
            ),
            open_loops=_validate_open_loops(payload["open_loops"]),
            updated_at=_validate_unix_timestamp("continuity_summary.updated_at", payload["updated_at"]),
        )


def _validate_open_loops(value: Any) -> List[str]:
    if not isinstance(value, list):
        raise SectionedMemoryContractError("continuity_summary.open_loops must be a list")
    if len(value) > MAX_OPEN_LOOPS:
        raise SectionedMemoryContractError(
            f"continuity_summary.open_loops may have at most {MAX_OPEN_LOOPS} items"
        )
    normalized: List[str] = []
    for idx, item in enumerate(value):
        s = _require_non_empty_str(f"continuity_summary.open_loops[{idx}]", item)
        if len(s) > MAX_OPEN_LOOP_CHARS:
            raise SectionedMemoryContractError(
                f"continuity_summary.open_loops[{idx}] exceeds {MAX_OPEN_LOOP_CHARS} chars ({len(s)})"
            )
        normalized.append(s)
    return normalized


def validate_continuity_summary(summary: ContinuitySummary) -> None:
    """Validates a ContinuitySummary instance."""
    _require_non_empty_str("continuity_summary.summary", summary.summary)
    _require_non_empty_str("continuity_summary.last_recommendation", summary.last_recommendation)
    _validate_open_loops(summary.open_loops)
    _validate_unix_timestamp("continuity_summary.updated_at", summary.updated_at)
