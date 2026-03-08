"""Consolidated tests for pure rule-engine logic."""

from __future__ import annotations

import unittest
from datetime import date, timedelta

from _test_support import valid_engine_output_payload
from rule_engine import (
    EVENT_DATE_VALIDATION_STATUSES,
    HARD_SESSION_TAGS,
    NON_HARD_SESSION_TAGS,
    PHASES,
    PLAN_UPDATE_STATUSES,
    RISK_FLAGS,
    TRACKS,
    RuleEngineArchetypeError,
    RuleEngineContractError,
    RuleEngineDateValidationError,
    RuleEngineIntentError,
    RuleEngineOutput,
    RuleEnginePhaseError,
    RuleEngineRiskError,
    RuleEngineSkeletonError,
    RuleEngineStabilizationError,
    RuleEngineSwitchingError,
    RuleEngineTrackError,
    apply_event_date_validation_guard,
    apply_main_sport_deload_adjustments,
    apply_phase_upgrade_hysteresis,
    apply_risk_overrides,
    apply_switch_transition_limits,
    build_decision_envelope,
    build_planner_brief,
    build_weekly_skeleton,
    compose_email_payload,
    derive_calendar_phase,
    derive_phase,
    derive_risk,
    detect_inconsistent_training,
    detect_infeasible_week,
    is_hard_session_tag,
    is_sustained_yellow,
    is_valid_event_date_status,
    is_valid_phase,
    is_valid_plan_update_status,
    is_valid_risk_flag,
    is_valid_track,
    normalize_goal_category,
    normalize_track_name,
    quality_archetype_for_experience,
    resolve_effective_performance_intent,
    resolve_main_sport_after_guardrails,
    repair_or_fallback_plan,
    route_today_action,
    select_quality_archetype,
    select_track,
    should_switch_main_sport,
    should_trigger_main_sport_deload,
    validate_event_date,
    validate_hard_session_tags,
    validate_planner_output,
    validate_rule_engine_output,
)


class TestRuleEngineContract(unittest.TestCase):
    def test_membership_helpers(self):
        for value in PHASES:
            self.assertTrue(is_valid_phase(value))
        for value in RISK_FLAGS:
            self.assertTrue(is_valid_risk_flag(value))
        for value in TRACKS:
            self.assertTrue(is_valid_track(value))
        for value in PLAN_UPDATE_STATUSES:
            self.assertTrue(is_valid_plan_update_status(value))

    def test_validate_output_and_round_trip(self):
        payload = valid_engine_output_payload()
        validate_rule_engine_output(payload)
        self.assertEqual(RuleEngineOutput.from_dict(payload).to_dict(), payload)

    def test_contract_rejects_missing_or_extra_fields(self):
        payload = valid_engine_output_payload()
        payload.pop("track")
        with self.assertRaises(RuleEngineContractError):
            validate_rule_engine_output(payload)

        payload = valid_engine_output_payload()
        payload["next_email_payload"]["cta"] = "reply"
        with self.assertRaises(RuleEngineContractError):
            validate_rule_engine_output(payload)

    def test_red_b_requires_disclaimer(self):
        payload = valid_engine_output_payload(risk_flag="red_b")
        payload["next_email_payload"]["disclaimer_short"] = " "
        with self.assertRaises(RuleEngineContractError):
            validate_rule_engine_output(payload)

    def test_hard_session_tag_helpers(self):
        for tag in HARD_SESSION_TAGS:
            self.assertTrue(is_hard_session_tag(tag))
        for tag in NON_HARD_SESSION_TAGS:
            self.assertFalse(is_hard_session_tag(tag))
        validate_hard_session_tags(["tempo", "easy_aerobic", "strength"])
        with self.assertRaises(RuleEngineContractError):
            validate_hard_session_tags(["tempo", "unknown_tag"])

    def test_naming_normalization(self):
        self.assertEqual(normalize_track_name("main_sport_build"), "main_build")
        self.assertEqual(
            normalize_goal_category({"primary_goal_timeframe": "performance"}),
            "performance_16w_plus",
        )


