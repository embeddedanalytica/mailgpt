import unittest
from unittest.mock import patch

from skills.coaching_reasoning.errors import CoachingReasoningError
from skills.coaching_reasoning.validator import validate_coaching_directive


def _valid_directive(**overrides):
    base = {
        "reply_action": "send",
        "opening": "Good question.",
        "main_message": "Yes, 75 minutes is still appropriate this week.",
        "content_plan": [
            "Answer the question directly",
            "Give one short reason",
        ],
        "avoid": [
            "Do not rewrite the full week",
        ],
        "tone": "Direct and concise",
        "recommend_material": None,
        "rationale": "This is a narrow-answer turn.",
    }
    base.update(overrides)
    return base


def _answer_first_brief():
    return {
        "reply_mode": "lightweight_non_planning",
        "athlete_context": {
            "goal_summary": "Half marathon in 10 weeks",
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
                "sun": "long run 75min",
            },
        },
        "memory_context": {},
        "delivery_context": {
            "inbound_body": (
                "Quick question: is 75 minutes too long for my weekend long run "
                "at this point? That's all I need to know."
            ),
        },
    }


class TestCoachingReasoningShapeValidation(unittest.TestCase):
    def test_answer_first_turn_rejects_broad_content_plan(self):
        with self.assertRaises(CoachingReasoningError) as ctx:
            validate_coaching_directive(
                _valid_directive(
                    content_plan=[
                        "Answer the question directly",
                        "Give one short reason",
                        "Restate unchanged constraints",
                    ]
                ),
                response_shape="answer_first_then_stop",
                turn_purpose="lightweight_answer",
            )
        self.assertIn("too broad", str(ctx.exception))


class TestCoachingReasoningRunnerStructuralRetry(unittest.TestCase):
    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_retries_once_for_answer_first_turn(self, mock_runtime):
        first_payload = _valid_directive(
            content_plan=[
                "Answer the question directly",
                "Give one short reason",
                "Restate unchanged constraints",
            ]
        )
        second_payload = _valid_directive()
        mock_runtime.execute_json_schema.side_effect = [
            (first_payload, "raw-one"),
            (second_payload, "raw-two"),
        ]
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        result = run_coaching_reasoning_workflow(_answer_first_brief(), model_name="gpt-4o")

        self.assertEqual(result["directive"]["content_plan"], second_payload["content_plan"])
        self.assertEqual(mock_runtime.execute_json_schema.call_count, 2)
        second_call = mock_runtime.execute_json_schema.call_args_list[1]
        user_content = second_call.kwargs.get("user_content") or second_call[1]["user_content"]
        self.assertIn("Revision request:", user_content)
        self.assertIn("directive too broad for answer-first turn", user_content)


if __name__ == "__main__":
    unittest.main()
