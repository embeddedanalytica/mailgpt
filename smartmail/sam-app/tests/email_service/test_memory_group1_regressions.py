"""Targeted deterministic regressions for Group 1 open memory defects (sectioned memory)."""

import unittest
import uuid
from unittest import mock

from memory_compiler import compile_prompt_memory
from sectioned_memory_contract import (
    VALID_STORAGE_BUCKETS,
    empty_sectioned_memory,
    normalize_fact_key,
)
from sectioned_memory_reducer import SectionedCandidateReducerError, apply_sectioned_refresh
from skills.memory.sectioned.errors import SectionedMemoryRefreshError
from skills.memory.sectioned.runner import run_sectioned_memory_refresh
from skills.memory.sectioned.validator import validate_sectioned_candidate_response


def _continuity() -> dict:
    return {
        "summary": "Current coaching context updated.",
        "last_recommendation": "Use the updated current schedule and constraints going forward.",
        "open_loops": [],
    }


def _output(candidates) -> dict:
    return {"candidates": candidates, "continuity": _continuity()}


def _validated(candidates) -> dict:
    return validate_sectioned_candidate_response(_output(candidates))


def _flat_row(
    *,
    memory_note_id: str,
    fact_type: str,
    fact_key: str,
    summary: str,
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


def _stable_memory_id(label: str) -> str:
    """Deterministic UUID for tests (MemoryFact requires UUID-shaped ids)."""
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, f"group1.regression.{label}"))


def _flat_to_sectioned(*rows: dict) -> dict:
    """Map legacy flat bench rows into persisted sectioned memory."""
    mem = empty_sectioned_memory()
    for f in rows:
        mid = _stable_memory_id(f["memory_note_id"])
        ft = f["fact_type"]
        fk = f["fact_key"]
        summary = f["summary"]
        imp = f.get("importance", "high")
        ca = f.get("created_at", 1000)
        ua = f.get("updated_at", ca)
        lc = f.get("last_confirmed_at", ca)
        slug = fk.split(":", 1)[1] if ":" in fk else fk

        if ft == "goal":
            bucket = "goals"
            section = "goal"
            subtype = "primary" if imp == "high" else "secondary"
        elif ft == "constraint":
            bucket = "constraints"
            section = "constraint"
            subtype = "injury" if "achilles" in summary.lower() else "logistics"
        elif ft == "schedule":
            bucket = "schedule_anchors"
            section = "schedule_anchor"
            subtype = "recurring_anchor"
        elif ft == "preference":
            bucket = "preferences"
            section = "preference"
            subtype = "communication"
        else:
            bucket = "context_notes"
            section = "context"
            subtype = "life_context" if imp == "high" else "other"

        canon = normalize_fact_key(section, slug)
        mem[bucket]["active"].append(
            {
                "memory_id": mid,
                "section": section,
                "subtype": subtype,
                "fact_key": canon,
                "summary": summary,
                "status": "active",
                "supersedes": [],
                "created_at": ca,
                "updated_at": ua,
                "last_confirmed_at": lc,
            }
        )
    return mem


def _active_ids(memory: dict) -> set[str]:
    ids: set[str] = set()
    for bucket in VALID_STORAGE_BUCKETS:
        for fact in memory[bucket]["active"]:
            mid = fact.get("memory_id")
            if isinstance(mid, str):
                ids.add(mid)
    return ids


def _apply_refresh_sequence(sectioned: dict, *candidate_batches):
    current = sectioned
    now_epoch = 1710700000
    for index, candidates in enumerate(candidate_batches):
        out = apply_sectioned_refresh(_validated(candidates), current, now_epoch=now_epoch + index)
        current = out["sectioned_memory"]
    return current


class TestGroup1Bug10SeasonGoalCanonicalization(unittest.TestCase):
    def test_bug10_basketball_season_goal_paraphrase_is_rejected_as_duplicate_goal_alias(self):
        existing = _flat_to_sectioned(
            _flat_row(
                memory_note_id="goal1",
                fact_type="goal",
                fact_key="goal:summer-rec-league",
                summary="Train for the summer rec league.",
                importance="high",
            )
        )

        with self.assertRaises(
            SectionedCandidateReducerError,
            msg=(
                "Bug 10 regression: paraphrased season-goal wording should be recognized as the same goal "
                "and rejected on the create path so a second active goal cannot be created."
            ),
        ):
            apply_sectioned_refresh(
                _validated(
                    [
                        {
                            "action": "upsert",
                            "section": "goal",
                            "subtype": "primary",
                            "fact_key": "summer recreational basketball league",
                            "summary": "Primary goal is the summer recreational basketball league.",
                            "evidence_source": "athlete_email",
                            "evidence_strength": "explicit",
                        }
                    ]
                ),
                existing,
                now_epoch=1710700000,
            )