class TestEventDateAndIntent(unittest.TestCase):
    def test_event_date_validation_and_guard(self):
        today = date(2026, 3, 3)
        self.assertEqual(validate_event_date({"event_date": None}, today), "invalid_missing")
        self.assertEqual(validate_event_date({"event_date": "03/20/2026"}, today), "invalid_format")
        self.assertEqual(validate_event_date({"event_date": "2026-03-02"}, today), "invalid_past")
        self.assertEqual(validate_event_date({"event_date": "2026-03-03"}, today), "valid")
        self.assertTrue(all(is_valid_event_date_status(status) for status in EVENT_DATE_VALIDATION_STATUSES))

        phase, plan_status = apply_event_date_validation_guard(
            validation_status="invalid_past",
            candidate_phase="peak_taper",
            prior_phase="build",
        )
        self.assertEqual((phase, plan_status), ("build", "unchanged_clarification_needed"))

    def test_effective_performance_intent_fallback(self):
        self.assertTrue(
            resolve_effective_performance_intent(
                {"performance_intent_default": False},
                {"performance_intent_this_week": True},
            )
        )
        self.assertTrue(
            resolve_effective_performance_intent(
                {"performance_intent_default": True},
                {"performance_intent_this_week": None},
            )
        )
        self.assertFalse(resolve_effective_performance_intent({}, {}))


class TestRiskAndPhase(unittest.TestCase):
    def setUp(self):
        self.today = date(2026, 3, 3)
        self.peak_event = {"event_date": (self.today + timedelta(days=14)).strftime("%Y-%m-%d")}

    def test_risk_precedence_and_worsening(self):
        self.assertEqual(derive_risk({}, {"risk_candidate": "yellow"}, {}), "yellow")
        self.assertEqual(derive_risk({}, {"pain_sharp": True}, {}), "red_b")
        self.assertEqual(derive_risk({}, {"pain_score": 5}, {}), "red_a")
        self.assertEqual(
            derive_risk({"injury_baseline": "recurring_niggles"}, {"pain_score": 1}, {}),
            "yellow",
        )
        self.assertEqual(
            derive_risk({}, {"pain_score": 4}, {"weekly_signals_last_4": [{"pain_score": 2}]}),
            "red_b",
        )

    def test_calendar_phase_boundaries(self):
        self.assertEqual(
            derive_calendar_phase({"event_date": (self.today + timedelta(days=85)).strftime("%Y-%m-%d")}, self.today),
            "base",
        )
        self.assertEqual(
            derive_calendar_phase({"event_date": (self.today + timedelta(days=84)).strftime("%Y-%m-%d")}, self.today),
            "build",
        )
        self.assertEqual(
            derive_calendar_phase({"event_date": (self.today + timedelta(days=21)).strftime("%Y-%m-%d")}, self.today),
            "peak_taper",
        )

    def test_phase_overrides(self):
        self.assertEqual(
            derive_phase(
                {},
                {**self.peak_event, "returning_from_break": True},
                self.today,
                {},
                risk_flag="green",
                effective_performance_intent=False,
            ),
            "return_to_training",
        )
        self.assertEqual(
            derive_phase(
                {"experience_level": "new"},
                {**self.peak_event, "has_upcoming_event": True},
                self.today,
                {},
                risk_flag="green",
                effective_performance_intent=False,
            ),
            "base",
        )
        self.assertEqual(
            derive_phase(
                {"goal_category": "event_8_16w"},
                {**self.peak_event, "has_upcoming_event": None},
                self.today,
                {},
                risk_flag="green",
                effective_performance_intent=False,
            ),
            "peak_taper",
        )
        self.assertEqual(
            derive_phase(
                {"goal_category": "general_consistency"},
                {"has_upcoming_event": False},
                self.today,
                {},
                risk_flag="green",
                effective_performance_intent=True,
            ),
            "build",
        )


