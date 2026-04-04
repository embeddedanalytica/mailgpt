import unittest

from skills.coaching_reasoning.prompt import build_system_prompt


def _fragile_return_brief():
    return {
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
            "risk_recent_history": ["yellow", "yellow", "yellow", "green"],
            "weeks_in_coaching": 19,
        },
        "validated_plan": {
            "weekly_skeleton": {
                "mon": "easy aerobic 50-60min",
                "wed": "easy aerobic 50-60min",
                "fri": "tempo 40min",
                "sun": "long run 75min",
            },
        },
        "memory_context": {
            "continuity_summary": {
                "summary": "Athlete has been rebuilding consistently.",
                "last_recommendation": "Keep everything fully aerobic for now while the Achilles stays quiet.",
                "open_loops": [],
            },
        },
        "delivery_context": {
            "inbound_body": (
                "Question for you: since things are stable again, should I add strides after "
                "one easy run, or keep everything fully aerobic for now?"
            ),
        },
    }


class TestCoachingReasoningPromptRegressions(unittest.TestCase):
    def test_prompt_instructs_fully_aerobic_answers_not_to_smuggle_in_quality(self):
        prompt = build_system_prompt(_fragile_return_brief())
        self.assertIn("default to fully aerobic guidance", prompt)
        self.assertIn("do not also permit strides, tempo, hills, fast finishes, pickups", prompt)
        self.assertIn("Put those in avoid instead", prompt)

    def test_prompt_requires_capability_consistency_across_turns(self):
        prompt = build_system_prompt(_fragile_return_brief())
        self.assertIn("Capability limits must stay consistent across turns", prompt)
        self.assertIn("cannot attach files", prompt)
        self.assertIn("do not later imply that it already did so", prompt)

    def test_prompt_blocks_recap_when_athlete_only_wants_one_change(self):
        prompt = build_system_prompt(_fragile_return_brief())
        self.assertIn("do not restate standing constraints or unchanged setup", prompt)
        self.assertIn("Surface only the new coaching decision", prompt)

    def test_prompt_requires_one_clear_recommendation_when_asked_to_choose(self):
        prompt = build_system_prompt(_fragile_return_brief())
        self.assertIn("make one clear recommendation first", prompt)
        self.assertIn("Do not hedge with equal-weight options", prompt)


if __name__ == "__main__":
    unittest.main()
