"""Evaluation tests for coaching reasoning directives on known-problematic turns.

These tests require ENABLE_LIVE_LLM_CALLS=true. They feed synthetic ResponseBriefs
(modeled on real e2e sim turns) through the coaching reasoning skill and assert the
directive addresses the coaching signal.

Run: ENABLE_LIVE_LLM_CALLS=true python3 -m unittest -v test_coaching_reasoning_eval
"""

import os
import unittest

from skills.coaching_reasoning.errors import CoachingReasoningError
from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

_LIVE = os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"


def _base_brief(**overrides):
    base = {
        "reply_mode": "normal_coaching",
        "athlete_context": {
            "goal_summary": "Half marathon on 2026-05-17",
            "experience_level": "intermediate",
            "structure_preference": "structured",
            "primary_sport": "running",
            "constraints_summary": "History of mild Achilles tightness",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do planned",
            "clarification_needed": False,
        },
        "validated_plan": {
            "weekly_skeleton": {
                "mon": "easy aerobic 50-60min",
                "wed": "easy aerobic 50-60min",
                "fri": "tempo 40min",
                "sun": "long run 75min",
            },
            "plan_summary": "4 sessions/week, building toward half marathon.",
        },
        "memory_context": {
            "priority_facts": [
                "Athlete has mild Achilles tightness history",
            ],
            "structure_facts": [
                "4 days/week runner",
            ],
            "context_facts": [
                "Prefers structured plans",
            ],
            "continuity_summary": {
                "summary": "Athlete has been rebuilding consistently.",
                "last_recommendation": "Keep sessions easy, monitor Achilles.",
                "open_loops": [],
            },
        },
        "delivery_context": {
            "inbound_body": "Check-in for this week.",
        },
    }
    base.update(overrides)
    return base


def _turn_18_post_recovery_brief():
    """Turn 18: First green week after 3 yellows. Athlete feels good and ran well."""
    brief = _base_brief()
    brief["decision_context"]["risk_flag"] = "green"
    brief["decision_context"]["risk_recent_history"] = [
        "yellow", "yellow", "yellow", "green",
    ]
    brief["decision_context"]["weeks_in_coaching"] = 18
    brief["delivery_context"]["inbound_body"] = (
        "Better week. I ran three times: 35m easy, 50m steady, and 80m today for about "
        "9 miles. Felt good, slept well, and the Achilles feels quiet again. Same four-day "
        "rhythm still seems like the sweet spot."
    )
    return brief


def _turn_27_race_completion_brief():
    """Turn 27: Athlete just finished their goal half marathon in 1:55."""
    brief = _base_brief()
    brief["decision_context"]["risk_flag"] = "green"
    brief["decision_context"]["risk_recent_history"] = [
        "green", "green", "green", "green",
    ]
    brief["decision_context"]["weeks_in_coaching"] = 27
    brief["delivery_context"]["inbound_body"] = (
        "Race update: I ran the half marathon today in 1:55. I jogged 15m after, I feel "
        "tired but happy, and nothing feels scary. This whole build really confirmed that "
        "four days per week is a good groove for me."
    )
    return brief


def _turn_25_reflection_brief():
    """Turn 25: Athlete asks a reflective question about their coaching journey."""
    brief = _base_brief()
    brief["decision_context"]["risk_flag"] = "green"
    brief["decision_context"]["risk_recent_history"] = [
        "green", "green", "green", "green",
    ]
    brief["decision_context"]["weeks_in_coaching"] = 25
    brief["reply_mode"] = "lightweight_non_planning"
    brief["delivery_context"]["inbound_body"] = (
        "I have a mild cold and the weather is awful this week. Energy is not great. "
        "I don't want to do anything dumb, but I also don't want to lose the thread "
        "completely. How conservative should I be?"
    )
    return brief


