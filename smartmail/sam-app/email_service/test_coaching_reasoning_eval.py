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


# ---------------------------------------------------------------------------
# Phase 4: Directive boundary eval fixtures
# ---------------------------------------------------------------------------

def _forbidden_topic_brief():
    """Athlete explicitly says 'stop mentioning the Achilles'."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Achilles is fine — please stop bringing it up every message. "
            "Do not revisit the Achilles unless I raise it. "
            "Just tell me what's on the schedule this week."
        ),
    }
    return brief


def _reply_suppression_brief():
    """Athlete says 'only reply if there's a concern' and no concern exists."""
    brief = _base_brief()
    brief["decision_context"]["risk_flag"] = "green"
    brief["decision_context"]["risk_recent_history"] = ["green", "green", "green", "green"]
    brief["delivery_context"] = {
        "inbound_body": (
            "Ran easy 30 min, felt fine. Achilles quiet. "
            "No issues. Please only reply if there's a concern."
        ),
    }
    return brief


def _scope_this_week_only_brief():
    """Athlete says 'just tell me this week' — no future planning."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Just tell me this week — what are my sessions? "
            "I don't need the big picture right now."
        ),
    }
    return brief


def _format_constraint_brief():
    """Athlete asks for 3 lines max."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Send the three lines I asked for: "
            "1) Two must-not-miss sessions. "
            "2) Confirm caps. "
            "3) Calf flare rule. 3 lines max."
        ),
    }
    return brief


