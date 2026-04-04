import unittest
from decimal import Decimal
from unittest import mock

import athlete_simulation
import skills.runtime as skill_runtime


def _valid_reaction_payload() -> dict:
    return {
        "reaction_summary": "The coach sounded attentive and practical.",
        "felt_understood_score": 4,
        "communication_style_fit": 4,
        "trust_delta": "up",
        "what_helped": ["They matched the current stress level."],
        "what_bothered": ["They did not mention the Friday constraint."],
        "continue_conversation": True,
        "stop_reason": "",
        "next_subject": "A bit more context",
        "next_body": "Fridays are still my lightest day because of work.",
    }


def _valid_judge_payload() -> dict:
    return {
        "headline": "Mostly strong reply with one continuity miss.",
        "scores": {
            "understanding": 4,
            "memory_continuity": 3,
            "personalization": 4,
            "coaching_quality": 4,
            "tone_trust": 4,
            "communication_style_fit": 4,
            "safety": 5,
        },
        "what_landed": ["The coach simplified the week well."],
        "what_missed": ["The reply missed the athlete's protected Friday."],
        "improved_reply_example": "Protect Friday as the light day and keep the harder session earlier in the week.",
        "hallucinations_or_unwarranted_assumptions": ["None."],
        "athlete_likely_experience": "Likely feels mostly understood but not fully seen.",
        "issue_tags": ["missed_fact"],
        "strength_tags": ["specific_guidance", "good_attunement"],
    }


class TestAthleteSimulationValidation(unittest.TestCase):
    def test_validate_athlete_reaction_requires_next_message_when_continuing(self):
        payload = _valid_reaction_payload()
        payload["next_body"] = ""
        with self.assertRaisesRegex(ValueError, "next_body"):
            athlete_simulation.validate_athlete_reaction_output(payload)

    def test_validate_judge_output_rejects_unknown_tags(self):
        payload = _valid_judge_payload()
        payload["issue_tags"] = ["made_up_tag"]
        with self.assertRaisesRegex(ValueError, "unsupported tag"):
            athlete_simulation.validate_judge_output(payload)

    def test_validate_judge_output_allows_missing_improved_reply_example(self):
        payload = _valid_judge_payload()
        del payload["improved_reply_example"]
        validated = athlete_simulation.validate_judge_output(payload)
        self.assertIsNone(validated["improved_reply_example"])

    def test_validate_judge_output_rejects_invalid_improved_reply_example(self):
        payload = _valid_judge_payload()
        payload["improved_reply_example"] = 123
        with self.assertRaisesRegex(ValueError, "improved_reply_example"):
            athlete_simulation.validate_judge_output(payload)

    def test_validate_judge_output_preserves_improved_reply_example(self):
        validated = athlete_simulation.validate_judge_output(_valid_judge_payload())
        self.assertEqual(
            validated["improved_reply_example"],
            "Protect Friday as the light day and keep the harder session earlier in the week.",
        )

    def test_validate_judge_output_caps_vague_trivial_ack_turn(self):
        payload = _valid_judge_payload()
        payload["headline"] = "Brief acknowledgment with little substance."
        payload["what_landed"] = []
        payload["what_missed"] = ["Reply just acknowledges the message and stays generic."]
        payload["issue_tags"] = ["too_vague"]
        payload["strength_tags"] = []
        payload["scores"] = {
            "understanding": 4,
            "memory_continuity": 4,
            "personalization": 4,
            "coaching_quality": 5,
            "tone_trust": 4,
            "communication_style_fit": 4,
            "safety": 5,
        }

        validated = athlete_simulation.validate_judge_output(payload)

        self.assertLessEqual(validated["scores"]["coaching_quality"], 2)
        self.assertLessEqual(validated["scores"]["understanding"], 2)
        self.assertLessEqual(validated["scores"]["personalization"], 2)

    def test_validate_judge_output_caps_hallucinated_context_scores(self):
        payload = _valid_judge_payload()
        payload["issue_tags"] = ["hallucinated_context"]
        payload["scores"] = {
            "understanding": 5,
            "memory_continuity": 5,
            "personalization": 5,
            "coaching_quality": 5,
            "tone_trust": 4,
            "communication_style_fit": 4,
            "safety": 5,
        }

        validated = athlete_simulation.validate_judge_output(payload)

        self.assertLessEqual(validated["scores"]["understanding"], 2)
        self.assertLessEqual(validated["scores"]["memory_continuity"], 2)
        self.assertLessEqual(validated["scores"]["personalization"], 2)
        self.assertLessEqual(validated["scores"]["coaching_quality"], 2)

    def test_validate_reaction_rejects_repeated_stale_promise_loop(self):
        payload = _valid_reaction_payload()
        payload["next_body"] = "I'll send the weekly check-in tomorrow."
        with self.assertRaisesRegex(ValueError, "stale promise"):
            athlete_simulation.validate_athlete_reaction_output_with_context(
                payload,
                pending_commitments=[
                    {
                        "what": "send the weekly check in tomorrow",
                        "promised_turn": 1,
                        "turns_outstanding": 2,
                    }
                ],
            )

    def test_validate_reaction_allows_fulfilling_stale_commitment(self):
        payload = _valid_reaction_payload()
        payload["next_body"] = "Here is the weekly check-in with sleep and splits."
        validated = athlete_simulation.validate_athlete_reaction_output_with_context(
            payload,
            pending_commitments=[
                {
                    "what": "send the weekly check in tomorrow",
                    "promised_turn": 1,
                    "turns_outstanding": 2,
                }
            ],
        )
        self.assertIn("Here is the weekly check-in", validated["next_body"])


