"""Targeted deterministic regressions for Group 1 open memory defects.

These tests are intentionally named after the backlog bug ids so the expected
behavior is explicit when a contract changes or a bug is fixed.
"""

import unittest
from unittest import mock

from athlete_memory_reducer import CandidateReducerError, apply_candidate_refresh
from skills.memory.unified.errors import MemoryRefreshError
from skills.memory.unified.runner import run_candidate_memory_refresh
from skills.memory.unified.validator import validate_candidate_memory_response


def _fact(
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


def _continuity() -> dict:
    return {
        "summary": "Current coaching context updated.",
        "last_recommendation": "Use the updated current schedule and constraints going forward.",
        "open_loops": [],
    }


def _output(candidates) -> dict:
    return {"candidates": candidates, "continuity": _continuity()}


def _validated_output(candidates) -> dict:
    return validate_candidate_memory_response(_output(candidates))


def _apply_refresh_sequence(existing, *candidate_batches):
    current = list(existing)
    now_epoch = 1710700000
    for index, candidates in enumerate(candidate_batches):
        result = apply_candidate_refresh(
            _validated_output(candidates),
            current,
            now_epoch=now_epoch + index,
        )
        current = result["memory_notes"]
    return current


class TestGroup1Bug10SeasonGoalCanonicalization(unittest.TestCase):
    def test_bug10_basketball_season_goal_paraphrase_is_rejected_as_duplicate_goal_alias(self):
        """AM-012 paraphrases should not create a second active goal."""
        existing = _fact(
            memory_note_id="goal1",
            fact_type="goal",
            fact_key="goal:summer-rec-league",
            summary="Train for the summer rec league.",
            importance="high",
        )

        with self.assertRaises(
            CandidateReducerError,
            msg=(
                "Bug 10 regression: paraphrased season-goal wording should be recognized as the same goal "
                "and rejected on the create path so a second active goal cannot be created."
            ),
        ):
            apply_candidate_refresh(
                _output([
                    {
                        "action": "upsert",
                        "fact_type": "goal",
                        "fact_key": "summer recreational basketball league",
                        "summary": "Primary goal is the summer recreational basketball league.",
                        "importance": "high",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ]),
                [existing],
                now_epoch=1710700000,
            )


class TestGroup1Bug15RuleEngineStateConfirmOnly(unittest.TestCase):
    def test_bug15_rule_engine_state_targeted_upsert_is_rejected(self):
        payload = {
            "candidates": [
                {
                    "action": "upsert",
                    "target_id": "goal1",
                    "fact_type": None,
                    "fact_key": None,
                    "summary": "Updated from rule engine state",
                    "importance": None,
                    "supersedes_fact_keys": None,
                    "evidence_source": "rule_engine_state",
                    "evidence_strength": "explicit",
                }
            ],
            "continuity": _continuity(),
        }

        with self.assertRaisesRegex(
            MemoryRefreshError,
            "rule_engine_state",
            msg="Bug 15 regression: rule_engine_state should be confirm-only and must not rewrite an existing fact.",
        ):
            validate_candidate_memory_response(payload)

    def test_bug15_rule_engine_state_confirm_is_allowed(self):
        payload = {
            "candidates": [
                {
                    "action": "confirm",
                    "target_id": "goal1",
                    "fact_type": None,
                    "fact_key": None,
                    "summary": None,
                    "importance": None,
                    "supersedes_fact_keys": None,
                    "evidence_source": "rule_engine_state",
                    "evidence_strength": "strong_inference",
                }
            ],
            "continuity": _continuity(),
        }

        validated = validate_candidate_memory_response(payload)
        self.assertEqual(
            validated["candidates"][0]["action"],
            "confirm",
            msg=f"Expected confirm-only rule_engine_state candidate, got {validated['candidates']}",
        )


class TestGroup1Bug16IdentitySafeMutation(unittest.TestCase):
    def test_bug16_new_create_upsert_with_existing_canonical_key_is_rejected(self):
        existing = _fact(
            memory_note_id="sched1",
            fact_type="schedule",
            fact_key="schedule:weekday-trainer",
            summary="Weekday trainer rides before work.",
            importance="high",
        )

        with self.assertRaises(
            CandidateReducerError,
            msg=(
                "Bug 16 regression: create-upsert with an already-active canonical key should not mutate "
                "the fact implicitly; it should require an explicit target_id update path."
            ),
        ):
            apply_candidate_refresh(
                _output([
                    {
                        "action": "upsert",
                        "fact_type": "schedule",
                        "fact_key": "weekday trainer",
                        "summary": "Weekday trainer rides now start at 5:45am.",
                        "importance": "high",
                        "evidence_source": "athlete_email",
                        "evidence_strength": "explicit",
                    }
                ]),
                [existing],
                now_epoch=1710700000,
            )


class TestGroup1Bug18ReplacementRetirement(unittest.TestCase):
    def test_bug18_reversal_backstop_retries_when_replacement_omits_retire(self):
        existing = [
            _fact(
                memory_note_id="sched1",
                fact_type="schedule",
                fact_key="schedule:tuesday-masters",
                summary="Tuesday masters is the standing weekly swim slot.",
                importance="high",
            )
        ]
        interaction_context = {
            "inbound_email": "I switched from Tuesday masters to Wednesday nights.",
            "coach_reply": "Use Wednesday nights as the new anchor.",
        }
        first_attempt = _output([
            {
                "action": "upsert",
                "fact_type": "schedule",
                "fact_key": "Wednesday nights",
                "summary": "Wednesday nights are now the standing weekly swim slot.",
                "importance": "high",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            }
        ])
        second_attempt = _output([
            {
                "action": "retire",
                "target_id": "sched1",
                "summary": "Retire the old Tuesday masters slot.",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            },
            {
                "action": "upsert",
                "fact_type": "schedule",
                "fact_key": "Wednesday nights",
                "summary": "Wednesday nights are now the standing weekly swim slot.",
                "importance": "high",
                "evidence_source": "athlete_email",
                "evidence_strength": "explicit",
            },
        ])

        with mock.patch(
            "skills.memory.unified.runner._run_single_attempt",
            side_effect=[first_attempt, second_attempt],
        ) as run_attempt:
            validated = run_candidate_memory_refresh(
                current_memory_notes=existing,
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
    def test_bug19_am005_primary_goal_survives_ahead_of_newer_secondary_medium_facts(self):
        existing = [
            _fact(
                memory_note_id="g1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                importance="high",
                last_confirmed_at=1101,
            ),
            _fact(
                memory_note_id="g2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                importance="high",
                last_confirmed_at=1102,
            ),
            _fact(
                memory_note_id="g3",
                fact_type="goal",
                fact_key="goal:durability",
                summary="Build durability through the season.",
                importance="high",
                last_confirmed_at=1103,
            ),
            _fact(
                memory_note_id="g4",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                importance="high",
                last_confirmed_at=1104,
            ),
            _fact(
                memory_note_id="g5",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                importance="high",
                last_confirmed_at=1105,
            ),
            _fact(
                memory_note_id="goal-season",
                fact_type="goal",
                fact_key="goal:1500-free",
                summary="Primary competition goal is the summer 1500 free.",
                importance="medium",
                last_confirmed_at=900,
            ),
            _fact(
                memory_note_id="schedule-anchor",
                fact_type="schedule",
                fact_key="schedule:before-work",
                summary="Swims happen before work.",
                importance="medium",
                last_confirmed_at=901,
            ),
            _fact(
                memory_note_id="detail1",
                fact_type="schedule",
                fact_key="schedule:saturday-stroke-clinic",
                summary="Saturday stroke clinic is now a recurring technical session.",
                importance="medium",
                last_confirmed_at=1200,
            ),
            _fact(
                memory_note_id="detail2",
                fact_type="other",
                fact_key="other:lane-space",
                summary="Lane space has been tight at the pool.",
                importance="medium",
                last_confirmed_at=1201,
            ),
            _fact(
                memory_note_id="detail3",
                fact_type="other",
                fact_key="other:pull-set-progress",
                summary="Pull sets have felt better recently.",
                importance="medium",
                last_confirmed_at=1202,
            ),
        ]

        result = apply_candidate_refresh(_output([]), existing, now_epoch=1710700000)
        surviving_ids = {note["memory_note_id"] for note in result["memory_notes"]}

        self.assertIn(
            "goal-season",
            surviving_ids,
            msg=(
                "Bug 19 regression (AM-005): primary competition goal should survive budget pressure ahead of "
                "newer secondary medium facts. "
                f"surviving_ids={sorted(surviving_ids)}"
            ),
        )
        self.assertNotIn(
            "detail2",
            surviving_ids,
            msg=(
                "Bug 19 regression (AM-005): secondary detail should be evicted before the primary goal or core schedule "
                f"anchor. surviving_ids={sorted(surviving_ids)}"
            ),
        )
        self.assertNotIn(
            "detail3",
            surviving_ids,
            msg=(
                "Bug 19 regression (AM-005): routine progress detail should be evicted before the primary goal. "
                f"surviving_ids={sorted(surviving_ids)}"
            ),
        )

    def test_bug19_am012_primary_goal_survives_ahead_of_newer_late_added_medium_items(self):
        existing = [
            _fact(
                memory_note_id="h1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                importance="high",
                last_confirmed_at=1101,
            ),
            _fact(
                memory_note_id="h2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                importance="high",
                last_confirmed_at=1102,
            ),
            _fact(
                memory_note_id="h3",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                importance="high",
                last_confirmed_at=1103,
            ),
            _fact(
                memory_note_id="h4",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                importance="high",
                last_confirmed_at=1104,
            ),
            _fact(
                memory_note_id="h5",
                fact_type="constraint",
                fact_key="constraint:family",
                summary="Family travel affects some weekends.",
                importance="high",
                last_confirmed_at=1105,
            ),
            _fact(
                memory_note_id="goal-season",
                fact_type="goal",
                fact_key="goal:summer-rec-league",
                summary="Primary competition goal is the summer rec league.",
                importance="medium",
                last_confirmed_at=900,
            ),
            _fact(
                memory_note_id="schedule-late",
                fact_type="schedule",
                fact_key="schedule:after-8pm",
                summary="Most training happens after 8pm because of work.",
                importance="medium",
                last_confirmed_at=901,
            ),
            _fact(
                memory_note_id="schedule-conditioning",
                fact_type="schedule",
                fact_key="schedule:conditioning-day",
                summary="One conditioning day is part of the weekly structure.",
                importance="medium",
                last_confirmed_at=1200,
            ),
            _fact(
                memory_note_id="schedule-shooting",
                fact_type="schedule",
                fact_key="schedule:saturday-shooting-group",
                summary="Saturday shooting group is a recurring session.",
                importance="medium",
                last_confirmed_at=1201,
            ),
            _fact(
                memory_note_id="detail-noise",
                fact_type="other",
                fact_key="other:first-step",
                summary="Keeps first-step quickness sharp.",
                importance="medium",
                last_confirmed_at=1202,
            ),
        ]

        result = apply_candidate_refresh(_output([]), existing, now_epoch=1710700000)
        surviving_ids = {note["memory_note_id"] for note in result["memory_notes"]}

        self.assertIn(
            "goal-season",
            surviving_ids,
            msg=(
                "Bug 19 regression (AM-012): primary season goal should survive ahead of later-added medium "
                f"schedule/detail items. surviving_ids={sorted(surviving_ids)}"
            ),
        )
        self.assertNotIn(
            "detail-noise",
            surviving_ids,
            msg=(
                "Bug 19 regression (AM-012): low-value supporting detail should be evicted before the "
                f"primary season goal. surviving_ids={sorted(surviving_ids)}"
            ),
        )


class TestGroup1Bug19UpstreamRepros(unittest.TestCase):
    def test_bug19_repro_am005_primary_goal_misclassified_as_schedule_is_eventually_evicted(self):
        """Reproduces AM-005 loss at the AM2 boundary instead of reducer-only setup."""
        existing = [
            _fact(
                memory_note_id="h1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                importance="high",
                last_confirmed_at=1101,
            ),
            _fact(
                memory_note_id="h2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                importance="high",
                last_confirmed_at=1102,
            ),
            _fact(
                memory_note_id="h3",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                importance="high",
                last_confirmed_at=1103,
            ),
            _fact(
                memory_note_id="h4",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                importance="high",
                last_confirmed_at=1104,
            ),
            _fact(
                memory_note_id="h5",
                fact_type="constraint",
                fact_key="constraint:family",
                summary="Family travel affects some weekends.",
                importance="high",
                last_confirmed_at=1105,
            ),
        ]

        final_notes = _apply_refresh_sequence(
            existing,
            [
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "1500 free",
                    "summary": "Primary competition goal is the summer 1500 free.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "before work",
                    "summary": "Swims happen before work.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ],
            [
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "saturday stroke clinic",
                    "summary": "Saturday stroke clinic is now a recurring technical session.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
                {
                    "action": "upsert",
                    "fact_type": "other",
                    "fact_key": "lane space",
                    "summary": "Lane space has been tight at the pool.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ],
        )

        self.assertTrue(
            any("1500 free" in note["summary"].lower() for note in final_notes),
            msg=(
                "Bug 19 repro (AM-005): when AM2 stores the primary event goal as a medium schedule fact, "
                "later medium schedule facts evict it under budget pressure. "
                f"final_fact_keys={[note['fact_key'] for note in final_notes]}"
            ),
        )

    def test_bug19_repro_am012_primary_goal_misclassified_as_schedule_is_eventually_evicted(self):
        """Reproduces AM-012 loss at the AM2 boundary instead of reducer-only setup."""
        existing = [
            _fact(
                memory_note_id="h1",
                fact_type="goal",
                fact_key="goal:marathon",
                summary="Run the fall marathon.",
                importance="high",
                last_confirmed_at=1101,
            ),
            _fact(
                memory_note_id="h2",
                fact_type="goal",
                fact_key="goal:consistency",
                summary="Stay consistent with four sessions per week.",
                importance="high",
                last_confirmed_at=1102,
            ),
            _fact(
                memory_note_id="h3",
                fact_type="constraint",
                fact_key="constraint:achilles",
                summary="Monitor Achilles response before progression.",
                importance="high",
                last_confirmed_at=1103,
            ),
            _fact(
                memory_note_id="h4",
                fact_type="constraint",
                fact_key="constraint:tuesday-mornings",
                summary="Busy work mornings on Tuesdays.",
                importance="high",
                last_confirmed_at=1104,
            ),
            _fact(
                memory_note_id="h5",
                fact_type="constraint",
                fact_key="constraint:family",
                summary="Family travel affects some weekends.",
                importance="high",
                last_confirmed_at=1105,
            ),
        ]

        final_notes = _apply_refresh_sequence(
            existing,
            [
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "summer rec league",
                    "summary": "Primary competition goal is the summer rec league.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "after 8pm",
                    "summary": "Most training happens after 8pm because of work.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ],
            [
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "conditioning day",
                    "summary": "One conditioning day is part of the weekly structure.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
                {
                    "action": "upsert",
                    "fact_type": "schedule",
                    "fact_key": "saturday shooting group",
                    "summary": "Saturday shooting group is a recurring session.",
                    "importance": "medium",
                    "evidence_source": "athlete_email",
                    "evidence_strength": "explicit",
                },
            ],
        )

        self.assertTrue(
            any("summer rec league" in note["summary"].lower() for note in final_notes),
            msg=(
                "Bug 19 repro (AM-012): when AM2 stores the season goal as a medium schedule fact, "
                "later medium schedule facts evict it under budget pressure. "
                f"final_fact_keys={[note['fact_key'] for note in final_notes]}"
            ),
        )


if __name__ == "__main__":
    unittest.main()