def _stop_week_labels_brief():
    """Athlete explicitly asks to stop using week labels."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Stop labeling weeks — no 'Week 5' or 'initial_assessment'. "
            "Just reference the locked 8-week build to Sep 24. "
            "Confirm Sat ride and Sun run are locked."
        ),
    }
    return brief


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestForbiddenTopicDirective(unittest.TestCase):
    """Athlete says 'stop mentioning the Achilles'. Directive must comply."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_forbidden_topic_brief())
        cls.directive = cls.result["directive"]

    def test_avoid_contains_achilles(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        self.assertTrue(
            "achilles" in avoid_text,
            f"Avoid must forbid Achilles: {self.directive['avoid']}",
        )

    def test_main_message_does_not_mention_achilles(self):
        self.assertNotIn(
            "achilles",
            self.directive["main_message"].lower(),
            "main_message must not mention Achilles",
        )

    def test_content_plan_does_not_mention_achilles(self):
        content = " ".join(self.directive["content_plan"]).lower()
        self.assertNotIn(
            "achilles", content,
            "content_plan must not mention Achilles",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestReplySuppression(unittest.TestCase):
    """Athlete says 'only reply if concern' and there is no concern."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_reply_suppression_brief())
        cls.directive = cls.result["directive"]

    def test_reply_action_is_suppress(self):
        self.assertEqual(
            self.directive.get("reply_action"), "suppress",
            f"reply_action should be 'suppress', got: {self.directive.get('reply_action')}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestScopeThisWeekOnly(unittest.TestCase):
    """Athlete says 'just this week'. Directive must not plan ahead."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_scope_this_week_only_brief())
        cls.directive = cls.result["directive"]

    def test_avoid_mentions_future(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        future_signals = ["next week", "future", "long-term", "coming weeks", "beyond this week"]
        self.assertTrue(
            any(s in avoid_text for s in future_signals),
            f"Avoid should block future scope: {self.directive['avoid']}",
        )

    def test_content_plan_is_narrow(self):
        self.assertLessEqual(
            len(self.directive["content_plan"]), 3,
            f"content_plan should be narrow: {self.directive['content_plan']}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestFormatConstraint(unittest.TestCase):
    """Athlete asks for 3 lines max."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_format_constraint_brief())
        cls.directive = cls.result["directive"]

    def test_avoid_mentions_length_constraint(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        self.assertTrue(
            any(s in avoid_text for s in ["3 lines", "three lines", "exceed"]),
            f"Avoid should enforce format constraint: {self.directive['avoid']}",
        )

    def test_content_plan_is_tight(self):
        self.assertLessEqual(
            len(self.directive["content_plan"]), 3,
            f"content_plan should have at most 3 items: {self.directive['content_plan']}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestStopWeekLabels(unittest.TestCase):
    """Athlete says 'stop labeling weeks'."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_stop_week_labels_brief())
        cls.directive = cls.result["directive"]

    def test_avoid_contains_week_label_rule(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        self.assertTrue(
            any(s in avoid_text for s in ["week label", "week number", "week "]),
            f"Avoid should forbid week labels: {self.directive['avoid']}",
        )

    def test_main_message_has_no_week_number(self):
        import re
        self.assertIsNone(
            re.search(r"Week \d+", self.directive["main_message"]),
            f"main_message should not contain 'Week N': {self.directive['main_message']}",
        )


# ---------------------------------------------------------------------------
# Phase 7: Expanded regression eval fixtures
# ---------------------------------------------------------------------------

def _stale_context_schedule_change_brief():
    """Athlete says 5 days now, memory says 4. Directive must use the update."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Update: I can now do 5 days a week instead of 4. "
            "My schedule opened up — add a Friday easy run. "
            "Everything else stays the same."
        ),
    }
    brief["memory_context"]["structure_facts"] = [
        "4 days/week runner",
        "Available Mon/Wed/Fri/Sun",
    ]
    brief["memory_context"]["contradicted_facts"] = [
        'Prior fact "4 days/week runner" may be superseded — athlete now says 5 days'
    ]
    return brief


def _confirmed_detail_reopened_brief():
    """Athlete confirmed Tuesday, coach should not re-ask."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Yes, Tuesday works. I confirmed this last message. "
            "Please just send the plan."
        ),
    }
    return brief


def _answer_only_brief():
    """Athlete asks a direct question, expects only an answer."""
    brief = _base_brief()
    brief["reply_mode"] = "lightweight_non_planning"
    brief["delivery_context"] = {
        "inbound_body": (
            "Quick question: is 75 minutes too long for my weekend long run "
            "at this point? That's all I need to know."
        ),
    }
    return brief


def _start_from_week_2_brief():
    """Athlete says start from Week 2, not Week 1."""
    brief = _base_brief()
    brief["delivery_context"] = {
        "inbound_body": (
            "Start from Week 2, not Week 1. "
            "I already did the intro week on my own."
        ),
    }
    return brief


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestStaleContextScheduleChange(unittest.TestCase):
    """Athlete updates from 4 to 5 days. Directive must reflect the new schedule."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_stale_context_schedule_change_brief())
        cls.directive = cls.result["directive"]

    def test_main_message_references_5_days(self):
        main = self.directive["main_message"].lower()
        self.assertTrue(
            any(s in main for s in ["5 days", "five days", "friday"]),
            f"main_message should reference 5 days or Friday: {self.directive['main_message']}",
        )

    def test_avoid_blocks_stale_4_days(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        # The directive should either avoid "4 days" or at least not assert it
        main = self.directive["main_message"].lower()
        content = " ".join(self.directive["content_plan"]).lower()
        self.assertNotIn(
            "4 days a week",
            main + " " + content,
            "Directive should not assert stale '4 days a week'",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestConfirmedDetailNotReopened(unittest.TestCase):
    """Athlete confirmed Tuesday. Directive should close that loop."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_confirmed_detail_reopened_brief())
        cls.directive = cls.result["directive"]

    def test_avoid_blocks_scheduling_re_ask(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        self.assertTrue(
            any(s in avoid_text for s in ["tuesday", "day", "schedule", "confirmed"]),
            f"Avoid should block re-asking about Tuesday: {self.directive['avoid']}",
        )

    def test_content_plan_does_not_ask_about_day(self):
        content = " ".join(self.directive["content_plan"]).lower()
        re_ask_signals = ["which day", "what day", "confirm tuesday", "prefer"]
        found = [s for s in re_ask_signals if s in content]
        self.assertEqual(
            found, [],
            f"content_plan should not re-ask about day preference: {found}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestAnswerOnlyDirective(unittest.TestCase):
    """Athlete asks a direct question. Directive should be narrow."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_answer_only_brief())
        cls.directive = cls.result["directive"]

    def test_content_plan_is_narrow(self):
        self.assertLessEqual(
            len(self.directive["content_plan"]), 2,
            f"content_plan should be narrow for a direct question: {self.directive['content_plan']}",
        )

    def test_main_message_addresses_the_question(self):
        main = self.directive["main_message"].lower()
        self.assertTrue(
            any(s in main for s in ["75", "long run", "appropriate", "fine", "ok", "good"]),
            f"main_message should address the 75-min question: {self.directive['main_message']}",
        )

    def test_avoid_blocks_plan_rewrite(self):
        avoid_text = " ".join(self.directive["avoid"]).lower()
        block_signals = ["rewrite", "full plan", "restructure", "beyond", "extra"]
        self.assertTrue(
            any(s in avoid_text for s in block_signals),
            f"Avoid should block plan rewrite: {self.directive['avoid']}",
        )


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestStartFromWeek2(unittest.TestCase):
    """Athlete says 'start from Week 2'. Directive must use Week 2 exactly."""

    @classmethod
    def setUpClass(cls):
        cls.result = run_coaching_reasoning_workflow(_start_from_week_2_brief())
        cls.directive = cls.result["directive"]

    def test_main_message_says_week_2(self):
        main = self.directive["main_message"].lower()
        self.assertTrue(
            "week 2" in main,
            f"main_message should say 'week 2': {self.directive['main_message']}",
        )

    def test_main_message_does_not_say_week_1(self):
        main = self.directive["main_message"].lower()
        self.assertNotIn(
            "week 1", main,
            f"main_message should not say 'week 1': {self.directive['main_message']}",
        )


if __name__ == "__main__":
    unittest.main()
