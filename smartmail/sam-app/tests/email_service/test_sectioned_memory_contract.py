"""Tests for sectioned_memory_contract (PR 1)."""

from __future__ import annotations

import unittest
import uuid

import sectioned_memory_contract as smc


def _uid() -> str:
    return str(uuid.uuid4())


class TestMemoryFact(unittest.TestCase):
    def test_valid_active_fact(self) -> None:
        mid = _uid()
        d = {
            "memory_id": mid,
            "section": smc.SECTION_GOAL,
            "subtype": "primary",
            "fact_key": "goal:marathon",
            "summary": "Train for spring marathon",
            "status": smc.STATUS_ACTIVE,
            "supersedes": [],
            "created_at": 1_700_000_000,
            "updated_at": 1_700_000_000,
            "last_confirmed_at": 1_700_000_000,
        }
        fact = smc.MemoryFact.from_dict(d)
        self.assertEqual(fact.memory_id, mid)
        self.assertEqual(fact.section, smc.SECTION_GOAL)
        self.assertIsNone(fact.retirement_reason)
        self.assertIsNone(fact.retired_at)
        self.assertEqual(smc.validate_memory_fact(d)["memory_id"], mid)

    def test_invalid_section(self) -> None:
        with self.assertRaises(smc.SectionedMemoryContractError):
            smc.MemoryFact.from_dict(
                {
                    "memory_id": _uid(),
                    "section": "not_a_section",
                    "subtype": "primary",
                    "fact_key": "x:y",
                    "summary": "s",
                    "status": smc.STATUS_ACTIVE,
                    "supersedes": [],
                    "created_at": 1,
                    "updated_at": 1,
                    "last_confirmed_at": 1,
                }
            )

    def test_invalid_subtype_for_section(self) -> None:
        with self.assertRaises(smc.SectionedMemoryContractError):
            smc.MemoryFact.from_dict(
                {
                    "memory_id": _uid(),
                    "section": smc.SECTION_GOAL,
                    "subtype": "hard_blocker",
                    "fact_key": "goal:x",
                    "summary": "s",
                    "status": smc.STATUS_ACTIVE,
                    "supersedes": [],
                    "created_at": 1,
                    "updated_at": 1,
                    "last_confirmed_at": 1,
                }
            )

    def test_retired_requires_reason_and_retired_at(self) -> None:
        mid = _uid()
        base = {
            "memory_id": mid,
            "section": smc.SECTION_CONSTRAINT,
            "subtype": "injury",
            "fact_key": "constraint:knee",
            "summary": "Bad knee",
            "status": smc.STATUS_RETIRED,
            "supersedes": [],
            "created_at": 1,
            "updated_at": 1,
            "last_confirmed_at": 1,
        }
        with self.assertRaises(smc.SectionedMemoryContractError):
            smc.MemoryFact.from_dict({**base, "retirement_reason": smc.RETIREMENT_RESOLVED})
        with self.assertRaises(smc.SectionedMemoryContractError):
            smc.MemoryFact.from_dict({**base, "retired_at": 2})
        ok = {
            **base,
            "retirement_reason": smc.RETIREMENT_RESOLVED,
            "retired_at": 2,
        }
        f = smc.MemoryFact.from_dict(ok)
        self.assertEqual(f.retired_at, 2)


class TestNormalizeFactKey(unittest.TestCase):
    def test_slug_and_prefix(self) -> None:
        self.assertEqual(
            smc.normalize_fact_key(smc.SECTION_SCHEDULE_ANCHOR, "Tuesday evening swim"),
            "schedule_anchor:tuesday-evening-swim",
        )

    def test_invalid_section(self) -> None:
        with self.assertRaises(smc.SectionedMemoryContractError):
            smc.normalize_fact_key("schedule", "x")


