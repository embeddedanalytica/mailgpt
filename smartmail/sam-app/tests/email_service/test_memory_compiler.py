"""Tests for memory_compiler."""

from __future__ import annotations

import unittest
import uuid

from memory_compiler import compile_prompt_memory
from sectioned_memory_contract import (
    BUCKET_CONSTRAINTS,
    BUCKET_CONTEXT_NOTES,
    BUCKET_GOALS,
    BUCKET_PREFERENCES,
    BUCKET_SCHEDULE_ANCHORS,
    SECTION_CONSTRAINT,
    SECTION_CONTEXT,
    SECTION_GOAL,
    SECTION_PREFERENCE,
    SECTION_SCHEDULE_ANCHOR,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    empty_sectioned_memory,
)


def _mid() -> str:
    return str(uuid.uuid4())


def _af(
    *,
    section: str,
    subtype: str,
    fact_key: str,
    summary: str,
    last_confirmed_at: int = 100,
    updated_at: int = 100,
    status: str = STATUS_ACTIVE,
) -> dict:
    return {
        "memory_id": _mid(),
        "section": section,
        "subtype": subtype,
        "fact_key": fact_key,
        "summary": summary,
        "status": status,
        "supersedes": [],
        "created_at": 1,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


class TestMemoryCompiler(unittest.TestCase):
    def test_priority_all_goals_and_constraints(self) -> None:
        m = empty_sectioned_memory()
        for i in range(4):
            m["goals"]["active"].append(
                _af(
                    section=SECTION_GOAL,
                    subtype="primary",
                    fact_key=f"goal:{i}",
                    summary=f"G{i}",
                )
            )
        for j in range(8):
            m["constraints"]["active"].append(
                _af(
                    section=SECTION_CONSTRAINT,
                    subtype="injury",
                    fact_key=f"constraint:{j}",
                    summary=f"C{j}",
                )
            )
        out = compile_prompt_memory(m, None)
        self.assertEqual(len(out["priority_facts"]), 12)

    def test_schedule_cap_four_sorts_subtype(self) -> None:
        m = empty_sectioned_memory()
        for i, st in enumerate(
            ["other", "soft_preference", "hard_blocker", "recurring_anchor", "hard_blocker"]
        ):
            m["schedule_anchors"]["active"].append(
                _af(
                    section=SECTION_SCHEDULE_ANCHOR,
                    subtype=st,
                    fact_key=f"schedule:{i}",
                    summary=f"S{i}",
                    last_confirmed_at=200 + i,
                )
            )
        out = compile_prompt_memory(m, None)
        self.assertEqual(len(out["structure_facts"]), 4)
        subtypes = [f["subtype"] for f in out["structure_facts"]]
        self.assertEqual(subtypes[0], "hard_blocker")

    def test_preference_cap_two(self) -> None:
        m = empty_sectioned_memory()
        for i in range(4):
            m["preferences"]["active"].append(
                _af(
                    section=SECTION_PREFERENCE,
                    subtype="other",
                    fact_key=f"preference:{i}",
                    summary=f"P{i}",
                    last_confirmed_at=300 + i,
                )
            )
        out = compile_prompt_memory(m, None)
        self.assertEqual(len(out["preference_facts"]), 2)

    def test_context_cap_three(self) -> None:
        m = empty_sectioned_memory()
        for i in range(5):
            m["context_notes"]["active"].append(
                _af(
                    section=SECTION_CONTEXT,
                    subtype="life_context",
                    fact_key=f"context:{i}",
                    summary=f"X{i}",
                    last_confirmed_at=400 + i,
                )
            )
        out = compile_prompt_memory(m, None)
        self.assertEqual(len(out["context_facts"]), 3)

    def test_retired_ignored(self) -> None:
        m = empty_sectioned_memory()
        m["goals"]["retired"].append(
            _af(
                section=SECTION_GOAL,
                subtype="primary",
                fact_key="goal:old",
                summary="Old",
                status=STATUS_RETIRED,
            )
        )
        m["goals"]["active"].append(
            _af(
                section=SECTION_GOAL,
                subtype="primary",
                fact_key="goal:new",
                summary="New",
            )
        )
        out = compile_prompt_memory(m, None)
        self.assertEqual(len(out["priority_facts"]), 1)

    def test_continuity_focus(self) -> None:
        out = compile_prompt_memory(
            empty_sectioned_memory(),
            {"summary": "  Focus line  ", "other": 1},
        )
        self.assertEqual(out["continuity_focus"], "Focus line")

    def test_empty_ok(self) -> None:
        out = compile_prompt_memory(empty_sectioned_memory(), None)
        self.assertEqual(out["priority_facts"], [])
        self.assertEqual(out["structure_facts"], [])
        self.assertEqual(out["continuity_focus"], None)

    def test_deterministic(self) -> None:
        m = empty_sectioned_memory()
        m["schedule_anchors"]["active"].append(
            _af(
                section=SECTION_SCHEDULE_ANCHOR,
                subtype="soft_preference",
                fact_key="schedule:a",
                summary="A",
                last_confirmed_at=10,
                updated_at=10,
            )
        )
        m["schedule_anchors"]["active"].append(
            _af(
                section=SECTION_SCHEDULE_ANCHOR,
                subtype="hard_blocker",
                fact_key="schedule:b",
                summary="B",
                last_confirmed_at=10,
                updated_at=10,
            )
        )
        a = compile_prompt_memory(m, None)
        b = compile_prompt_memory(m, None)
        self.assertEqual(a, b)


if __name__ == "__main__":
    unittest.main()