class TestTrackSwitchingAndDeload(unittest.TestCase):
    def test_track_selection(self):
        self.assertEqual(
            select_track({"main_sport_current": None, "time_bucket": "2_3h"}, "base", "green"),
            "general_low_time",
        )
        self.assertEqual(
            select_track({"main_sport_current": "run", "time_bucket": "4_6h"}, "build", "green"),
            "main_build",
        )
        self.assertEqual(
            select_track({"main_sport_current": "run", "time_bucket": "4_6h"}, "peak_taper", "red_b"),
            "return_or_risk_managed",
        )

    def test_switching_guardrails(self):
        profile = {"main_sport_current": "run"}
        checkin = {
            "sports_last_week": [{"sport": "bike", "minutes": 80}, {"sport": "run", "minutes": 40}],
        }
        rule_state = {
            "weekly_signals_last_4": [{"sports_minutes_by_sport": {"bike": 20, "run": 20}}],
        }
        self.assertTrue(should_switch_main_sport(profile, checkin, rule_state))
        self.assertEqual(
            resolve_main_sport_after_guardrails(
                profile,
                {
                    "sports_last_week": [{"sport": "bike", "minutes": 100}, {"sport": "run", "minutes": 20}],
                    "requested_main_sport": "bike",
                },
                {
                    "main_sport_transition_weeks_remaining": 1,
                    "weekly_signals_last_4": [{"sports_minutes_by_sport": {"bike": 50, "run": 20}}],
                },
                "green",
            ),
            "run",
        )
        constrained = apply_switch_transition_limits(
            {"max_quality_sessions_per_week": 3, "max_weekly_volume_increase_pct": 15},
            {"main_sport_transition_weeks_remaining": 2},
            {},
        )
        self.assertEqual(constrained["max_quality_sessions_per_week"], 1)
        self.assertEqual(constrained["max_weekly_volume_increase_pct"], 10)

    def test_deload_rules(self):
        self.assertTrue(
            is_sustained_yellow(
                {"phase_risk_time_last_6": [{"risk_flag": "yellow"}, {"risk_flag": "green"}, {"risk_flag": "yellow"}]},
                "yellow",
            )
        )
        self.assertTrue(should_trigger_main_sport_deload("build", {"weeks_since_deload": 4}, "green"))
        self.assertFalse(should_trigger_main_sport_deload("peak_taper", {"weeks_since_deload": 6}, "green"))
        adjusted = apply_main_sport_deload_adjustments(["easy_aerobic", "tempo", "strength"])
        self.assertNotIn("tempo", adjusted)
        self.assertIn("deload_volume_reduce_20pct", adjusted)


class TestArchetypesAndSkeleton(unittest.TestCase):
    def test_archetype_selection(self):
        self.assertEqual(quality_archetype_for_experience("new")["template"], "strides_hills_or_short_tempo")
        self.assertEqual(quality_archetype_for_experience("advanced")["template"], "event_specific_intervals")
        self.assertEqual(
            select_quality_archetype({"experience_level": "advanced"}, "red_b", "low")["max_quality_sessions_per_week"],
            0,
        )
        self.assertEqual(
            select_quality_archetype({"experience_level": "advanced"}, "green", "high")["template"],
            "conservative_quality_variant",
        )

    def test_skeleton_building_and_overrides(self):
        general = build_weekly_skeleton(
            profile={"time_bucket": "4_6h"},
            checkin={"days_available": 4},
            track="general_moderate_time",
            phase="build",
            risk_flag="green",
            effective_performance_intent=True,
            rule_state={},
        )
        self.assertIn("quality", general["weekly_skeleton"])

        advanced = build_weekly_skeleton(
            profile={
                "main_sport_current": "run",
                "time_bucket": "10h_plus",
                "experience_level": "advanced",
                "schedule_variability": "medium",
            },
            checkin={"days_available": 10},
            track="main_build",
            phase="build",
            risk_flag="green",
            effective_performance_intent=True,
            rule_state={},
        )
        hard_count = sum(1 for token in advanced["weekly_skeleton"] if token in HARD_SESSION_TAGS)
        self.assertGreaterEqual(hard_count, 2)

        red_sessions, red_adjustments = apply_risk_overrides(
            ["quality", "easy_aerobic", "threshold"],
            "red_b",
            "main_build",
        )
        self.assertTrue(all(token not in HARD_SESSION_TAGS for token in red_sessions))
        self.assertIn("clinician_stop_recommended", red_adjustments)

        infeasible = build_weekly_skeleton(
            profile={"time_bucket": "4_6h"},
            checkin={"days_available": 1},
            track="general_moderate_time",
            phase="base",
            risk_flag="green",
            effective_performance_intent=False,
            rule_state={},
        )
        self.assertEqual(infeasible["plan_update_status"], "unchanged_infeasible_week")
        self.assertEqual(infeasible["weekly_skeleton"], [])
        self.assertTrue(detect_infeasible_week({}, {"days_available": 1}, ["easy_aerobic"]))