class TestEmptyAndValidateSectionedMemory(unittest.TestCase):
    def test_empty_helper_validates(self) -> None:
        empty = smc.empty_sectioned_memory()
        out = smc.validate_sectioned_memory(empty)
        self.assertEqual(out, empty)
        self.assertEqual(set(out.keys()), set(smc.VALID_STORAGE_BUCKETS))

    def test_valid_minimal_structure(self) -> None:
        mid = _uid()
        m = smc.empty_sectioned_memory()
        fact = {
            "memory_id": mid,
            "section": smc.SECTION_GOAL,
            "subtype": "primary",
            "fact_key": "goal:marathon",
            "summary": "Marathon",
            "status": smc.STATUS_ACTIVE,
            "supersedes": [],
            "created_at": 100,
            "updated_at": 100,
            "last_confirmed_at": 100,
        }
        m["goals"]["active"].append(fact)
        smc.validate_sectioned_memory(m)

    def test_rejects_duplicate_memory_id_across_buckets(self) -> None:
        mid = _uid()
        base = {
            "memory_id": mid,
            "subtype": "primary",
            "fact_key": "goal:a",
            "summary": "s",
            "status": smc.STATUS_ACTIVE,
            "supersedes": [],
            "created_at": 1,
            "updated_at": 1,
            "last_confirmed_at": 1,
        }
        m = smc.empty_sectioned_memory()
        m["goals"]["active"].append({**base, "section": smc.SECTION_GOAL})
        m["constraints"]["active"].append(
            {
                **base,
                "section": smc.SECTION_CONSTRAINT,
                "subtype": "injury",
                "fact_key": "constraint:b",
            }
        )
        with self.assertRaises(smc.SectionedMemoryContractError) as ctx:
            smc.validate_sectioned_memory(m)
        self.assertIn("duplicate memory_id", str(ctx.exception))

    def test_rejects_duplicate_fact_key_in_same_section_active(self) -> None:
        mid1, mid2 = _uid(), _uid()
        fk = "goal:same-key"
        m = smc.empty_sectioned_memory()
        for mid in (mid1, mid2):
            m["goals"]["active"].append(
                {
                    "memory_id": mid,
                    "section": smc.SECTION_GOAL,
                    "subtype": "secondary",
                    "fact_key": fk,
                    "summary": "s",
                    "status": smc.STATUS_ACTIVE,
                    "supersedes": [],
                    "created_at": 1,
                    "updated_at": 1,
                    "last_confirmed_at": 1,
                }
            )
        with self.assertRaises(smc.SectionedMemoryContractError) as ctx:
            smc.validate_sectioned_memory(m)
        self.assertIn("duplicate fact_key", str(ctx.exception))

    def test_rejects_wrong_section_for_bucket(self) -> None:
        m = smc.empty_sectioned_memory()
        m["goals"]["active"].append(
            {
                "memory_id": _uid(),
                "section": smc.SECTION_CONSTRAINT,
                "subtype": "injury",
                "fact_key": "constraint:x",
                "summary": "s",
                "status": smc.STATUS_ACTIVE,
                "supersedes": [],
                "created_at": 1,
                "updated_at": 1,
                "last_confirmed_at": 1,
            }
        )
        with self.assertRaises(smc.SectionedMemoryContractError) as ctx:
            smc.validate_sectioned_memory(m)
        self.assertIn("expected", str(ctx.exception))

    def test_active_fact_in_retired_list_rejected(self) -> None:
        m = smc.empty_sectioned_memory()
        m["goals"]["retired"].append(
            {
                "memory_id": _uid(),
                "section": smc.SECTION_GOAL,
                "subtype": "primary",
                "fact_key": "goal:x",
                "summary": "s",
                "status": smc.STATUS_ACTIVE,
                "supersedes": [],
                "created_at": 1,
                "updated_at": 1,
                "last_confirmed_at": 1,
            }
        )
        with self.assertRaises(smc.SectionedMemoryContractError):
            smc.validate_sectioned_memory(m)


class TestCapsAndConstants(unittest.TestCase):
    def test_caps_exposed(self) -> None:
        self.assertEqual(smc.ACTIVE_CAP_BY_BUCKET[smc.BUCKET_GOALS], 4)
        self.assertEqual(smc.ACTIVE_CAP_BY_BUCKET[smc.BUCKET_CONSTRAINTS], 8)
        self.assertEqual(smc.ACTIVE_CAP_BY_BUCKET[smc.BUCKET_SCHEDULE_ANCHORS], 8)
        self.assertEqual(smc.ACTIVE_CAP_BY_BUCKET[smc.BUCKET_PREFERENCES], 4)
        self.assertEqual(smc.ACTIVE_CAP_BY_BUCKET[smc.BUCKET_CONTEXT_NOTES], 4)
        self.assertEqual(smc.RETIRED_CAP_PER_SECTION, 5)

    def test_active_cap_enforced(self) -> None:
        m = smc.empty_sectioned_memory()
        for i in range(5):
            m["goals"]["active"].append(
                {
                    "memory_id": _uid(),
                    "section": smc.SECTION_GOAL,
                    "subtype": "primary",
                    "fact_key": f"goal:{i}",
                    "summary": "s",
                    "status": smc.STATUS_ACTIVE,
                    "supersedes": [],
                    "created_at": 1,
                    "updated_at": 1,
                    "last_confirmed_at": 1,
                }
            )
        with self.assertRaises(smc.SectionedMemoryContractError) as ctx:
            smc.validate_sectioned_memory(m)
        self.assertIn("exceeds cap", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
