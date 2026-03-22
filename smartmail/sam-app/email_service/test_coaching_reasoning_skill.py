import unittest
from unittest.mock import patch

from skills.coaching_reasoning.errors import CoachingReasoningError
from skills.coaching_reasoning.prompt import build_system_prompt
from skills.coaching_reasoning.validator import validate_coaching_directive


def _valid_directive(**overrides):
    base = {
        "opening": "Great to hear the shin is feeling better.",
        "main_message": "We're staying conservative this week — one more easy week before adding intensity.",
        "content_plan": [
            "Acknowledge recovery progress",
            "Present easy week structure",
            "Explain why we're holding back one more week",
        ],
        "avoid": [
            "Do not suggest tempo or interval sessions",
            "Do not reference old injury as a current limitation",
        ],
        "tone": "Calm, reassuring, direct",
        "recommend_material": None,
        "rationale": "Athlete just returned to green after 3 yellow weeks. First good week is fragile.",
    }
    base.update(overrides)
    return base


def _minimal_brief(**overrides):
    base = {
        "reply_mode": "normal_coaching",
        "athlete_context": {
            "goal_summary": "Half marathon in 10 weeks",
            "experience_level": "intermediate",
            "structure_preference": "flexibility",
            "primary_sport": "running",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do planned",
            "clarification_needed": False,
            "risk_recent_history": ["yellow", "yellow", "yellow", "green"],
            "weeks_in_coaching": 8,
        },
        "validated_plan": {"weekly_skeleton": {"mon": "easy 30min"}},
        "memory_context": {},
        "delivery_context": {"inbound_body": "Shin feels much better this week."},
    }
    base.update(overrides)
    return base


class TestValidateCoachingDirective(unittest.TestCase):

    def test_valid_directive_passes(self):
        result = validate_coaching_directive(_valid_directive())
        self.assertEqual(result["opening"], "Great to hear the shin is feeling better.")
        self.assertIsNone(result["recommend_material"])

    def test_valid_directive_with_recommendation(self):
        result = validate_coaching_directive(_valid_directive(
            recommend_material="80/20 Running by Matt Fitzgerald"
        ))
        self.assertEqual(result["recommend_material"], "80/20 Running by Matt Fitzgerald")

    def test_missing_required_field_raises(self):
        d = _valid_directive()
        del d["opening"]
        with self.assertRaises(CoachingReasoningError) as ctx:
            validate_coaching_directive(d)
        self.assertIn("opening", str(ctx.exception))

    def test_extra_field_raises(self):
        d = _valid_directive(extra_field="oops")
        with self.assertRaises(CoachingReasoningError) as ctx:
            validate_coaching_directive(d)
        self.assertIn("extra_field", str(ctx.exception))

    def test_empty_opening_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(opening=""))

    def test_whitespace_only_opening_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(opening="   "))

    def test_empty_content_plan_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(content_plan=[]))

    def test_content_plan_with_empty_item_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(content_plan=["good", ""]))

    def test_avoid_with_empty_item_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(avoid=["good", "  "]))

    def test_empty_avoid_list_passes(self):
        result = validate_coaching_directive(_valid_directive(avoid=[]))
        self.assertEqual(result["avoid"], [])

    def test_non_dict_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive("not a dict")

    def test_strips_whitespace(self):
        result = validate_coaching_directive(_valid_directive(
            opening="  padded  ",
            tone="  warm  ",
            content_plan=["  item one  "],
            avoid=["  no hedging  "],
        ))
        self.assertEqual(result["opening"], "padded")
        self.assertEqual(result["tone"], "warm")
        self.assertEqual(result["content_plan"], ["item one"])
        self.assertEqual(result["avoid"], ["no hedging"])

    def test_recommend_material_wrong_type_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(recommend_material=42))


class TestBuildSystemPrompt(unittest.TestCase):

    def test_includes_base_prompt(self):
        prompt = build_system_prompt("running")
        self.assertIn("expert coaching strategist", prompt)
        self.assertIn("coaching_directive", prompt)

    def test_includes_running_doctrine(self):
        prompt = build_system_prompt("running")
        self.assertIn("Daniels", prompt)
        self.assertIn("easy run paradox", prompt.lower())

    def test_no_sport_includes_universal_only(self):
        prompt = build_system_prompt(None)
        self.assertIn("periodization", prompt.lower())
        self.assertNotIn("Daniels", prompt)

    def test_includes_methodology_header(self):
        prompt = build_system_prompt("running")
        self.assertIn("Coaching methodology:", prompt)


class TestRunnerWithMockedLLM(unittest.TestCase):

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_returns_directive_and_metadata(self, mock_runtime):
        mock_runtime.execute_json_schema.return_value = (_valid_directive(), "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        result = run_coaching_reasoning_workflow(_minimal_brief(), model_name="gpt-4o")

        self.assertIn("directive", result)
        self.assertIn("doctrine_files_loaded", result)
        self.assertEqual(result["directive"]["opening"], "Great to hear the shin is feeling better.")
        self.assertIn("running/methodology.md", result["doctrine_files_loaded"])
        self.assertIn("universal/core.md", result["doctrine_files_loaded"])

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_uses_sport_from_brief(self, mock_runtime):
        mock_runtime.execute_json_schema.return_value = (_valid_directive(), "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        result = run_coaching_reasoning_workflow(_minimal_brief(), model_name="gpt-4o")

        # Should have loaded running files since brief has primary_sport="running"
        self.assertIn("running/methodology.md", result["doctrine_files_loaded"])

        # Verify system prompt passed to LLM includes running doctrine
        call_kwargs = mock_runtime.execute_json_schema.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs[1].get("system_prompt")
        self.assertIn("Daniels", system_prompt)

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_no_sport_loads_universal_only(self, mock_runtime):
        mock_runtime.execute_json_schema.return_value = (_valid_directive(), "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        brief = _minimal_brief()
        del brief["athlete_context"]["primary_sport"]
        result = run_coaching_reasoning_workflow(brief, model_name="gpt-4o")

        self.assertNotIn("running/methodology.md", result["doctrine_files_loaded"])
        self.assertIn("universal/core.md", result["doctrine_files_loaded"])

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_raises_on_invalid_llm_output(self, mock_runtime):
        mock_runtime.execute_json_schema.return_value = ({"bad": "output"}, "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        with self.assertRaises(CoachingReasoningError):
            run_coaching_reasoning_workflow(_minimal_brief(), model_name="gpt-4o")

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_wraps_skill_execution_error(self, mock_runtime):
        class MockSkillError(Exception):
            def __init__(self):
                super().__init__("boom")
                self.raw_response = "partial json"

        mock_runtime.SkillExecutionError = MockSkillError
        mock_runtime.execute_json_schema.side_effect = MockSkillError()
        mock_runtime.preview_text.return_value = "partial json"

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        with self.assertRaises(CoachingReasoningError):
            run_coaching_reasoning_workflow(_minimal_brief(), model_name="gpt-4o")


class TestExtractSport(unittest.TestCase):

    def test_extracts_from_athlete_context(self):
        from skills.coaching_reasoning.runner import _extract_sport

        self.assertEqual(_extract_sport(_minimal_brief()), "running")

    def test_returns_none_when_missing(self):
        from skills.coaching_reasoning.runner import _extract_sport

        brief = _minimal_brief()
        del brief["athlete_context"]["primary_sport"]
        self.assertIsNone(_extract_sport(brief))

    def test_returns_none_for_no_athlete_context(self):
        from skills.coaching_reasoning.runner import _extract_sport

        self.assertIsNone(_extract_sport({}))


if __name__ == "__main__":
    unittest.main()