def _turn_20_mature_relationship_brief():
    """Turn 20+: Long-tenured athlete — should not get basic technique cues."""
    brief = _base_brief()
    brief["decision_context"]["risk_flag"] = "green"
    brief["decision_context"]["risk_recent_history"] = [
        "green", "green", "green", "green",
    ]
    brief["decision_context"]["weeks_in_coaching"] = 22
    brief["delivery_context"]["inbound_body"] = (
        "Good week — hit all four sessions, felt strong. Long run was 80 minutes and "
        "I negative-split the last 20. Ready for whatever is next."
    )
    return brief


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestTurn18PostRecoveryEscalation(unittest.TestCase):
    """After 3 yellow weeks, the first green week should NOT escalate intensity."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_turn_18_post_recovery_brief())
        cls.directive = cls.result["directive"]

    def test_opening_acknowledges_recovery(self):
        opening = self.directive["opening"].lower()
        recovery_signals = ["better", "good", "recover", "back", "progress", "quiet"]
        self.assertTrue(
            any(s in opening for s in recovery_signals),
            f"Opening should acknowledge recovery arc: {self.directive['opening']}",
        )

    def test_avoid_includes_premature_intensity(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        intensity_signals = ["tempo", "interval", "speed", "hard", "intensity", "escalat", "push"]
        self.assertTrue(
            any(s in avoid_text for s in intensity_signals),
            f"Avoid should warn against premature intensity: {self.directive['avoid']}",
        )

    def test_rationale_mentions_fragility(self):
        rationale = self.directive["rationale"].lower()
        fragility_signals = ["fragile", "first green", "cautious", "conservative", "yellow", "recovery"]
        self.assertTrue(
            any(s in rationale for s in fragility_signals),
            f"Rationale should reference recovery fragility: {self.directive['rationale']}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestTurn27RaceCompletion(unittest.TestCase):
    """Completing the goal race should lead with celebration, not planning."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_turn_27_race_completion_brief())
        cls.directive = cls.result["directive"]

    def test_opening_leads_with_celebration(self):
        opening = self.directive["opening"].lower()
        celebration_signals = [
            "congratulat", "amazing", "incredible", "proud", "celebrat",
            "well done", "fantastic", "1:55", "milestone", "earned",
        ]
        self.assertTrue(
            any(s in opening for s in celebration_signals),
            f"Opening should celebrate the race: {self.directive['opening']}",
        )

    def test_content_plan_starts_with_milestone(self):
        first_item = self.directive["content_plan"][0].lower()
        milestone_signals = [
            "celebrat", "race", "achievement", "milestone", "half marathon",
            "congratulat", "1:55", "finish", "accomplish",
        ]
        self.assertTrue(
            any(s in first_item for s in milestone_signals),
            f"First content item should be milestone recognition: {self.directive['content_plan'][0]}",
        )

    def test_no_immediate_next_plan(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        planning_signals = ["next week", "next plan", "immediately", "jump into", "next cycle"]
        has_planning_avoidance = any(s in avoid_text for s in planning_signals)
        # Also check that main_message doesn't jump to planning
        main = self.directive["main_message"].lower()
        celebration_in_main = any(
            s in main for s in ["celebrat", "race", "earned", "milestone", "journey", "1:55"]
        )
        self.assertTrue(
            has_planning_avoidance or celebration_in_main,
            "Directive should prioritize celebration over next-cycle planning",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestTurn20MatureRelationship(unittest.TestCase):
    """At 22 weeks, directive should NOT repeat basic technique cues."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_turn_20_mature_relationship_brief())
        cls.directive = cls.result["directive"]

    def test_no_basic_technique_cues_in_content_plan(self):
        content = " ".join(self.directive["content_plan"]).lower()
        basic_cues = ["cadence", "posture", "tall posture", "170-180", "arm swing"]
        found = [c for c in basic_cues if c in content]
        self.assertEqual(
            found, [],
            f"Content plan should not repeat basic technique cues at week 22: {found}",
        )

    def test_tone_is_direct(self):
        tone = self.directive["tone"].lower()
        direct_signals = ["direct", "concise", "brief", "collaborative", "partner", "confident"]
        self.assertTrue(
            any(s in tone for s in direct_signals),
            f"Tone should be direct/collaborative at week 22: {self.directive['tone']}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestTurn25ConservativeGuidance(unittest.TestCase):
    """Sick athlete asking how conservative to be — needs personalized synthesis."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_turn_25_reflection_brief())
        cls.directive = cls.result["directive"]

    def test_main_message_is_personalized(self):
        main = self.directive["main_message"].lower()
        personal_signals = [
            "cold", "energy", "conservative", "rest", "recover",
            "back off", "reduce", "skip", "easy", "thread",
        ]
        self.assertTrue(
            any(s in main for s in personal_signals),
            f"Main message should address the athlete's illness: {self.directive['main_message']}",
        )

    def test_rationale_references_context(self):
        rationale = self.directive["rationale"].lower()
        context_signals = ["cold", "sick", "illness", "energy", "conservative", "achilles"]
        self.assertTrue(
            any(s in rationale for s in context_signals),
            f"Rationale should reference athlete's current state: {self.directive['rationale']}",
        )


if __name__ == "__main__":
    unittest.main()
