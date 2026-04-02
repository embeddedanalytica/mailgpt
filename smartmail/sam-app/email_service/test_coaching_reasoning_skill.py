import unittest
from unittest.mock import patch

from skills.coaching_reasoning.errors import CoachingReasoningError
from skills.coaching_reasoning.prompt import build_system_prompt
from skills.coaching_reasoning.schema import JSON_SCHEMA
from skills.coaching_reasoning.validator import validate_coaching_directive


def _assert_openai_strict_schema_required_covers_properties(node: object, path: str = "") -> None:
    """OpenAI Responses API json_schema strict mode: every properties key must appear in required."""
    if isinstance(node, dict):
        props = node.get("properties")
        if isinstance(props, dict):
            req = node.get("required")
            if not isinstance(req, list):
                raise AssertionError(f"{path or 'root'}: object with properties must have required: list")
            missing = set(props.keys()) - set(req)
            if missing:
                raise AssertionError(
                    f"{path or 'root'}: properties keys missing from required: {sorted(missing)}"
                )
        for key, val in node.items():
            _assert_openai_strict_schema_required_covers_properties(
                val, f"{path}.{key}" if path else key
            )
    elif isinstance(node, list):
        for i, item in enumerate(node):
            _assert_openai_strict_schema_required_covers_properties(item, f"{path}[{i}]")


