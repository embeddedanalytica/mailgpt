"""Live regression for cross-turn capability consistency (bug 28).

Requires ENABLE_LIVE_LLM_CALLS=true.
"""

import os
import unittest

from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow
from skills.response_generation.runner import run_response_generation_workflow

_LIVE = os.getenv("ENABLE_LIVE_LLM_CALLS", "false").strip().lower() == "true"


def _base_brief() -> dict:
    return {
        "reply_mode": "normal_coaching",
        "athlete_context": {
            "goal_summary": "Half marathon on 2026-09-24",
            "experience_level": "intermediate",
            "structure_preference": "structured",
            "primary_sport": "running",
            "constraints_summary": "Weekday runs at 05:30, Saturday long run at 07:30.",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do planned",
            "clarification_needed": False,
            "weeks_in_coaching": 12,
        },
        "validated_plan": {
            "weekly_skeleton": [
                "easy_aerobic",
                "steady_aerobic",
                "long_run",
            ],
            "plan_summary": "3 runs this week, all remote guidance only.",
        },
        "memory_context": {
            "memory_available": True,
            "priority_facts": ["Half marathon on 2026-09-24"],
            "structure_facts": ["Weekday runs at 05:30, Saturday at 07:30"],
            "context_facts": ["Prefers concise logistics answers"],
            "continuity_summary": {
                "summary": "Athlete wants calendar logistics clarified without sharing credentials.",
                "last_recommendation": "Coach can only give written guidance by email.",
                "open_loops": [],
            },
        },
        "delivery_context": {
            "inbound_subject": "Calendar file question",
            "response_channel": "email",
        },
    }


def _writer_input(brief: dict, directive: dict) -> dict:
    return {
        "reply_mode": brief["reply_mode"],
        "coaching_directive": {
            key: value for key, value in directive.items() if key not in {"reply_action", "rationale"}
        },
        "plan_data": brief["validated_plan"],
        "delivery_context": brief["delivery_context"],
        "continuity_context": {
            "goal_horizon_type": "event",
            "current_phase": "build",
            "current_block_focus": "event_specific_build",
            "weeks_in_current_block": 4,
            "weeks_until_event": 12,
            "goal_event_date": "2026-09-24",
        },
    }


@unittest.skipUnless(_LIVE, "ENABLE_LIVE_LLM_CALLS not set")
class TestCapabilityConsistencyEval(unittest.TestCase):
    def test_cross_turn_does_not_invent_file_or_calendar_actions(self):
        turn1 = _base_brief()
        turn1["delivery_context"]["inbound_body"] = (
            "Please attach the ICS or CSV for this week, or tell me if you already released it "
            "to my calendar."
        )

        strategist_1 = run_coaching_reasoning_workflow(turn1)["directive"]
        writer_1 = run_response_generation_workflow(_writer_input(turn1, strategist_1))
        email_1 = writer_1["final_email_body"].lower()

        self.assertTrue(
            any(
                signal in email_1
                for signal in [
                    "can't attach",
                    "cannot attach",
                    "by email only",
                    "can't add events to your calendar",
                    "cannot add events to your calendar",
                    "can't release",
                    "cannot release",
                    "can't access your calendar",
                    "cannot access your calendar",
                ]
            ),
            f"turn 1 should state the capability limit plainly: {writer_1['final_email_body']}",
        )
        self.assertFalse(
            any(signal in email_1 for signal in ["i attached", "attached the", "released it", "imported it"]),
            f"turn 1 must not claim unsupported actions: {writer_1['final_email_body']}",
        )

        turn2 = _base_brief()
        turn2["memory_context"]["continuity_summary"] = {
            "summary": "Coach previously said it cannot attach files or release calendar items.",
            "last_recommendation": writer_1["final_email_body"],
            "open_loops": [],
        }
        turn2["delivery_context"]["inbound_body"] = (
            "Understood. Since you cannot attach files, did you import the plan into my account "
            "or release it somewhere after all?"
        )

        strategist_2 = run_coaching_reasoning_workflow(turn2)["directive"]
        writer_2 = run_response_generation_workflow(_writer_input(turn2, strategist_2))
        email_2 = writer_2["final_email_body"].lower()

        self.assertFalse(
            any(signal in email_2 for signal in ["i attached", "attached the", "released it", "imported it into your account"]),
            f"turn 2 must stay capability-consistent: {writer_2['final_email_body']}",
        )
        self.assertTrue(
            any(
                signal in email_2
                for signal in ["cannot", "can't", "by email", "written guidance", "do not have", "i can only"]
            ),
            f"turn 2 should preserve the remote-capability boundary: {writer_2['final_email_body']}",
        )


if __name__ == "__main__":
    unittest.main()
