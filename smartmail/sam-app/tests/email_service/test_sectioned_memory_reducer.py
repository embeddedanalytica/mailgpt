"""Tests for sectioned_memory_reducer."""

from __future__ import annotations

import unittest
import uuid

from sectioned_memory_contract import (
    BUCKET_GOALS,
    SECTION_GOAL,
    SECTION_PREFERENCE,
    SECTION_SCHEDULE_ANCHOR,
    STATUS_ACTIVE,
    STATUS_RETIRED,
    empty_sectioned_memory,
)
from sectioned_memory_reducer import (
    SectionedCandidateReducerError,
    apply_sectioned_refresh,
)


def _id() -> str:
    return str(uuid.uuid4())


def _fact(
    *,
    section: str = SECTION_GOAL,
    subtype: str = "primary",
    fact_key: str = "goal:test",
    summary: str = "Summary",
    memory_id: str | None = None,
    supersedes: list | None = None,
) -> dict:
    mid = memory_id or _id()
    return {
        "memory_id": mid,
        "section": section,
        "subtype": subtype,
        "fact_key": fact_key,
        "summary": summary,
        "status": STATUS_ACTIVE,
        "supersedes": supersedes or [],
        "created_at": 1000,
        "updated_at": 1000,
        "last_confirmed_at": 1000,
    }


def _continuity() -> dict:
    return {
        "summary": "Coach context here.",
        "last_recommendation": "Do the work.",
        "open_loops": ["Loop one"],
    }


class TestSectionedReducerBasics(unittest.TestCase):
    def test_new_upsert_in_goal_bucket(self) -> None:
        mem = empty_sectioned_memory()
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "section": SECTION_GOAL,
                        "subtype": "primary",
                        "fact_key": "marathon",
                        "summary": "Run marathon",
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            2000,
        )
        active = out["sectioned_memory"]["goals"]["active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["summary"], "Run marathon")
        self.assertEqual(active[0]["fact_key"], "goal:marathon")

    def test_update_upsert(self) -> None:
        f = _fact(summary="Old", fact_key="goal:x")
        mid = f["memory_id"]
        mem = empty_sectioned_memory()
        mem["goals"]["active"].append(f)
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "target_id": mid,
                        "summary": "New text",
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            2001,
        )
        self.assertEqual(out["sectioned_memory"]["goals"]["active"][0]["summary"], "New text")
        self.assertEqual(out["sectioned_memory"]["goals"]["active"][0]["updated_at"], 2001)

    def test_confirm(self) -> None:
        f = _fact()
        mid = f["memory_id"]
        mem = empty_sectioned_memory()
        mem["goals"]["active"].append(f)
        out = apply_sectioned_refresh(
            {
                "candidates": [{"action": "confirm", "target_id": mid}],
                "continuity": _continuity(),
            },
            mem,
            3000,
        )
        self.assertEqual(out["sectioned_memory"]["goals"]["active"][0]["last_confirmed_at"], 3000)


class TestRetireAndSupersede(unittest.TestCase):
    def test_retire_moves_to_retired(self) -> None:
        f = _fact(fact_key="goal:old", summary="Old goal")
        mid = f["memory_id"]
        mem = empty_sectioned_memory()
        mem["goals"]["active"].append(f)
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "retire",
                        "section": SECTION_GOAL,
                        "target_id": mid,
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            4000,
        )
        self.assertEqual(len(out["sectioned_memory"]["goals"]["active"]), 0)
        self.assertEqual(len(out["sectioned_memory"]["goals"]["retired"]), 1)
        r = out["sectioned_memory"]["goals"]["retired"][0]
        self.assertEqual(r["status"], STATUS_RETIRED)
        self.assertEqual(r["retirement_reason"], "no_longer_relevant")

    def test_supersede_sets_replaced_reason(self) -> None:
        old = _fact(fact_key="goal:legacy", summary="Legacy")
        old_id = old["memory_id"]
        mem = empty_sectioned_memory()
        mem["goals"]["active"].append(old)
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "section": SECTION_GOAL,
                        "subtype": "primary",
                        "fact_key": "newgoal",
                        "summary": "Replacement",
                        "supersedes_fact_keys": ["goal:legacy"],
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            5000,
        )
        retired = out["sectioned_memory"]["goals"]["retired"]
        self.assertTrue(any(x["memory_id"] == old_id for x in retired))
        self.assertEqual(
            next(x for x in retired if x["memory_id"] == old_id)["retirement_reason"],
            "replaced_by_newer_active_fact",
        )
        active = out["sectioned_memory"]["goals"]["active"]
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0]["supersedes"], [old_id])


