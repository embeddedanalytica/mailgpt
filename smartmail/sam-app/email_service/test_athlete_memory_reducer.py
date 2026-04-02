"""Unit tests for AM2 candidate-operation memory reducer."""

import unittest

from athlete_memory_reducer import apply_candidate_refresh, CandidateReducerError


def _fact(
    *,
    memory_note_id: str = "f1",
    fact_type: str = "goal",
    fact_key: str = "goal:marathon",
    summary: str = "Run a marathon",
    importance: str = "high",
    created_at: int = 1000,
    updated_at: int = 1000,
    last_confirmed_at: int = 1000,
) -> dict:
    return {
        "memory_note_id": memory_note_id,
        "fact_type": fact_type,
        "fact_key": fact_key,
        "summary": summary,
        "importance": importance,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


def _continuity():
    return {
        "summary": "Athlete completed first tempo run",
        "last_recommendation": "Add strides next week",
        "open_loops": ["Confirm tempo pace felt manageable"],
    }


def _output(candidates=None, continuity=None):
    return {
        "candidates": candidates or [],
        "continuity": continuity or _continuity(),
    }


class TestApplyCandidateRefresh(unittest.TestCase):
    """Tests for apply_candidate_refresh (AM2 reducer)."""

    def setUp(self):
        self.now = 1710700000

    def test_empty_candidates_preserves_facts(self):
        facts = [_fact()]
        result = apply_candidate_refresh(_output(), facts, self.now)
        self.assertEqual(len(result["memory_notes"]), 1)
        self.assertEqual(result["memory_notes"][0]["summary"], "Run a marathon")

    def test_upsert_creates_new_fact(self):
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "goal",
                "fact_key": "Half Marathon",
                "summary": "Run a half marathon in May",
                "importance": "high",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [],
            self.now,
        )
        notes = result["memory_notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["summary"], "Run a half marathon in May")
        self.assertEqual(notes[0]["fact_key"], "goal:half-marathon")
        self.assertEqual(notes[0]["created_at"], self.now)
        self.assertEqual(notes[0]["updated_at"], self.now)
        self.assertEqual(notes[0]["last_confirmed_at"], self.now)

    def test_upsert_updates_existing_fact(self):
        existing = _fact(memory_note_id="f1", created_at=900, updated_at=900)
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "target_id": "f1",
                "summary": "Updated marathon goal to sub-3:30",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        notes = result["memory_notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["summary"], "Updated marathon goal to sub-3:30")
        # created_at preserved
        self.assertEqual(notes[0]["created_at"], 900)
        # updated_at refreshed
        self.assertEqual(notes[0]["updated_at"], self.now)

    def test_confirm_refreshes_last_confirmed_at(self):
        existing = _fact(memory_note_id="f1", last_confirmed_at=900)
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "confirm",
                "target_id": "f1",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        self.assertEqual(result["memory_notes"][0]["last_confirmed_at"], self.now)

    def test_retire_deletes_fact(self):
        existing = _fact(memory_note_id="f1")
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "retire",
                "target_id": "f1",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        self.assertEqual(len(result["memory_notes"]), 0)

    def test_unknown_target_id_rejects_batch(self):
        with self.assertRaises(CandidateReducerError):
            apply_candidate_refresh(
                _output(candidates=[{
                    "action": "confirm",
                    "target_id": "nonexistent",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                }]),
                [],
                self.now,
            )

    def test_unknown_retire_target_id_is_skipped(self):
        existing = _fact(memory_note_id="f1")
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "retire",
                "target_id": "nonexistent",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        self.assertEqual(len(result["memory_notes"]), 1)
        self.assertEqual(result["memory_notes"][0]["memory_note_id"], "f1")

    def test_retire_can_resolve_by_fact_key_when_target_id_is_wrong(self):
        existing = _fact(
            memory_note_id="f1",
            fact_type="schedule",
            fact_key="schedule:recovery-only-sunday",
            summary="Sunday is usually recovery-only due to match fatigue.",
        )
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "retire",
                "target_id": "bad-id",
                "fact_key": "schedule:recovery-only-sunday",
                "summary": "Retire the old Sunday recovery-only note",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        self.assertEqual(result["memory_notes"], [])

    def test_upsert_can_supersede_old_schedule_fact_by_fact_key(self):
        existing = _fact(
            memory_note_id="f1",
            fact_type="schedule",
            fact_key="schedule:thursday-doubles",
            summary="Thursday has been a fixed doubles night every week.",
            importance="high",
        )
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "schedule",
                "fact_key": "Tuesday league slot",
                "summary": "Tuesday is now the fixed weekly league slot.",
                "importance": "high",
                "supersedes_fact_keys": ["schedule:thursday-doubles"],
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        notes = result["memory_notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["fact_key"], "schedule:tuesday-league-slot")
        self.assertNotIn("thursday", notes[0]["summary"].lower())

    def test_superseded_phrase_is_removed_from_continuity(self):
        existing = _fact(
            memory_note_id="f1",
            fact_type="schedule",
            fact_key="schedule:saturday-long-erg",
            summary="Saturday has usually been the long erg session.",
            importance="high",
        )
        result = apply_candidate_refresh(
            _output(
                candidates=[{
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "Sunday long water session",
                    "summary": "Sunday is now the long water session (replaces prior Saturday long erg slot).",
                    "importance": "high",
                    "supersedes_fact_keys": ["schedule:saturday-long-erg"],
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                }],
                continuity={
                    "summary": "Sunday is now the long water session; the old Saturday long erg slot is retired.",
                    "last_recommendation": "Retire the Saturday long erg slot and plan around Sunday.",
                    "open_loops": ["Confirm timing for the new Sunday long water session."],
                },
            ),
            [existing],
            self.now,
        )
        continuity = result["continuity_summary"]
        self.assertNotIn("saturday long erg", continuity["summary"].lower())
        self.assertNotIn("saturday long erg", continuity["last_recommendation"].lower())

    def test_importance_enforcement_goal_forced_high(self):
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "goal",
                "fact_key": "Marathon",
                "summary": "Run a marathon",
                "importance": "medium",  # Should be forced to high
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [],
            self.now,
        )
        self.assertEqual(result["memory_notes"][0]["importance"], "high")

    def test_importance_enforcement_constraint_forced_high(self):
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "constraint",
                "fact_key": "Knee injury",
                "summary": "Bad knee",
                "importance": "medium",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [],
            self.now,
        )
        self.assertEqual(result["memory_notes"][0]["importance"], "high")

    def test_budget_eviction_medium_first(self):
        # Create 7 existing high-importance facts + 1 new medium
        existing = [
            _fact(
                memory_note_id=f"f{i}",
                fact_key=f"goal:fact-{i}",
                importance="high",
                last_confirmed_at=1000 + i,
            )
            for i in range(7)
        ]
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "preference",
                "fact_key": "Extra pref",
                "summary": "Prefers morning runs",
                "importance": "medium",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            existing,
            self.now,
        )
        # Medium fact should be evicted, 7 high kept
        self.assertEqual(len(result["memory_notes"]), 7)
        for note in result["memory_notes"]:
            self.assertEqual(note["importance"], "high")

    def test_budget_eviction_prefers_other_over_schedule(self):
        # 6 high-importance goals + 1 medium schedule + 1 medium other = 8 facts, budget 7
        # The medium "other" fact should be evicted before the medium "schedule" fact
        existing = [
            _fact(
                memory_note_id=f"g{i}",
                fact_type="goal",
                fact_key=f"goal:goal-{i}",
                importance="high",
                last_confirmed_at=1000 + i,
            )
            for i in range(6)
        ]
        existing.append(_fact(
            memory_note_id="sched1",
            fact_type="schedule",
            fact_key="schedule:weekday-trainer",
            summary="Indoor trainer weekdays",
            importance="medium",
            last_confirmed_at=900,  # older than the other fact
        ))
        existing.append(_fact(
            memory_note_id="other1",
            fact_type="other",
            fact_key="other:fan-detail",
            summary="Uses a floor fan during indoor sessions",
            importance="medium",
            last_confirmed_at=1200,  # newer than the schedule fact
        ))
        result = apply_candidate_refresh(_output(), existing, self.now)
        self.assertEqual(len(result["memory_notes"]), 7)
        surviving_ids = {n["memory_note_id"] for n in result["memory_notes"]}
        self.assertIn("sched1", surviving_ids, "Schedule fact should survive over other fact")
        self.assertNotIn("other1", surviving_ids, "Other fact should be evicted first")

    def test_admission_gate_rejects_low_value_when_budget_tight(self):
        # 5 existing facts (at ADMISSION_THRESHOLD) — new medium "other" should be rejected
        existing = [
            _fact(
                memory_note_id=f"f{i}",
                fact_type="goal" if i < 3 else "schedule",
                fact_key=f"goal:fact-{i}" if i < 3 else f"schedule:sched-{i}",
                importance="high",
                last_confirmed_at=1000 + i,
            )
            for i in range(5)
        ]
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "other",
                "fact_key": "Fan detail",
                "summary": "Uses a floor fan during indoor sessions",
                "importance": "medium",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            existing,
            self.now,
        )
        # The "other" fact should have been rejected at the gate
        self.assertEqual(len(result["memory_notes"]), 5)
        fact_types = {n["fact_type"] for n in result["memory_notes"]}
        self.assertNotIn("other", fact_types)

    def test_admission_gate_allows_high_value_when_budget_tight(self):
        # 5 existing facts — new "schedule" fact should still be admitted
        existing = [
            _fact(
                memory_note_id=f"f{i}",
                fact_key=f"goal:fact-{i}",
                importance="high",
                last_confirmed_at=1000 + i,
            )
            for i in range(5)
        ]
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "schedule",
                "fact_key": "Weekly trainer",
                "summary": "Indoor trainer weekdays before work",
                "importance": "high",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            existing,
            self.now,
        )
        self.assertEqual(len(result["memory_notes"]), 6)

    def test_admission_gate_allows_low_value_under_threshold(self):
        # 4 existing facts (below ADMISSION_THRESHOLD=5) — medium "other" should be admitted
        existing = [
            _fact(
                memory_note_id=f"f{i}",
                fact_key=f"goal:fact-{i}",
                importance="high",
                last_confirmed_at=1000 + i,
            )
            for i in range(4)
        ]
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "fact_type": "other",
                "fact_key": "Power meter",
                "summary": "Has power meter on gravel bike",
                "importance": "medium",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            existing,
            self.now,
        )
        self.assertEqual(len(result["memory_notes"]), 5)

    def test_high_importance_overflow_accepted(self):
        # 8 high-importance facts should all be kept (overflow allowed)
        existing = [
            _fact(
                memory_note_id=f"f{i}",
                fact_type="goal",
                fact_key=f"goal:fact-{i}",
                importance="high",
                last_confirmed_at=1000 + i,
            )
            for i in range(8)
        ]
        result = apply_candidate_refresh(_output(), existing, self.now)
        self.assertEqual(len(result["memory_notes"]), 8)

    def test_continuity_passthrough(self):
        result = apply_candidate_refresh(_output(), [], self.now)
        cs = result["continuity_summary"]
        self.assertEqual(cs["summary"], "Athlete completed first tempo run")
        self.assertEqual(cs["last_recommendation"], "Add strides next week")
        self.assertEqual(cs["open_loops"], ["Confirm tempo pace felt manageable"])
        self.assertEqual(cs["updated_at"], self.now)

    def test_upsert_with_target_id_preserves_fact_type_and_key(self):
        existing = _fact(
            memory_note_id="f1",
            fact_type="schedule",
            fact_key="schedule:weekly-structure",
        )
        result = apply_candidate_refresh(
            _output(candidates=[{
                "action": "upsert",
                "target_id": "f1",
                "summary": "Updated to 5 days/week",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }]),
            [existing],
            self.now,
        )
        note = result["memory_notes"][0]
        self.assertEqual(note["fact_type"], "schedule")
        self.assertEqual(note["fact_key"], "schedule:weekly-structure")


if __name__ == "__main__":
    unittest.main()