class TestStabilizationAndInvalidInputs(unittest.TestCase):
    def test_stabilization(self):
        self.assertTrue(detect_inconsistent_training(["base"], "build", "green"))
        self.assertEqual(apply_phase_upgrade_hysteresis(["base"], "build", "green"), "base")
        self.assertEqual(
            apply_phase_upgrade_hysteresis(["base"], "build", "green", prior_upgrade_streak=1),
            "build",
        )
        self.assertEqual(apply_phase_upgrade_hysteresis(["base", "build"], "build", "green"), "build")
        self.assertEqual(
            apply_phase_upgrade_hysteresis(["build"], "return_to_training", "green"),
            "return_to_training",
        )

    def test_invalid_input_smoke_checks(self):
        with self.assertRaises(RuleEngineDateValidationError):
            validate_event_date([], date(2026, 3, 3))
        with self.assertRaises(RuleEngineIntentError):
            resolve_effective_performance_intent({}, {"performance_intent_this_week": "yes"})
        with self.assertRaises(RuleEngineRiskError):
            derive_risk([], {}, {})
        with self.assertRaises(RuleEnginePhaseError):
            derive_phase({}, {}, "2026-03-03", {}, risk_flag="green", effective_performance_intent=False)
        with self.assertRaises(RuleEngineTrackError):
            select_track({}, "", "green")
        with self.assertRaises(RuleEngineArchetypeError):
            select_quality_archetype([], "green", "medium")
        with self.assertRaises(RuleEngineSkeletonError):
            build_weekly_skeleton([], {}, "main_build", "build", "green", True, {})
        with self.assertRaises(RuleEngineStabilizationError):
            detect_inconsistent_training("base", "build", "green")
        with self.assertRaises(RuleEngineSwitchingError):
            should_switch_main_sport([], {}, {})