def _valid_directive(**overrides):
    base = {
        "reply_action": "send",
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
            "constraints_summary": "",
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


def _neutral_running_brief(**overrides):
    """Stable green history and neutral copy — no situational doctrine triggers."""
    base = _minimal_brief(
        decision_context={
            "track": "main_build",
            "phase": "build",
            "risk_flag": "green",
            "today_action": "do planned",
            "clarification_needed": False,
            "risk_recent_history": ["green", "green", "green", "green"],
            "weeks_in_coaching": 8,
        },
        delivery_context={"inbound_body": "Solid week — legs feel good."},
    )
    base.update(overrides)
    return base


class TestValidateCoachingDirective(unittest.TestCase):

    def test_valid_directive_passes(self):
        result = validate_coaching_directive(_valid_directive())
        self.assertEqual(result["reply_action"], "send")
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

    def test_invalid_reply_action_raises(self):
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(_valid_directive(reply_action="maybe"))


class TestCoachingDirectiveJsonSchema(unittest.TestCase):
    def test_openai_strict_required_matches_properties_everywhere(self):
        _assert_openai_strict_schema_required_covers_properties(JSON_SCHEMA)


class TestBuildSystemPrompt(unittest.TestCase):

    def test_includes_base_prompt(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("expert coaching strategist", prompt)
        self.assertIn("coaching_directive", prompt)

    def test_includes_running_doctrine(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("Daniels", prompt)
        self.assertIn("easy run paradox", prompt.lower())

    def test_no_sport_includes_core_only_not_running_methodology(self):
        brief = _neutral_running_brief()
        del brief["athlete_context"]["primary_sport"]
        prompt = build_system_prompt(brief)
        self.assertIn("periodization", prompt.lower())
        self.assertNotIn("Daniels", prompt)

    def test_includes_methodology_header(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("Coaching methodology:", prompt)

    def test_neutral_brief_omits_situational_doctrine(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertNotIn("Return From Setback", prompt)
        self.assertNotIn("Common Running Prescription Errors", prompt)

    def test_setback_brief_includes_return_doctrine(self):
        brief = _neutral_running_brief(
            delivery_context={"inbound_body": "Pain flared again after Tuesday's workout."},
        )
        self.assertIn("Return From Setback", build_system_prompt(brief))


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


def _valid_continuity_recommendation(**overrides):
    base = {
        "recommended_goal_horizon_type": "general_fitness",
        "recommended_phase": "base",
        "recommended_block_focus": "controlled_load_progression",
        "recommended_transition_action": "keep",
        "recommended_transition_reason": "No change needed",
        "recommended_goal_event_date": None,
    }
    base.update(overrides)
    return base


class TestValidatorContinuityRecommendation(unittest.TestCase):

    def test_valid_directive_with_continuity_recommendation(self):
        d = _valid_directive(continuity_recommendation=_valid_continuity_recommendation())
        result = validate_coaching_directive(d)
        self.assertIn("continuity_recommendation", result)
        self.assertEqual(result["continuity_recommendation"]["recommended_transition_action"], "keep")

    def test_valid_directive_without_continuity_recommendation(self):
        result = validate_coaching_directive(_valid_directive())
        self.assertNotIn("continuity_recommendation", result)

    def test_invalid_continuity_recommendation_raises(self):
        d = _valid_directive(continuity_recommendation={"bad": "data"})
        with self.assertRaises(CoachingReasoningError) as ctx:
            validate_coaching_directive(d)
        self.assertIn("continuity_recommendation", str(ctx.exception))

    def test_continuity_recommendation_invalid_enum(self):
        d = _valid_directive(
            continuity_recommendation=_valid_continuity_recommendation(
                recommended_transition_action="yolo",
            )
        )
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(d)

    def test_continuity_recommendation_invalid_block_focus(self):
        d = _valid_directive(
            continuity_recommendation=_valid_continuity_recommendation(
                recommended_block_focus="go_hard",
            )
        )
        with self.assertRaises(CoachingReasoningError):
            validate_coaching_directive(d)


class TestBuildSystemPromptContinuity(unittest.TestCase):

    def test_continuity_context_included_in_prompt(self):
        ctx = {
            "goal_horizon_type": "event",
            "current_phase": "build",
            "current_block_focus": "event_specific_build",
            "weeks_in_current_block": 4,
            "weeks_until_event": 8,
            "goal_event_date": "2026-06-15",
            "last_transition_reason": "Ready for build phase",
        }
        prompt = build_system_prompt(_neutral_running_brief(), continuity_context=ctx)
        self.assertIn("## Continuity context", prompt)
        self.assertIn("event_specific_build", prompt)
        self.assertIn("Weeks in current block: 4", prompt)
        self.assertIn("Weeks until event: 8", prompt)
        self.assertIn("keep", prompt)

    def test_continuity_context_none_no_section(self):
        prompt = build_system_prompt(_neutral_running_brief(), continuity_context=None)
        self.assertNotIn("## Continuity context", prompt)

    def test_continuity_context_empty_no_section(self):
        prompt = build_system_prompt(_neutral_running_brief(), continuity_context={})
        self.assertNotIn("## Continuity context", prompt)

    def test_no_event_omits_weeks_until_event(self):
        ctx = {
            "goal_horizon_type": "general_fitness",
            "current_phase": "base",
            "current_block_focus": "maintain_fitness",
            "weeks_in_current_block": 3,
            "last_transition_reason": "bootstrap",
        }
        prompt = build_system_prompt(_neutral_running_brief(), continuity_context=ctx)
        self.assertIn("## Continuity context", prompt)
        self.assertNotIn("Weeks until event", prompt)


class TestRunnerContinuityRecommendation(unittest.TestCase):

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_returns_continuity_recommendation(self, mock_runtime):
        directive_with_rec = _valid_directive(
            continuity_recommendation=_valid_continuity_recommendation()
        )
        mock_runtime.execute_json_schema.return_value = (directive_with_rec, "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        result = run_coaching_reasoning_workflow(_minimal_brief(), model_name="gpt-4o")
        self.assertIn("continuity_recommendation", result)
        self.assertIsNotNone(result["continuity_recommendation"])
        self.assertEqual(result["continuity_recommendation"]["recommended_transition_action"], "keep")
        # Directive should NOT contain continuity_recommendation
        self.assertNotIn("continuity_recommendation", result["directive"])

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_returns_none_when_no_recommendation(self, mock_runtime):
        mock_runtime.execute_json_schema.return_value = (_valid_directive(), "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        result = run_coaching_reasoning_workflow(_minimal_brief(), model_name="gpt-4o")
        self.assertIn("continuity_recommendation", result)
        self.assertIsNone(result["continuity_recommendation"])

    @patch("skills.coaching_reasoning.runner.skill_runtime")
    def test_runner_passes_continuity_context_to_prompt(self, mock_runtime):
        mock_runtime.execute_json_schema.return_value = (_valid_directive(), "raw")
        mock_runtime.SkillExecutionError = Exception

        from skills.coaching_reasoning.runner import run_coaching_reasoning_workflow

        ctx = {
            "goal_horizon_type": "event",
            "current_phase": "build",
            "current_block_focus": "event_specific_build",
            "weeks_in_current_block": 4,
        }
        run_coaching_reasoning_workflow(
            _minimal_brief(), model_name="gpt-4o", continuity_context=ctx
        )

        call_kwargs = mock_runtime.execute_json_schema.call_args
        system_prompt = call_kwargs.kwargs.get("system_prompt") or call_kwargs[1].get("system_prompt")
        self.assertIn("## Continuity context", system_prompt)
        self.assertIn("event_specific_build", system_prompt)


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


# ---------------------------------------------------------------------------
# Phase 4: Directive boundary tests (prompt content assertions)
# ---------------------------------------------------------------------------

class TestPromptPackInstructionFidelity(unittest.TestCase):
    """Verify the prompt pack contains the instruction-fidelity rules."""

    def test_prompt_contains_instruction_fidelity_section(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("INSTRUCTION FIDELITY", prompt)

    def test_prompt_contains_avoid_list_categories(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("Forbidden content", prompt)
        self.assertIn("Forbidden reopenings", prompt)
        self.assertIn("Forbidden expansions", prompt)

    def test_prompt_contains_no_week_labels_when_absent_rule(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("no continuity context is provided", prompt.lower())
        self.assertIn("do not reference week numbers", prompt.lower())

    def test_prompt_contains_athlete_override_rule(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("athlete's correction", prompt.lower())


class TestPromptWithContradictedFacts(unittest.TestCase):
    """Verify contradicted facts are surfaced in the prompt."""

    def test_contradicted_facts_surfaced(self):
        brief = _neutral_running_brief(
            memory_context={
                "priority_facts": ["Constraint: recurring knee issue"],
                "contradicted_facts": [
                    'Prior fact "Constraint: recurring knee issue" may be superseded',
                ],
            },
        )
        prompt = build_system_prompt(brief)
        self.assertIn("Contradicted durable facts", prompt)
        self.assertIn("recurring knee issue", prompt)

    def test_no_contradicted_section_when_absent(self):
        brief = _neutral_running_brief()
        prompt = build_system_prompt(brief)
        self.assertNotIn("Contradicted durable facts", prompt)


class TestPromptPackOpenLoopResolution(unittest.TestCase):
    """Verify the prompt pack contains the open-loop decision checkpoint rule."""

    def test_prompt_contains_open_loop_decision_rule(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("open_loops", prompt)
        self.assertIn("decision checkpoint", prompt.lower())

    def test_prompt_instructs_to_make_the_decision(self):
        prompt = build_system_prompt(_neutral_running_brief())
        self.assertIn("Make the decision", prompt)
        self.assertIn("Do not defer", prompt)


if __name__ == "__main__":
    unittest.main()
