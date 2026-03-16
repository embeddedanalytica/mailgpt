import unittest

from response_generation_assembly import build_response_brief


def _memory_note(note_id: int = 1) -> dict:
    return {
        "memory_note_id": note_id,
        "fact_type": "constraint",
        "fact_key": f"weekday_before_7am_cutoff_{note_id}",
        "summary": "Weekday sessions need to finish before 7am",
        "importance": "high",
        "status": "active",
        "created_at": 1773273600,
        "updated_at": 1773273600,
        "last_confirmed_at": 1773273600,
    }


def _continuity_summary() -> dict:
    return {
        "summary": "Athlete is rebuilding consistency.",
        "last_recommendation": "Keep one controlled quality session this week.",
        "open_loops": ["How did the quality session feel?"],
        "updated_at": 1773273600,
    }


class TestBuildResponseBrief(unittest.TestCase):
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
            pre_reply_refresh_attempted=True,
            post_reply_refresh_eligible=False,
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
                "memory_notes": [_memory_note()],
                "continuity_summary": _continuity_summary(),
            },
            pre_reply_refresh_attempted=True,
            post_reply_refresh_eligible=True,
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
        self.assertEqual(len(brief.memory_context["memory_notes"]), 1)
        self.assertEqual(brief.memory_context["continuity_summary"]["summary"], "Athlete is rebuilding consistency.")
        self.assertEqual(brief.memory_context["memory_available"], True)
        self.assertEqual(
            brief.memory_context["continuity_focus"],
            "Athlete is rebuilding consistency.",
        )
        self.assertEqual(
            [note["memory_note_id"] for note in brief.memory_context["priority_memory_notes"]],
            [1],
        )
        self.assertEqual(brief.memory_context["supporting_memory_notes"], [])

    def test_rule_engine_guided_includes_validated_engine_fields(self):
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
            memory_context={"memory_notes": [], "continuity_summary": None},
            pre_reply_refresh_attempted=False,
            post_reply_refresh_eligible=True,
        )

        self.assertEqual(brief.reply_mode, "normal_coaching")
        self.assertEqual(brief.decision_context["track"], "return_or_risk_managed")
        self.assertEqual(brief.decision_context["phase"], "build")
        self.assertEqual(brief.decision_context["risk_flag"], "yellow")
        self.assertEqual(brief.decision_context["today_action"], "prioritize_big_2_anchors")
        self.assertEqual(brief.decision_context["plan_update_status"], "updated")
        self.assertEqual(brief.validated_plan["weekly_skeleton"], ["easy_aerobic", "strength"])
        self.assertEqual(
            brief.validated_plan["session_guidance"],
            ["Priority: long easy aerobic session"],
        )
        self.assertEqual(
            brief.validated_plan["adjustments_or_priorities"],
            [
                "This is a risk-managed week.",
                "Use safety and consistency as the primary filter.",
                "Keep cadence light and posture tall.",
                "Prioritize recovery basics before adding any load.",
            ],
        )
        self.assertEqual(
            brief.validated_plan["if_then_rules"],
            ["If symptoms rise, remove intensity immediately."],
        )
        self.assertEqual(
            brief.validated_plan["safety_note"],
            "No hard sessions when risk is red-tier.",
        )

    def test_memory_salience_uses_high_importance_notes_as_priority_and_rest_as_supporting(self):
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
                    _memory_note(1),
                    {
                        **_memory_note(2),
                        "importance": "medium",
                        "summary": "Travel every third week of the month",
                        "fact_key": "travel_every_third_week",
                    },
                    {
                        **_memory_note(3),
                        "importance": "low",
                        "summary": "Prefers concise bullets",
                        "fact_key": "prefers_concise_bullets",
                    },
                ],
                "continuity_summary": _continuity_summary(),
            },
            pre_reply_refresh_attempted=True,
            post_reply_refresh_eligible=True,
        )

        self.assertEqual(
            [note["memory_note_id"] for note in brief.memory_context["priority_memory_notes"]],
            [1],
        )
        self.assertEqual(
            [note["memory_note_id"] for note in brief.memory_context["supporting_memory_notes"]],
            [2, 3],
        )

    def test_memory_salience_promotes_most_recent_note_when_no_high_notes_exist(self):
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
                "memory_notes": [
                    {
                        **_memory_note(2),
                        "importance": "low",
                        "summary": "Most recent note",
                        "fact_key": "preference:most_recent_note",
                        "created_at": 1773187200,
                        "updated_at": 1773273600,
                        "last_confirmed_at": 1773273600,
                    },
                    {
                        **_memory_note(1),
                        "importance": "medium",
                        "summary": "Less recent note",
                        "fact_key": "schedule:less_recent_note",
                        "created_at": 1773097200,
                        "updated_at": 1773187200,
                        "last_confirmed_at": 1773187200,
                    },
                ],
                "continuity_summary": None,
            },
            pre_reply_refresh_attempted=True,
            post_reply_refresh_eligible=True,
        )

        self.assertEqual(
            [note["memory_note_id"] for note in brief.memory_context["priority_memory_notes"]],
            [2],
        )
        self.assertEqual(
            [note["memory_note_id"] for note in brief.memory_context["supporting_memory_notes"]],
            [1],
        )

    def test_safety_and_off_topic_map_to_canonical_modes_without_validated_plan(self):
        safety = build_response_brief(
            athlete_id="ath_1",
            reply_kind="safety_concern",
            inbound_subject="Pain question",
            selected_model_name="gpt-5-nano",
            profile_after={},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision={"reply_strategy": "safety_concern"},
            memory_context={"memory_notes": [], "continuity_summary": None},
            pre_reply_refresh_attempted=False,
            post_reply_refresh_eligible=False,
        )
        off_topic = build_response_brief(
            athlete_id="ath_1",
            reply_kind="off_topic",
            inbound_subject="Shoes",
            selected_model_name=None,
            profile_after={},
            missing_profile_fields=[],
            plan_summary=None,
            rule_engine_decision={"reply_strategy": "off_topic"},
            memory_context={"memory_notes": [], "continuity_summary": None},
            pre_reply_refresh_attempted=False,
            post_reply_refresh_eligible=False,
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
            memory_context={"memory_notes": [_memory_note()], "continuity_summary": _continuity_summary()},
            pre_reply_refresh_attempted=True,
            post_reply_refresh_eligible=True,
        )

        self.assertEqual(brief.reply_mode, "lightweight_non_planning")
        self.assertEqual(brief.validated_plan, {})
        self.assertEqual(brief.decision_context["track"], "main_build")

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
            pre_reply_refresh_attempted=False,
            post_reply_refresh_eligible=True,
        )

        self.assertEqual(brief.validated_plan, {})
        self.assertEqual(brief.memory_context["memory_notes"], [])
        self.assertIsNone(brief.memory_context["continuity_summary"])
        self.assertIsNone(brief.memory_context["continuity_focus"])
        self.assertEqual(brief.memory_context["priority_memory_notes"], [])
        self.assertEqual(brief.memory_context["supporting_memory_notes"], [])
        self.assertEqual(brief.delivery_context["response_channel"], "email")

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
            memory_context={"memory_notes": [], "continuity_summary": None},
            pre_reply_refresh_attempted=False,
            post_reply_refresh_eligible=True,
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
                "memory_notes": [{"summary": "Missing required fields"}],
                "continuity_summary": {"summary": " "},
            },
            pre_reply_refresh_attempted=True,
            post_reply_refresh_eligible=True,
        )

        self.assertEqual(brief.memory_context["memory_notes"], [])
        self.assertIsNone(brief.memory_context["continuity_summary"])
        self.assertIsNone(brief.memory_context["continuity_focus"])
        self.assertEqual(brief.memory_context["priority_memory_notes"], [])
        self.assertEqual(brief.memory_context["supporting_memory_notes"], [])
        self.assertFalse(brief.memory_context["memory_available"])


if __name__ == "__main__":
    unittest.main()