class TestAthleteSimulationRunnerCalls(unittest.TestCase):
    def test_athlete_reaction_prompt_includes_loop_and_follow_through_guardrails(self):
        prompt = athlete_simulation.ATHLETE_REACTION_SYSTEM_PROMPT
        self.assertIn("Do not get stuck in loops", prompt)
        self.assertIn("substantially the same as your previous message", prompt)
        self.assertIn("follow through within the next 1-2 turns", prompt)
        self.assertIn("If the payload includes current_phase", prompt)
        self.assertIn("If the payload includes pending_commitments", prompt)

    def test_schemas_bound_scores_to_one_through_five(self):
        athlete_score_schema = athlete_simulation.ATHLETE_REACTION_SCHEMA["properties"]["felt_understood_score"]
        judge_score_schema = athlete_simulation.JUDGE_SCHEMA["properties"]["scores"]["properties"]["understanding"]
        self.assertEqual(athlete_score_schema["minimum"], 1)
        self.assertEqual(athlete_score_schema["maximum"], 5)
        self.assertEqual(judge_score_schema["minimum"], 1)
        self.assertEqual(judge_score_schema["maximum"], 5)

    def test_schemas_constrain_tag_vocab_and_trust_delta(self):
        trust_delta_schema = athlete_simulation.ATHLETE_REACTION_SCHEMA["properties"]["trust_delta"]
        issue_tags_schema = athlete_simulation.JUDGE_SCHEMA["properties"]["issue_tags"]
        strength_tags_schema = athlete_simulation.JUDGE_SCHEMA["properties"]["strength_tags"]
        self.assertEqual(sorted(trust_delta_schema["enum"]), sorted(athlete_simulation.TRUST_DELTAS))
        self.assertEqual(sorted(issue_tags_schema["items"]["enum"]), sorted(athlete_simulation.ISSUE_TAGS))
        self.assertEqual(sorted(strength_tags_schema["items"]["enum"]), sorted(athlete_simulation.STRENGTH_TAGS))

    def test_judge_schema_marks_improved_reply_example_required_but_nullable(self):
        required = athlete_simulation.JUDGE_SCHEMA["required"]
        improved_reply_example_schema = athlete_simulation.JUDGE_SCHEMA["properties"]["improved_reply_example"]
        self.assertIn("improved_reply_example", required)
        self.assertEqual(
            improved_reply_example_schema["anyOf"],
            [
                {"type": "string", "minLength": 1},
                {"type": "null"},
            ],
        )

    def test_render_payload_serializes_decimal_values(self):
        rendered = athlete_simulation._render_payload(  # type: ignore[attr-defined]
            {
                "progress": {
                    "last_7d_activity_count": Decimal("2"),
                    "last_7d_distance_km": Decimal("18.5"),
                }
            }
        )
        self.assertIn('"last_7d_activity_count":2', rendered)
        self.assertIn('"last_7d_distance_km":18.5', rendered)

    def test_generate_opening_message_wraps_runtime_errors(self):
        with mock.patch.object(
            skill_runtime,
            "execute_json_schema",
            side_effect=skill_runtime.SkillExecutionError("bad", code="invalid_json_response"),
        ):
            with self.assertRaisesRegex(athlete_simulation.AthleteSimulationError, "athlete opening invalid"):
                athlete_simulation.AthleteSimulator.generate_opening_message(
                    scenario_name="sample",
                    athlete_brief="brief",
                    evaluation_focus=[],
                    min_turns=10,
                    max_turns=12,
                )

    def test_react_to_coach_reply_validates_payload(self):
        invalid_payload = _valid_reaction_payload()
        invalid_payload["felt_understood_score"] = 8
        with mock.patch.object(skill_runtime, "execute_json_schema", return_value=(invalid_payload, "{}")):
            with self.assertRaisesRegex(athlete_simulation.AthleteSimulationError, "athlete reaction invalid"):
                athlete_simulation.AthleteSimulator.react_to_coach_reply(
                    scenario_name="sample",
                    athlete_brief="brief",
                    transcript=[],
                    latest_athlete_message={"subject": "s", "body": "b"},
                    latest_coach_reply={"subject": "Re: s", "text": "reply"},
                    min_turns=10,
                    max_turns=12,
                    turn_number=1,
                    evaluation_focus=[],
                )

    def test_react_to_coach_reply_rejects_stale_promise_loop(self):
        invalid_payload = _valid_reaction_payload()
        invalid_payload["next_body"] = "I'll send the weekly check-in tomorrow."
        with mock.patch.object(skill_runtime, "execute_json_schema", return_value=(invalid_payload, "{}")):
            with self.assertRaisesRegex(athlete_simulation.AthleteSimulationError, "stale promise"):
                athlete_simulation.AthleteSimulator.react_to_coach_reply(
                    scenario_name="sample",
                    athlete_brief="brief",
                    transcript=[],
                    latest_athlete_message={"subject": "s", "body": "b"},
                    latest_coach_reply={"subject": "Re: s", "text": "reply"},
                    min_turns=10,
                    max_turns=12,
                    turn_number=3,
                    evaluation_focus=[],
                    pending_commitments=[
                        {
                            "what": "send the weekly check in tomorrow",
                            "promised_turn": 1,
                            "turns_outstanding": 2,
                        }
                    ],
                )

    def test_evaluate_reply_validates_payload(self):
        invalid_payload = _valid_judge_payload()
        invalid_payload["strength_tags"] = ["invented"]
        with mock.patch.object(skill_runtime, "execute_json_schema", return_value=(invalid_payload, "{}")):
            with self.assertRaisesRegex(athlete_simulation.CoachReplyJudgeError, "judge output invalid"):
                athlete_simulation.CoachReplyJudge.evaluate_reply(
                    scenario_name="sample",
                    judge_brief="judge",
                    transcript=[],
                    latest_athlete_message={"subject": "s", "body": "b"},
                    latest_coach_reply={"subject": "Re: s", "text": "reply"},
                    state_snapshot={},
                    evaluation_focus=[],
                )


if __name__ == "__main__":
    unittest.main()