class TestGroup1Bug15RuleEngineStateConfirmOnly(unittest.TestCase):
    def test_bug15_rule_engine_state_targeted_upsert_is_rejected(self):
        payload = {
            "candidates": [
                {
                    "action": "upsert",
                    "target_id": "goal1",
                    "summary": "Updated from rule engine state",
                    "evidence_source": "rule_engine_state",
                    "evidence_strength": "explicit",
                }
            ],
            "continuity": _continuity(),
        }

        with self.assertRaisesRegex(
            SectionedMemoryRefreshError,
            "rule_engine_state",
            msg="Bug 15 regression: rule_engine_state should be confirm-only and must not rewrite an existing fact.",
        ):
            validate_sectioned_candidate_response(payload)

    def test_bug15_rule_engine_state_confirm_is_allowed(self):
        payload = {
            "candidates": [
                {
                    "action": "confirm",
                    "target_id": "goal1",
                    "evidence_source": "rule_engine_state",
                    "evidence_strength": "strong_inference",
                }
            ],
            "continuity": _continuity(),
        }

        validated = validate_sectioned_candidate_response(payload)
        self.assertEqual(
            validated["candidates"][0]["action"],
            "confirm",
            msg=f"Expected confirm-only rule_engine_state candidate, got {validated['candidates']}",
        )


class TestGroup1Bug16IdentitySafeMutation(unittest.TestCase):
    def test_bug16_new_create_upsert_with_existing_canonical_key_is_rejected(self):
        existing = _flat_to_sectioned(
            _flat_row(
                memory_note_id="sched1",
                fact_type="schedule",
                fact_key="schedule:weekday-trainer",
                summary="Weekday trainer rides before work.",
                importance="high",
            )
        )

        with self.assertRaises(
            SectionedCandidateReducerError,
            msg=(
                "Bug 16 regression: create-upsert with an already-active canonical key should not mutate "
                "the fact implicitly; it should require an explicit target_id update path."
            ),
        ):
            apply_sectioned_refresh(
                _validated(
                    [
                        {
                            "action": "upsert",
                            "section": "schedule_anchor",
                            "subtype": "recurring_anchor",
                            "fact_key": "weekday trainer",
                            "summary": "Weekday trainer rides now start at 5:45am.",
                            "evidence_source": "athlete_email",
                            "evidence_strength": "explicit",
                        }
                    ]
                ),
                existing,
                now_epoch=1710700000,
            )


