import unittest
from unittest import mock

import response_generation_assembly
from response_generation_assembly import (
    build_response_brief,
    build_response_generation_input,
    detect_contradicted_facts,
    extract_athlete_instructions,
)
from response_generation_contract import ResponseBrief


def _memory_note(
    *,
    memory_note_id: str = "f1",
    fact_type: str = "goal",
    fact_key: str = "goal:half-marathon",
    summary: str = "Half marathon in October",
    importance: str = "high",
    created_at: int = 1773273600,
    updated_at: int = 1773273600,
    last_confirmed_at: int = 1773273600,
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


def _continuity_summary() -> dict:
    return {
        "summary": "Athlete is rebuilding consistency.",
        "last_recommendation": "Keep one controlled quality session this week.",
        "open_loops": ["How did the quality session feel?"],
        "updated_at": 1773273600,
    }


def _empty_memory_context() -> dict:
    return {"memory_notes": [], "continuity_summary": None}


class TestBuildResponseBrief(unittest.TestCase):
    def test_clarification_questions_are_sourced_from_response_generation_copy_helper(self):
        with mock.patch.object(
            response_generation_assembly,
            "build_clarification_questions",
            return_value=["- helper owned question"],
        ):
            brief = build_response_brief(
                athlete_id="ath_helper",
                reply_kind="profile_incomplete",
                inbound_subject=None,
                selected_model_name=None,
                profile_after={},
                missing_profile_fields=["primary_goal"],
                plan_summary=None,
                rule_engine_decision=None,
                memory_context=None,
            )

        self.assertEqual(brief.decision_context["clarification_questions"], ["- helper owned question"])

    def test_profile_incomplete_maps_to_clarification_and_omits_missing_optional_context(self):
        brief = build_response_brief(
            athlete_id="ath_1",
            reply_kind="profile_incomplete",
            inbound_subject=None,
            selected_model_name=None,
            profile_after={},
            missing_profile_fields=["primary_goal"],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context=None,
        )

        self.assertEqual(brief.reply_mode, "clarification")
        self.assertEqual(brief.athlete_context, {})
        self.assertEqual(brief.validated_plan, {})
        self.assertEqual(brief.memory_context["memory_available"], False)
        self.assertEqual(brief.decision_context["clarification_needed"], True)
        self.assertEqual(
            brief.decision_context["clarification_questions"],
            ["- Your primary goal (e.g., first marathon, improve 10k time)"],
        )

    def test_generic_coaching_includes_goal_plan_delivery_and_memory(self):
        brief = build_response_brief(
            athlete_id="ath_2",
            reply_kind="coaching_reply",
            inbound_subject="Plan help",
            selected_model_name="gpt-5-nano",
            profile_after={
                "primary_goal": "Half marathon",
                "experience_level": "intermediate",
                "structure_preference": "flexibility",
            },
            missing_profile_fields=[],
            plan_summary="Current plan - Goal: Half marathon.",
            rule_engine_decision=None,
            memory_context={
                "memory_notes": [
                    _memory_note(
                        memory_note_id="f1",
                        fact_type="constraint",
                        fact_key="constraint:early-finish",
                        summary="Weekday sessions need to finish before 7am",
                    ),
                    _memory_note(
                        memory_note_id="f2",
                        fact_type="preference",
                        fact_key="preference:gear",
                        summary="Owns a power meter",
                        importance="medium",
                    ),
                ],
                "continuity_summary": _continuity_summary(),
            },
            connect_strava_link="https://geniml.com/action/tok_123",
        )

        self.assertEqual(brief.reply_mode, "normal_coaching")
        self.assertEqual(brief.athlete_context["goal_summary"], "Half marathon")
        self.assertEqual(brief.athlete_context["experience_level"], "intermediate")
        self.assertEqual(brief.delivery_context["inbound_subject"], "Plan help")
        self.assertEqual(brief.delivery_context["selected_model_name"], "gpt-5-nano")
        self.assertEqual(
            brief.delivery_context["connect_strava_link"],
            "https://geniml.com/action/tok_123",
        )
        self.assertEqual(brief.validated_plan["plan_summary"], "Current plan - Goal: Half marathon.")
        self.assertEqual(brief.memory_context["continuity_summary"]["summary"], "Athlete is rebuilding consistency.")
        self.assertEqual(brief.memory_context["memory_available"], True)
        self.assertEqual(
            brief.memory_context["continuity_focus"],
            "Athlete is rebuilding consistency.",
        )
        # Constraint is in priority_facts, preference in context_facts
        self.assertIn("Weekday sessions need to finish before 7am", brief.memory_context["priority_facts"])
        self.assertIn("Owns a power meter", brief.memory_context["context_facts"])

    def test_rule_engine_guided_reply_kind_no_longer_leaks_engine_fields(self):
        brief = build_response_brief(
            athlete_id="ath_3",
            reply_kind="rule_engine_guided",
            inbound_subject="Weekly check-in",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary="Current plan - Goal: 10k.",
            rule_engine_decision={
                "reply_strategy": "rule_engine_guided",
                "clarification_needed": False,
                "engine_output": {
                    "classification_label": "deterministic_re3_transition",
                    "track": "return_or_risk_managed",
                    "phase": "build",
                    "risk_flag": "yellow",
                    "weekly_skeleton": ["easy_aerobic", "strength"],
                    "today_action": "prioritize_big_2_anchors",
                    "plan_update_status": "updated",
                    "adjustments": ["prioritize_big_2_anchors"],
                    "next_email_payload": {
                        "subject_hint": "This week: stay safe and keep it steady",
                        "summary": "This is a risk-managed week.",
                        "sessions": ["Priority: long easy aerobic session"],
                        "plan_focus_line": "Use safety and consistency as the primary filter.",
                        "technique_cue": "Keep cadence light and posture tall.",
                        "recovery_target": "Prioritize recovery basics before adding any load.",
                        "if_then_rules": ["If symptoms rise, remove intensity immediately."],
                        "disclaimer_short": "",
                        "safety_note": "No hard sessions when risk is red-tier.",
                    },
                },
            },
            memory_context=_empty_memory_context(),
        )

        self.assertEqual(brief.reply_mode, "normal_coaching")
        self.assertEqual(brief.decision_context, {})
        self.assertEqual(brief.validated_plan, {"plan_summary": "Current plan - Goal: 10k."})

    def test_memory_salience_groups_facts_by_type(self):
        brief = build_response_brief(
            athlete_id="ath_4",
            reply_kind="coaching_reply",
            inbound_subject="Next week",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "Half marathon"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context={
                "memory_notes": [
                    _memory_note(
                        memory_note_id="f1",
                        fact_type="goal",
                        fact_key="goal:half-marathon",
                        summary="Half marathon in October",
                    ),
                    _memory_note(
                        memory_note_id="f2",
                        fact_type="constraint",
                        fact_key="constraint:early-finish",
                        summary="Weekday sessions need to finish before 7am",
                    ),
                    _memory_note(
                        memory_note_id="f3",
                        fact_type="preference",
                        fact_key="preference:calf-watch",
                        summary="Watch for calf tightness when adding speed",
                        importance="medium",
                    ),
                    _memory_note(
                        memory_note_id="f4",
                        fact_type="preference",
                        fact_key="preference:format",
                        summary="Prefers concise bullets",
                        importance="medium",
                    ),
                ],
                "continuity_summary": _continuity_summary(),
            },
        )

        # goal + constraint → priority_facts
        self.assertIn("Half marathon in October", brief.memory_context["priority_facts"])
        self.assertIn("Weekday sessions need to finish before 7am", brief.memory_context["priority_facts"])
        # preference → context_facts
        self.assertEqual(len(brief.memory_context["context_facts"]), 2)
        self.assertTrue(brief.memory_context["memory_available"])

    def test_empty_memory_notes_with_continuity_still_available(self):
        brief = build_response_brief(
            athlete_id="ath_5",
            reply_kind="coaching_reply",
            inbound_subject="Next week",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "Half marathon"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context={
                "memory_notes": [],
                "continuity_summary": _continuity_summary(),
            },
        )

        self.assertNotIn("priority_facts", brief.memory_context)
        self.assertNotIn("structure_facts", brief.memory_context)
        self.assertNotIn("context_facts", brief.memory_context)
        self.assertEqual(
            brief.memory_context["continuity_focus"],
            "Athlete is rebuilding consistency.",
        )
        self.assertTrue(brief.memory_context["memory_available"])


class TestBuildResponseGenerationInput(unittest.TestCase):
    def test_strips_strategist_only_fields_before_writer_validation(self):
        brief = ResponseBrief.from_dict(
            {
                "reply_mode": "normal_coaching",
                "athlete_context": {},
                "decision_context": {},
                "validated_plan": {
                    "plan_summary": "Keep the week simple.",
                },
                "delivery_context": {
                    "inbound_subject": "Check-in",
                },
                "memory_context": {
                    "memory_available": False,
                    "continuity_summary": None,
                },
            }
        )

        payload = build_response_generation_input(
            directive={
                "reply_action": "send",
                "opening": "Good update.",
                "main_message": "Keep one key session only.",
                "content_plan": ["Acknowledge the update", "Set the weekly focus"],
                "avoid": ["Do not add extra volume"],
                "tone": "calm and direct",
                "recommend_material": None,
                "rationale": "Internal only.",
            },
            brief=brief,
        )

        self.assertNotIn("reply_action", payload["coaching_directive"])
        self.assertNotIn("rationale", payload["coaching_directive"])

    def test_safety_and_off_topic_map_to_canonical_modes_without_validated_plan(self):
        safety = build_response_brief(
            athlete_id="ath_1",
            reply_kind="safety_concern",
            inbound_subject="Pain question",
            selected_model_name="gpt-5-nano",
            profile_after={},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision={"intent": "safety_concern"},
            memory_context=_empty_memory_context(),
        )
        off_topic = build_response_brief(
            athlete_id="ath_1",
            reply_kind="off_topic",
            inbound_subject="Shoes",
            selected_model_name=None,
            profile_after={},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision={"intent": "off_topic"},
            memory_context=_empty_memory_context(),
        )

        self.assertEqual(safety.reply_mode, "safety_risk_managed")
        self.assertEqual(safety.validated_plan, {})
        self.assertEqual(safety.decision_context, {})
        self.assertEqual(off_topic.reply_mode, "off_topic_redirect")
        self.assertEqual(off_topic.validated_plan, {})
        self.assertEqual(off_topic.decision_context, {})

    def test_lightweight_non_planning_omits_validated_plan_fields(self):
        brief = build_response_brief(
            athlete_id="ath_7",
            reply_kind="lightweight_non_planning",
            inbound_subject="Easy run question",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k", "experience_level": "intermediate"},
            missing_profile_fields=[],
            plan_summary="Current plan - Goal: 10k.",
            rule_engine_decision={
                "intent": "question",
                "engine_output": {
                    "classification_label": "deterministic_re3_transition",
                    "track": "main_build",
                    "phase": "build",
                    "risk_flag": "green",
                    "weekly_skeleton": ["easy_aerobic", "strength"],
                    "today_action": "do_planned",
                    "plan_update_status": "updated",
                    "adjustments": ["hold_steady"],
                    "next_email_payload": {
                        "subject_hint": "This week: execute with control",
                        "summary": "Training can continue.",
                        "sessions": ["session_1: easy_aerobic"],
                        "plan_focus_line": "Hit the key sessions without forcing extra load.",
                        "technique_cue": "Keep effort smooth.",
                        "recovery_target": "Sleep well.",
                        "if_then_rules": ["Do not make up missed intensity."],
                        "disclaimer_short": "",
                        "safety_note": "No hard sessions when risk is red-tier.",
                    },
                },
            },
            memory_context={
                "memory_notes": [
                    _memory_note(
                        memory_note_id="f1",
                        fact_type="constraint",
                        fact_key="constraint:early-finish",
                        summary="Weekday sessions need to finish before 7am",
                    ),
                ],
                "continuity_summary": _continuity_summary(),
            },
        )

        self.assertEqual(brief.reply_mode, "lightweight_non_planning")
        self.assertEqual(brief.validated_plan, {})
        self.assertEqual(brief.decision_context, {})

    def test_lightweight_non_planning_with_missing_injury_uses_targeted_followup(self):
        brief = build_response_brief(
            athlete_id="ath_q1",
            reply_kind="lightweight_non_planning",
            inbound_subject="Easy run question",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k", "experience_level": "intermediate"},
            missing_profile_fields=["injury_status"],
            plan_summary="Current plan - Goal: 10k.",
            rule_engine_decision={"intent": "question"},
            memory_context=_empty_memory_context(),
        )

        self.assertEqual(brief.reply_mode, "lightweight_non_planning")
        self.assertEqual(brief.validated_plan, {})
        self.assertNotIn("missing_profile_fields", brief.decision_context)
        self.assertNotIn("clarification_needed", brief.decision_context)
        self.assertEqual(
            brief.decision_context["clarification_questions"],
            [
                "- Any current injuries, pains, or physical limitations (perfectly fine if there are none — just let me know either way)"
            ],
        )

    def test_missing_plan_summary_and_memory_context_degrade_gracefully(self):
        brief = build_response_brief(
            athlete_id="ath_1",
            reply_kind="coaching_reply",
            inbound_subject=None,
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context={},
        )

        self.assertEqual(brief.validated_plan, {})
        self.assertIsNone(brief.memory_context["continuity_summary"])
        self.assertFalse(brief.memory_context["memory_available"])

    def test_invalid_rule_engine_output_does_not_leak_into_brief(self):
        brief = build_response_brief(
            athlete_id="ath_1",
            reply_kind="rule_engine_guided",
            inbound_subject="Weekly check-in",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary="Current plan - Goal: 10k.",
            rule_engine_decision={
                "reply_strategy": "rule_engine_guided",
                "engine_output": {"track": "main_build"},
            },
            memory_context=_empty_memory_context(),
        )

        self.assertEqual(brief.decision_context, {})
        self.assertEqual(brief.validated_plan, {"plan_summary": "Current plan - Goal: 10k."})

    def test_invalid_memory_artifacts_degrade_gracefully_without_failing(self):
        brief = build_response_brief(
            athlete_id="ath_6",
            reply_kind="coaching_reply",
            inbound_subject="Weekly check-in",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context={
                "memory_notes": "not a list",
                "continuity_summary": {"summary": " "},
            },
        )

        self.assertNotIn("priority_facts", brief.memory_context)
        self.assertNotIn("structure_facts", brief.memory_context)
        self.assertNotIn("context_facts", brief.memory_context)
        self.assertIsNone(brief.memory_context["continuity_summary"])
        self.assertFalse(brief.memory_context["memory_available"])


class TestExtractAthleteInstructions(unittest.TestCase):
    """Tests for deterministic athlete instruction extraction."""

    def test_empty_body_returns_empty(self):
        self.assertEqual(extract_athlete_instructions(None), {})
        self.assertEqual(extract_athlete_instructions(""), {})

    def test_no_instructions_returns_empty(self):
        result = extract_athlete_instructions("Ran easy 30 min today, felt good.")
        self.assertEqual(result, {})

    def test_forbidden_topic_dont_mention(self):
        result = extract_athlete_instructions(
            "Don't mention the Achilles anymore. Just tell me the sessions."
        )
        self.assertIn("forbidden_topics", result)
        self.assertTrue(
            any("achilles" in t.lower() for t in result["forbidden_topics"]),
            f"Expected 'achilles' in forbidden_topics, got: {result['forbidden_topics']}",
        )

    def test_forbidden_topic_stop_bringing_up(self):
        result = extract_athlete_instructions(
            "Stop bringing up week labels. I told you already."
        )
        self.assertIn("forbidden_topics", result)
        self.assertTrue(
            any("week" in t.lower() for t in result["forbidden_topics"]),
            f"Expected 'week' in forbidden_topics, got: {result['forbidden_topics']}",
        )

    def test_forbidden_topic_please_stop_labeling(self):
        result = extract_athlete_instructions(
            "Please stop labeling weeks. Just reference the locked build."
        )
        self.assertIn("forbidden_topics", result)

    def test_scope_just_tell_me(self):
        result = extract_athlete_instructions(
            "Just tell me this week's sessions."
        )
        self.assertIn("requested_scope", result)
        self.assertIn("this week", result["requested_scope"].lower())

    def test_scope_keep_it_short(self):
        result = extract_athlete_instructions(
            "Keep it short. Confirm I'm good to go this weekend."
        )
        self.assertIn("requested_scope", result)

    def test_format_three_lines_max(self):
        result = extract_athlete_instructions(
            "Send the three lines I asked for: 3 lines max."
        )
        self.assertIn("format_constraints", result)
        self.assertIn("3 lines max", result["format_constraints"].lower())

    def test_format_one_paragraph(self):
        result = extract_athlete_instructions(
            "Keep confirmations one short paragraph."
        )
        self.assertIn("format_constraints", result)

    def test_reply_suppression_only_reply_if(self):
        result = extract_athlete_instructions(
            "Please only reply if there's a concern."
        )
        self.assertIn("reply_suppression_hint", result)
        self.assertIn("only reply if", result["reply_suppression_hint"].lower())

    def test_reply_suppression_no_reply_unless(self):
        result = extract_athlete_instructions(
            "No reply needed unless you see a safety issue."
        )
        self.assertIn("reply_suppression_hint", result)

    def test_override_i_can_now(self):
        result = extract_athlete_instructions(
            "I can now run 5 days a week. My schedule opened up."
        )
        self.assertIn("latest_overrides", result)
        self.assertTrue(len(result["latest_overrides"]) > 0)

    def test_override_please_correct(self):
        result = extract_athlete_instructions(
            "Please correct: start from Week 2, not Week 3."
        )
        self.assertIn("latest_overrides", result)

    def test_multiple_instructions_in_one_message(self):
        result = extract_athlete_instructions(
            "Don't mention the Achilles. Keep it short. "
            "Only reply if there's a concern."
        )
        self.assertIn("forbidden_topics", result)
        self.assertIn("requested_scope", result)
        self.assertIn("reply_suppression_hint", result)


class TestDetectContradictedFacts(unittest.TestCase):
    """Tests for memory fact contradiction detection."""

    def test_empty_inputs_return_empty(self):
        self.assertEqual(detect_contradicted_facts(None, []), [])
        self.assertEqual(detect_contradicted_facts("hello", []), [])
        self.assertEqual(detect_contradicted_facts(None, ["some fact"]), [])

    def test_no_contradiction_returns_empty(self):
        result = detect_contradicted_facts(
            "Ran easy 30 min today. Felt good.",
            ["Goal: fall half marathon", "Constraint: Achilles tightness"],
        )
        self.assertEqual(result, [])

    def test_detects_achilles_resolved(self):
        result = detect_contradicted_facts(
            "The Achilles tightness is no longer an issue. It cleared up last week.",
            ["Constraint: Achilles tightness"],
        )
        self.assertTrue(len(result) > 0)
        self.assertTrue(any("Achilles" in c for c in result))

    def test_detects_schedule_change(self):
        result = detect_contradicted_facts(
            "I can now do 5 days a week. My schedule changed.",
            ["Available 4 days per week"],
        )
        self.assertTrue(len(result) > 0)

    def test_does_not_flag_unrelated_negation(self):
        result = detect_contradicted_facts(
            "I no longer need the Garmin link.",
            ["Goal: fall half marathon", "Constraint: Achilles tightness"],
        )
        self.assertEqual(result, [])


class TestBuildResponseBriefAthleteInstructions(unittest.TestCase):
    """Integration test: athlete_instructions flow through build_response_brief."""

    def test_forbidden_topics_appear_in_brief(self):
        brief = build_response_brief(
            athlete_id="ath_inst_1",
            reply_kind="coaching_reply",
            inbound_subject="Update",
            inbound_body="Don't mention the Achilles anymore. What are my sessions?",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context=_empty_memory_context(),
        )

        instructions = brief.delivery_context.get("athlete_instructions", {})
        self.assertIn("forbidden_topics", instructions)

    def test_suppression_hint_appears_in_brief(self):
        brief = build_response_brief(
            athlete_id="ath_inst_2",
            reply_kind="coaching_reply",
            inbound_subject="Check-in",
            inbound_body="Ran easy, felt fine. Only reply if there's a concern.",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context=_empty_memory_context(),
        )

        instructions = brief.delivery_context.get("athlete_instructions", {})
        self.assertIn("reply_suppression_hint", instructions)

    def test_no_instructions_omits_field(self):
        brief = build_response_brief(
            athlete_id="ath_inst_3",
            reply_kind="coaching_reply",
            inbound_subject="Update",
            inbound_body="Ran easy 30 min today. Felt good.",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context=_empty_memory_context(),
        )

        self.assertNotIn("athlete_instructions", brief.delivery_context)

    def test_contradicted_facts_appear_in_brief(self):
        brief = build_response_brief(
            athlete_id="ath_inst_4",
            reply_kind="coaching_reply",
            inbound_subject="Update",
            inbound_body="The knee issue is no longer a problem. Cleared up.",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision=None,
            memory_context={
                "memory_notes": [
                    _memory_note(
                        memory_note_id="f1",
                        fact_type="constraint",
                        fact_key="constraint:knee",
                        summary="Recurring knee issue after long runs",
                    ),
                ],
                "continuity_summary": None,
            },
        )

        self.assertIn("contradicted_facts", brief.memory_context)
        self.assertTrue(len(brief.memory_context["contradicted_facts"]) > 0)


class TestStrategistPromptNewSections(unittest.TestCase):
    """Test that new prompt sections are injected correctly."""

    def test_athlete_instructions_section_appears_in_strategist_prompt(self):
        from skills.coaching_reasoning.prompt import build_system_prompt

        brief = {
            "reply_mode": "normal_coaching",
            "athlete_context": {},
            "decision_context": {},
            "validated_plan": {},
            "delivery_context": {
                "inbound_body": "Don't mention the Achilles.",
                "athlete_instructions": {
                    "forbidden_topics": ["the Achilles"],
                },
            },
            "memory_context": {
                "memory_available": False,
                "continuity_summary": None,
            },
        }

        prompt = build_system_prompt(brief)
        self.assertIn("Athlete instructions", prompt)
        self.assertIn("Forbidden topics", prompt)
        self.assertIn("the Achilles", prompt)

    def test_contradicted_facts_section_appears_in_strategist_prompt(self):
        from skills.coaching_reasoning.prompt import build_system_prompt

        brief = {
            "reply_mode": "normal_coaching",
            "athlete_context": {},
            "decision_context": {},
            "validated_plan": {},
            "delivery_context": {
                "inbound_body": "Knee is fine now.",
            },
            "memory_context": {
                "memory_available": True,
                "continuity_summary": None,
                "priority_facts": ["Recurring knee issue"],
                "contradicted_facts": [
                    'Prior fact "Recurring knee issue" may be superseded by current message'
                ],
            },
        }

        prompt = build_system_prompt(brief)
        self.assertIn("Contradicted durable facts", prompt)
        self.assertIn("Recurring knee issue", prompt)

    def test_no_sections_when_no_instructions_or_contradictions(self):
        from skills.coaching_reasoning.prompt import build_system_prompt

        brief = {
            "reply_mode": "normal_coaching",
            "athlete_context": {},
            "decision_context": {},
            "validated_plan": {},
            "delivery_context": {
                "inbound_body": "Ran easy, felt good.",
            },
            "memory_context": {
                "memory_available": False,
                "continuity_summary": None,
            },
        }

        prompt = build_system_prompt(brief)
        self.assertNotIn("Athlete instructions", prompt)
        self.assertNotIn("Contradicted durable facts", prompt)


class TestBriefShapingEdgeCases(unittest.TestCase):
    """Phase 7: Additional edge cases for athlete instruction extraction and contradiction detection."""

    def test_forbidden_topic_do_not_revisit(self):
        result = extract_athlete_instructions("Do not revisit the scheduling discussion.")
        self.assertIn("forbidden_topics", result)

    def test_forbidden_topic_stop_asking_about(self):
        result = extract_athlete_instructions("Stop asking about my availability.")
        self.assertIn("forbidden_topics", result)

    def test_scope_only_tell_me(self):
        result = extract_athlete_instructions("Only tell me the sessions for this week.")
        self.assertIn("requested_scope", result)

    def test_override_please_update(self):
        result = extract_athlete_instructions("Please update: it's 5 days now, not 4.")
        self.assertIn("latest_overrides", result)

    def test_multiple_contradicted_facts(self):
        result = detect_contradicted_facts(
            "The knee is no longer an issue and I can now run 5 days.",
            [
                "Constraint: recurring knee pain",
                "Available 4 days per week",
            ],
        )
        self.assertGreaterEqual(len(result), 1)

    def test_no_false_positive_on_positive_mention(self):
        """Mentioning a keyword without negation should not flag contradiction."""
        result = detect_contradicted_facts(
            "My knee felt good on the long run.",
            ["Constraint: recurring knee pain"],
        )
        self.assertEqual(result, [])


class TestWriterBriefStripsStrategistFields(unittest.TestCase):
    """Verify build_response_generation_input strips strategist-only fields."""

    def test_rationale_and_reply_action_stripped(self):
        directive = {
            "opening": "Test",
            "main_message": "Brief.",
            "content_plan": ["ack"],
            "avoid": [],
            "tone": "calm",
            "recommend_material": None,
            "rationale": "Internal reasoning here",
            "reply_action": "send",
        }
        brief = build_response_brief(
            athlete_id="ath_strip",
            reply_kind="coaching_reply",
            inbound_subject="Update",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary="Simple plan.",
            rule_engine_decision=None,
            memory_context=_empty_memory_context(),
        )
        rg_input = build_response_generation_input(
            directive=directive,
            brief=brief,
        )
        self.assertNotIn("rationale", rg_input["coaching_directive"])
        self.assertNotIn("reply_action", rg_input["coaching_directive"])
        self.assertIn("opening", rg_input["coaching_directive"])

    def test_continuity_context_forwarded_when_present(self):
        directive = {
            "opening": "Test",
            "main_message": "Plan.",
            "content_plan": ["plan"],
            "avoid": [],
            "tone": "calm",
            "recommend_material": None,
        }
        brief = build_response_brief(
            athlete_id="ath_ctx",
            reply_kind="coaching_reply",
            inbound_subject="Update",
            selected_model_name="gpt-5-nano",
            profile_after={"primary_goal": "10k"},
            missing_profile_fields=[],
            plan_summary="Plan.",
            rule_engine_decision=None,
            memory_context=_empty_memory_context(),
        )
        continuity = {"weeks_in_current_block": 3, "current_block_focus": "base"}
        rg_input = build_response_generation_input(
            directive=directive,
            brief=brief,
            continuity_context=continuity,
        )
        self.assertEqual(rg_input["continuity_context"]["weeks_in_current_block"], 3)


if __name__ == "__main__":
    unittest.main()