class TestRejectAtCap(unittest.TestCase):
    def test_reject_when_at_cap_without_supersede(self) -> None:
        mem = empty_sectioned_memory()
        for i in range(4):
            mem["goals"]["active"].append(
                _fact(fact_key=f"goal:{i}", summary=f"S{i}", memory_id=_id())
            )
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "section": SECTION_GOAL,
                        "subtype": "secondary",
                        "fact_key": "extra",
                        "summary": "Extra",
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            6000,
        )
        self.assertEqual(len(out["sectioned_memory"]["goals"]["active"]), 4)

    def test_allow_supersede_at_cap(self) -> None:
        mem = empty_sectioned_memory()
        ids = []
        for i in range(4):
            mid = _id()
            ids.append(mid)
            mem["goals"]["active"].append(
                _fact(fact_key=f"goal:{i}", summary=f"S{i}", memory_id=mid)
            )
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "section": SECTION_GOAL,
                        "subtype": "primary",
                        "fact_key": "replacement",
                        "summary": "New",
                        "supersedes_fact_keys": ["goal:0"],
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            6001,
        )
        active = out["sectioned_memory"]["goals"]["active"]
        self.assertEqual(len(active), 4)


class TestTwoPassOrdering(unittest.TestCase):
    def test_retire_before_new_create_same_batch(self) -> None:
        mem = empty_sectioned_memory()
        for i in range(4):
            mem["goals"]["active"].append(
                _fact(fact_key=f"goal:{i}", summary=f"S{i}", memory_id=_id())
            )
        victim = mem["goals"]["active"][0]["memory_id"]
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "retire",
                        "section": SECTION_GOAL,
                        "target_id": victim,
                    },
                    {
                        "action": "upsert",
                        "section": SECTION_GOAL,
                        "subtype": "secondary",
                        "fact_key": "fresh",
                        "summary": "Fresh slot",
                    },
                ],
                "continuity": _continuity(),
            },
            mem,
            7000,
        )
        keys = [f["fact_key"] for f in out["sectioned_memory"]["goals"]["active"]]
        self.assertIn("goal:fresh", keys)
        self.assertEqual(len(out["sectioned_memory"]["goals"]["active"]), 4)


class TestLowValueDrop(unittest.TestCase):
    def test_drop_low_value_unreferenced(self) -> None:
        f = _fact(
            section=SECTION_PREFERENCE,
            subtype="other",
            fact_key="preference:x",
            summary="Lo",
        )
        mid = f["memory_id"]
        mem = empty_sectioned_memory()
        mem["preferences"]["active"] = [f]
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "retire",
                        "section": SECTION_PREFERENCE,
                        "target_id": mid,
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            8000,
        )
        self.assertEqual(out["sectioned_memory"]["preferences"]["retired"], [])

    def test_keep_low_value_when_superseded_chain(self) -> None:
        old = _fact(
            section=SECTION_PREFERENCE,
            subtype="communication",
            fact_key="preference:old",
            summary="Email only",
        )
        oid = old["memory_id"]
        mem = empty_sectioned_memory()
        mem["preferences"]["active"] = [old]
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "upsert",
                        "section": SECTION_PREFERENCE,
                        "subtype": "communication",
                        "fact_key": "newpref",
                        "summary": "Text ok",
                        "supersedes_fact_keys": ["preference:old"],
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            8001,
        )
        retired = out["sectioned_memory"]["preferences"]["retired"]
        self.assertTrue(any(x["memory_id"] == oid for x in retired))


class TestFuzzyRetire(unittest.TestCase):
    def test_resolves_by_fact_key_string(self) -> None:
        f = _fact(fact_key="goal:match-me", summary="Something")
        mem = empty_sectioned_memory()
        mem["goals"]["active"].append(f)
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "retire",
                        "section": SECTION_GOAL,
                        "target_id": "wrong-id",
                        "fact_key": "goal:match-me",
                    }
                ],
                "continuity": _continuity(),
            },
            mem,
            9000,
        )
        self.assertEqual(len(out["sectioned_memory"]["goals"]["active"]), 0)


class TestSupersedeCleanupContinuity(unittest.TestCase):
    def test_strips_segments_referencing_retired(self) -> None:
        # Align fact summary with a continuity segment so token overlap matches cleanup rules.
        old = _fact(fact_key="goal:gone", summary="Boston marathon plan focus")
        mem = empty_sectioned_memory()
        mem["goals"]["active"].append(old)
        out = apply_sectioned_refresh(
            {
                "candidates": [
                    {
                        "action": "retire",
                        "section": SECTION_GOAL,
                        "target_id": old["memory_id"],
                    }
                ],
                "continuity": {
                    "summary": "Boston marathon plan focus; unrelated tail",
                    "last_recommendation": "Run",
                    "open_loops": [],
                },
            },
            mem,
            10000,
        )
        s = out["continuity_summary"]["summary"].lower()
        self.assertNotIn("boston", s)
        self.assertIn("unrelated", s)


class TestErrors(unittest.TestCase):
    def test_update_missing_target_raises(self) -> None:
        with self.assertRaises(SectionedCandidateReducerError):
            apply_sectioned_refresh(
                {
                    "candidates": [
                        {"action": "upsert", "target_id": "nope", "summary": "x"}
                    ],
                    "continuity": _continuity(),
                },
                empty_sectioned_memory(),
                1,
            )


if __name__ == "__main__":
    unittest.main()