class TestGroup1Bug18ReplacementRetirement(unittest.TestCase):
    def test_bug18_reversal_backstop_retries_when_replacement_omits_retire(self):
        existing = _flat_to_sectioned(
            _flat_row(
                memory_note_id="sched1",
                fact_type="schedule",
                fact_key="schedule:tuesday-masters",
                summary="Tuesday masters is the standing weekly swim slot.",
                importance="high",
            )
        )
        interaction_context = {
            "inbound_email": "I switched from Tuesday masters to Wednesday nights.",
            "coach_reply": "Use Wednesday nights as the new anchor.",
        }
        first_attempt = _output(
            [
                {
                    "action": "upsert",
                    "section": "schedule_anchor",
                    "subtype": "recurring_anchor",
                    "fact_key": "Wednesday nights",
                    "summary": "Wednesday nights are now the standing weekly swim slot.",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                }
            ]
        )
        second_attempt = _output(
            [
                {
                    "action": "retire",
                    "target_id": _stable_memory_id("sched1"),
                    "section": "schedule_anchor",
                    "summary": "Retire the old Tuesday masters slot.",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
                {
                    "action": "upsert",
                    "section": "schedule_anchor",
                    "subtype": "recurring_anchor",
                    "fact_key": "Wednesday nights",
                    "summary": "Wednesday nights are now the standing weekly swim slot.",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ]
        )

        with mock.patch(
            "skills.memory.sectioned.runner._run_single_attempt",
            side_effect=[
                validate_sectioned_candidate_response(first_attempt),
                validate_sectioned_candidate_response(second_attempt),
            ],
        ) as run_attempt:
            validated = run_sectioned_memory_refresh(
                current_memory=existing,
                current_continuity=None,
                interaction_context=interaction_context,
            )

        self.assertEqual(
            run_attempt.call_count,
            2,
            msg=(
                "Bug 18 regression: explicit replacement language should trigger a retry when the first "
                "candidate batch adds the new schedule but omits retiring the old one."
            ),
        )
        self.assertEqual(
            [candidate["action"] for candidate in validated["candidates"]],
            ["retire", "upsert"],
            msg=f"Expected retry batch to contain retire+upsert, got {validated['candidates']}",
        )


class TestGroup1Bug19BudgetPressure(unittest.TestCase):
    def test_bug19_am005_primary_goal_and_compiler_priority_under_sectioned_caps(self):
        """Flat AM2 dropped facts under a global 7-fact cap; sectioned storage keeps per-bucket truths."""

        existing = _flat_to_sectioned(
            _flat_row(
                memory_note_id="g1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                last_confirmed_at=1101,
            ),
            _flat_row(
                memory_note_id="g2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                last_confirmed_at=1102,
            ),
            _flat_row(
                memory_note_id="g3",
                fact_type="goal",
                fact_key="goal:durability",
                summary="Build durability through the season.",
                last_confirmed_at=1103,
            ),
            _flat_row(
                memory_note_id="g4",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                last_confirmed_at=1104,
            ),
            _flat_row(
                memory_note_id="g5",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                last_confirmed_at=1105,
            ),
            _flat_row(
                memory_note_id="goal-season",
                fact_type="goal",
                fact_key="goal:1500-free",
                summary="Primary competition goal is the summer 1500 free.",
                importance="medium",
                last_confirmed_at=900,
            ),
            _flat_row(
                memory_note_id="schedule-anchor",
                fact_type="schedule",
                fact_key="schedule:before-work",
                summary="Swims happen before work.",
                importance="medium",
                last_confirmed_at=901,
            ),
            _flat_row(
                memory_note_id="detail1",
                fact_type="schedule",
                fact_key="schedule:saturday-stroke-clinic",
                summary="Saturday stroke clinic is now a recurring technical session.",
                importance="medium",
                last_confirmed_at=1200,
            ),
            _flat_row(
                memory_note_id="detail2",
                fact_type="other",
                fact_key="other:lane-space",
                summary="Lane space has been tight at the pool.",
                importance="medium",
                last_confirmed_at=1201,
            ),
            _flat_row(
                memory_note_id="detail3",
                fact_type="other",
                fact_key="other:pull-set-progress",
                summary="Pull sets have felt better recently.",
                importance="medium",
                last_confirmed_at=1202,
            ),
        )

        result = apply_sectioned_refresh(_validated([]), existing, now_epoch=1710700000)
        mem = result["sectioned_memory"]
        surviving_ids = _active_ids(mem)

        self.assertIn(_stable_memory_id("goal-season"), surviving_ids, msg=f"surviving_ids={sorted(surviving_ids)}")
        self.assertIn(_stable_memory_id("detail2"), surviving_ids, msg="sectioned buckets preserve context notes until cap/replace rules apply")

        compiled = compile_prompt_memory(mem, None)
        self.assertEqual(len(compiled["priority_facts"]), 6, msg="all goals + constraints must compile into priority_facts")
        goal_keys = {f.get("fact_key") for f in compiled["priority_facts"] if f.get("section") == "goal"}
        self.assertIn("goal:1500-free", goal_keys)

    def test_bug19_am012_primary_season_goal_retained_compiler_covers_goals(self):
        existing = _flat_to_sectioned(
            _flat_row(
                memory_note_id="h1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                last_confirmed_at=1101,
            ),
            _flat_row(
                memory_note_id="h2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                last_confirmed_at=1102,
            ),
            _flat_row(
                memory_note_id="h3",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                last_confirmed_at=1103,
            ),
            _flat_row(
                memory_note_id="h4",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                last_confirmed_at=1104,
            ),
            _flat_row(
                memory_note_id="h5",
                fact_type="constraint",
                fact_key="constraint:family",
                summary="Family travel affects some weekends.",
                last_confirmed_at=1105,
            ),
            _flat_row(
                memory_note_id="goal-season",
                fact_type="goal",
                fact_key="goal:summer-rec-league",
                summary="Primary competition goal is the summer rec league.",
                importance="medium",
                last_confirmed_at=900,
            ),
            _flat_row(
                memory_note_id="schedule-late",
                fact_type="schedule",
                fact_key="schedule:after-8pm",
                summary="Most training happens after 8pm because of work.",
                importance="medium",
                last_confirmed_at=901,
            ),
            _flat_row(
                memory_note_id="schedule-conditioning",
                fact_type="schedule",
                fact_key="schedule:conditioning-day",
                summary="One conditioning day is part of the weekly structure.",
                importance="medium",
                last_confirmed_at=1200,
            ),
            _flat_row(
                memory_note_id="schedule-shooting",
                fact_type="schedule",
                fact_key="schedule:saturday-shooting-group",
                summary="Saturday shooting group is a recurring session.",
                importance="medium",
                last_confirmed_at=1201,
            ),
            _flat_row(
                memory_note_id="detail-noise",
                fact_type="other",
                fact_key="other:first-step",
                summary="Keeps first-step quickness sharp.",
                importance="medium",
                last_confirmed_at=1202,
            ),
        )

        result = apply_sectioned_refresh(_validated([]), existing, now_epoch=1710700000)
        mem = result["sectioned_memory"]
        self.assertIn(_stable_memory_id("goal-season"), _active_ids(mem))

        compiled = compile_prompt_memory(mem, None)
        self.assertEqual(len(compiled["priority_facts"]), 6)
        self.assertTrue(
            any("summer rec league" in (f.get("summary") or "").lower() for f in compiled["priority_facts"]),
            msg="primary season goal must remain addressable via priority_facts",
        )


class TestGroup1Bug19MisclassifiedGoalInScheduleBucket(unittest.TestCase):
    """Old flat AM2 could misfile a primary goal as a medium schedule fact and evict it globally.

    Sectioned storage isolates buckets: schedule pressure does not remove goals.active facts.
    """

    def test_bug19_misfiled_goal_as_schedule_survives_schedule_anchor_pressure(self):
        base = _flat_to_sectioned(
            _flat_row(
                memory_note_id="h1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                last_confirmed_at=1101,
            ),
            _flat_row(
                memory_note_id="h2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                last_confirmed_at=1102,
            ),
            _flat_row(
                memory_note_id="h3",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                last_confirmed_at=1103,
            ),
            _flat_row(
                memory_note_id="h4",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                last_confirmed_at=1104,
            ),
            _flat_row(
                memory_note_id="h5",
                fact_type="constraint",
                fact_key="constraint:family",
                summary="Family travel affects some weekends.",
                last_confirmed_at=1105,
            ),
        )
        # Misclassified "primary event goal" lives in schedule_anchors (simulates bad LLM classification).
        bad = _flat_to_sectioned(
            _flat_row(
                memory_note_id="mis-1500",
                fact_type="schedule",
                fact_key="schedule:1500-free",
                summary="Primary competition goal is the summer 1500 free.",
                importance="medium",
                last_confirmed_at=800,
            )
        )
        for bucket in VALID_STORAGE_BUCKETS:
            base[bucket]["active"].extend(bad[bucket]["active"])

        final_mem = _apply_refresh_sequence(
            base,
            [
                {
                    "action": "upsert",
                    "section": "schedule_anchor",
                    "subtype": "recurring_anchor",
                    "fact_key": "before work",
                    "summary": "Swims happen before work.",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
                {
                    "action": "upsert",
                    "section": "schedule_anchor",
                    "subtype": "recurring_anchor",
                    "fact_key": "saturday stroke clinic",
                    "summary": "Saturday stroke clinic is now a recurring technical session.",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ],
            [
                {
                    "action": "upsert",
                    "section": "context",
                    "subtype": "other",
                    "fact_key": "lane space",
                    "summary": "Lane space has been tight at the pool.",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ],
        )

        keys = {f["fact_key"] for b in VALID_STORAGE_BUCKETS for f in final_mem[b]["active"]}
        self.assertIn(
            "schedule_anchor:1500-free",
            keys,
            msg=f"misfiled primary goal row should remain in schedule_anchors under sectioned caps: keys={sorted(keys)}",
        )

        compiled = compile_prompt_memory(final_mem, None)
        blob = " ".join(
            (f.get("summary") or "")
            for f in compiled["priority_facts"] + compiled["structure_facts"] + compiled["context_facts"]
        ).lower()
        self.assertIn("1500", blob, msg="compiler surfaces misfiled copy via structure_facts / priority_facts")


class TestGroup1Bug19CompilerGoalsUnderLoad(unittest.TestCase):
    def test_compile_includes_all_goals_when_many_schedule_anchors_exist(self):
        rows = []
        for i in range(4):
            rows.append(
                _flat_row(
                    memory_note_id=f"g{i}",
                    fact_type="goal",
                    fact_key=f"goal:race-{i}",
                    summary=f"Goal {i}.",
                    importance="high" if i < 2 else "medium",
                )
            )
        for i in range(8):
            rows.append(
                _flat_row(
                    memory_note_id=f"s{i}",
                    fact_type="schedule",
                    fact_key=f"schedule:anchor-{i}",
                    summary=f"Schedule anchor {i}.",
                    importance="medium",
                )
            )
        mem = _flat_to_sectioned(*rows)
        compiled = compile_prompt_memory(mem, None)
        self.assertEqual(len(compiled["priority_facts"]), 4)
        self.assertLessEqual(len(compiled["structure_facts"]), 4)


if __name__ == "__main__":
    unittest.main()