class TestRoutingAndPayload(unittest.TestCase):
    def test_route_today_action_pain_and_chaos(self):
        red_b = route_today_action(
            {"pain_score": 7, "days_available": 4},
            "red_b",
            "return_or_risk_managed",
            ["easy_aerobic", "strength"],
        )
        self.assertEqual(red_b["routing_context"]["winning_signal"], "pain")
        self.assertIn("consult_clinician", red_b["adjustments"])

        chaotic = route_today_action(
            {"week_chaotic": True, "days_available": 4, "energy_score": 9},
            "green",
            "main_build",
            ["easy_aerobic", "tempo", "strength"],
        )
        self.assertEqual(chaotic["today_action"], "prioritize_big_2_anchors")
        self.assertEqual(chaotic["routing_context"]["winning_signal"], "chaos")
        self.assertEqual(len(chaotic["routing_context"]["anchor_sessions"]), 2)

    def test_route_today_action_energy_and_missed(self):
        energy = route_today_action(
            {"energy_score": 3, "days_available": 4},
            "green",
            "main_build",
            ["easy_aerobic", "tempo", "strength"],
        )
        self.assertEqual(energy["routing_context"]["winning_signal"], "energy")
        self.assertEqual(energy["today_action"], "minimum_effective_dose_session")

        missed = route_today_action(
            {"energy_score": 8, "missed_sessions_count": 2, "days_available": 4},
            "green",
            "main_build",
            ["easy_aerobic", "tempo", "strength"],
        )
        self.assertEqual(missed["routing_context"]["winning_signal"], "missed_sessions")
        self.assertIn("no_make_up_intensity", missed["adjustments"])

    def test_build_decision_envelope_and_payload(self):
        routed_plan = route_today_action(
            {"week_chaotic": True, "days_available": 4},
            "yellow",
            "return_or_risk_managed",
            ["easy_aerobic", "strength"],
        )
        envelope = build_decision_envelope(
            {"main_sport_current": "run"},
            {"week_chaotic": True, "days_available": 4},
            "build",
            "yellow",
            "return_or_risk_managed",
            False,
            {},
            fallback_skeleton=["easy_aerobic", "strength"],
            adjustments=["reduce_intensity"] + routed_plan["adjustments"],
            plan_update_status="updated",
            today_action=routed_plan["today_action"],
            routing_context=routed_plan["routing_context"],
        )
        self.assertTrue(envelope["messaging_guardrails"]["suppress_peak_language"])
        self.assertIn("back_to_back_hard_days", envelope["weekly_targets"]["disallowed_patterns"])

        payload = compose_email_payload(
            {"main_sport_current": "run"},
            {"week_chaotic": True, "days_available": 4},
            {
                "weekly_skeleton": ["easy_aerobic", "strength"],
                "today_action": routed_plan["today_action"],
                "adjustments": ["reduce_intensity"] + routed_plan["adjustments"],
                "routing_context": routed_plan["routing_context"],
            },
            envelope,
        )
        self.assertEqual(payload["subject_hint"], "This week: protect the two anchors")
        self.assertTrue(any(item.startswith("Priority: ") for item in payload["sessions"]))


class TestPlannerContracts(unittest.TestCase):
    def test_build_planner_brief_contract(self):
        envelope = build_decision_envelope(
            {"main_sport_current": "run"},
            {"days_available": 4, "structure_preference": "flexibility"},
            "build",
            "yellow",
            "return_or_risk_managed",
            False,
            {},
            fallback_skeleton=["easy_aerobic", "strength"],
            adjustments=["reduce_intensity"],
            plan_update_status="updated",
            today_action="prioritize_big_2_anchors",
            routing_context={"winning_signal": "chaos"},
        )
        brief = build_planner_brief(
            {"structure_preference": "flexibility"},
            {"days_available": 4, "structure_preference": "flexibility"},
            envelope,
            {},
        )
        self.assertEqual(brief["risk_flag"], "yellow")
        self.assertEqual(brief["structure_preference"], "flexibility")
        self.assertIn("hard_limits", brief)
        self.assertIn("weekly_targets", brief)
        self.assertEqual(brief["fallback_skeleton"], ["easy_aerobic", "strength"])

    def test_validate_and_repair_planner_output(self):
        planner_brief = {
            "risk_flag": "yellow",
            "hard_limits": {"max_hard_sessions_per_week": 1, "max_sessions_per_week": 4},
            "disallowed_patterns": ["back_to_back_hard_days"],
            "max_sessions_per_week": 4,
            "structure_preference": "structure",
            "fallback_skeleton": ["easy_aerobic", "strength"],
        }
        invalid = {"weekly_skeleton": ["tempo", "intervals", "unknown_tag"]}
        validation = validate_planner_output(planner_brief, invalid)
        self.assertFalse(validation["is_valid"])
        repaired = repair_or_fallback_plan(validation, planner_brief)
        self.assertIn(repaired["source"], {"repaired_planner_plan", "deterministic_fallback"})
        self.assertTrue(all(token in HARD_SESSION_TAGS | NON_HARD_SESSION_TAGS for token in repaired["weekly_skeleton"]))
        self.assertLessEqual(
            sum(1 for token in repaired["weekly_skeleton"] if token in HARD_SESSION_TAGS),
            1,
        )
