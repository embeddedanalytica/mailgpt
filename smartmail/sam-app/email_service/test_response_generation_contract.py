import unittest

from response_generation_contract import (
    FinalEmailResponse,
    ResponseBrief,
    ResponseGenerationContractError,
    normalize_reply_mode,
    validate_final_email_response,
    validate_response_brief,
)


def _continuity_summary() -> dict:
    return {
        "summary": "Athlete is rebuilding consistency.",
        "last_recommendation": "Keep one controlled quality session this week.",
        "open_loops": ["How did the quality session feel?"],
        "updated_at": 1773273600,
    }


def _context_note(label: str = "Schedule", summary: str = "Weekday sessions need to finish before 7am") -> dict:
    return {"label": label, "summary": summary, "updated_at": 1773273600}


def _valid_brief(reply_mode: str = "normal_coaching") -> dict:
    return {
        "reply_mode": reply_mode,
        "athlete_context": {
            "goal_summary": "10k race in 8 weeks",
            "experience_level": "intermediate",
            "structure_preference": "flexibility",
        },
        "decision_context": {
            "track": "main_build",
            "phase": "build",
            "risk_flag": "yellow",
            "today_action": "do planned but conservative",
            "clarification_needed": False,
        },
        "validated_plan": {
            "weekly_skeleton": ["easy_aerobic", "strength", "tempo"],
            "planner_rationale": "Protect consistency while keeping one quality stimulus.",
            "plan_summary": "Current plan: rebuild consistency while protecting recovery.",
        },
        "delivery_context": {
            "inbound_subject": "Weekly check-in",
            "selected_model_name": "gpt-5-mini",
            "response_channel": "email",
        },
        "memory_context": {
            "memory_available": True,
            "backbone_summaries": {"hard_constraints": "Weekday sessions need to finish before 7am"},
            "context_notes": [_context_note()],
            "continuity_summary": _continuity_summary(),
            "continuity_focus": "Athlete is rebuilding consistency.",
        },
    }


def _valid_final_email_response() -> dict:
    return {
        "final_email_body": (
            "You can still move the week forward, but keep this one controlled.\n\n"
            "I want one purposeful session only if your legs feel steady, with easy aerobic work around it."
        ),
    }


class TestNormalizeReplyMode(unittest.TestCase):
    def test_maps_current_reply_kinds_to_canonical_modes(self):
        self.assertEqual(normalize_reply_mode("profile_incomplete"), "clarification")
        self.assertEqual(normalize_reply_mode("rule_engine_guided"), "normal_coaching")
        self.assertEqual(normalize_reply_mode("coaching_reply"), "normal_coaching")
        self.assertEqual(normalize_reply_mode("safety_concern"), "safety_risk_managed")
        self.assertEqual(normalize_reply_mode("off_topic"), "off_topic_redirect")

    def test_rejects_unknown_reply_mode(self):
        with self.assertRaises(ResponseGenerationContractError):
            normalize_reply_mode("standard")


class TestValidateResponseBrief(unittest.TestCase):
    def test_accepts_minimal_normal_coaching_brief(self):
        payload = _valid_brief()
        payload["athlete_context"] = {}
        payload["decision_context"] = {}
        payload["validated_plan"] = {}
        payload["delivery_context"] = {}
        payload["memory_context"] = {
            "memory_available": False,
            "continuity_summary": None,
        }

        validate_response_brief(payload)

    def test_accepts_clarification_brief(self):
        payload = _valid_brief("clarification")
        validate_response_brief(payload)

    def test_accepts_safety_risk_managed_brief(self):
        payload = _valid_brief("safety_risk_managed")
        validate_response_brief(payload)

    def test_accepts_off_topic_redirect_brief(self):
        payload = _valid_brief("off_topic_redirect")
        validate_response_brief(payload)

    def test_accepts_lightweight_non_planning_brief(self):
        payload = _valid_brief("lightweight_non_planning")
        validate_response_brief(payload)

    def test_round_trips_response_brief(self):
        payload = _valid_brief("profile_incomplete")

        rebuilt = ResponseBrief.from_dict(payload)

        self.assertEqual(rebuilt.reply_mode, "clarification")
        self.assertEqual(rebuilt.to_dict()["delivery_context"]["response_channel"], "email")

    def test_missing_reply_mode_is_rejected(self):
        payload = _valid_brief()
        del payload["reply_mode"]

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_unknown_top_level_field_is_rejected(self):
        payload = _valid_brief()
        payload["rule_engine_decision"] = {"reply_strategy": "rule_engine_guided"}

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_unknown_nested_athlete_context_field_is_rejected(self):
        payload = _valid_brief()
        payload["athlete_context"]["profile_blob"] = {"primary_goal": "10k"}

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_unknown_nested_decision_context_field_is_rejected(self):
        payload = _valid_brief()
        payload["decision_context"]["reply_strategy"] = "rule_engine_guided"

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_unknown_nested_validated_plan_field_is_rejected(self):
        payload = _valid_brief()
        payload["validated_plan"]["raw_rule_state"] = {"phase_history": ["base"]}

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_unknown_nested_delivery_context_field_is_rejected(self):
        payload = _valid_brief()
        payload["delivery_context"]["prompt_text"] = "raw prompt"

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_unknown_nested_memory_context_field_is_rejected(self):
        payload = _valid_brief()
        payload["memory_context"]["router_debug"] = {"route": "both"}

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_rejects_non_string_continuity_focus(self):
        payload = _valid_brief()
        payload["memory_context"]["continuity_focus"] = 123

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_rejects_non_dict_backbone_summaries(self):
        payload = _valid_brief()
        payload["memory_context"]["backbone_summaries"] = "not a dict"

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_rejects_empty_string_backbone_summary_value(self):
        payload = _valid_brief()
        payload["memory_context"]["backbone_summaries"] = {"primary_goal": "  "}

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_wrong_scalar_type_is_rejected(self):
        payload = _valid_brief()
        payload["decision_context"]["clarification_needed"] = "false"

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_weekly_skeleton_requires_strings(self):
        payload = _valid_brief()
        payload["validated_plan"]["weekly_skeleton"] = ["easy_aerobic", 3]

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_rejects_malformed_context_notes(self):
        payload = _valid_brief()
        payload["memory_context"]["context_notes"] = [{"summary": "Missing label"}]

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_memory_available_true_rejects_malformed_continuity_summary(self):
        payload = _valid_brief()
        payload["memory_context"]["continuity_summary"] = {"summary": "missing fields"}

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_memory_available_false_rejects_present_artifacts(self):
        payload = _valid_brief()
        payload["memory_context"]["memory_available"] = False

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_missing_memory_context_required_field_is_rejected(self):
        payload = _valid_brief()
        del payload["memory_context"]["continuity_summary"]

        with self.assertRaises(ResponseGenerationContractError):
            validate_response_brief(payload)

    def test_delivery_context_defaults_response_channel_to_email(self):
        payload = _valid_brief()
        del payload["delivery_context"]["response_channel"]

        brief = ResponseBrief.from_dict(payload)

        self.assertEqual(brief.delivery_context["response_channel"], "email")


class TestValidateFinalEmailResponse(unittest.TestCase):
    def test_accepts_valid_payload(self):
        validate_final_email_response(_valid_final_email_response())

    def test_round_trips_response_payload(self):
        rebuilt = FinalEmailResponse.from_dict(_valid_final_email_response())

        self.assertEqual(rebuilt.to_dict(), _valid_final_email_response())

    def test_rejects_missing_required_field(self):
        payload = _valid_final_email_response()
        del payload["final_email_body"]

        with self.assertRaises(ResponseGenerationContractError):
            validate_final_email_response(payload)

    def test_rejects_unknown_field(self):
        payload = _valid_final_email_response()
        payload["summary"] = "legacy field"

        with self.assertRaises(ResponseGenerationContractError):
            validate_final_email_response(payload)

    def test_rejects_non_dict_payload(self):
        with self.assertRaises(ResponseGenerationContractError):
            validate_final_email_response(["not", "a", "dict"])

    def test_rejects_empty_required_string(self):
        payload = _valid_final_email_response()
        payload["final_email_body"] = "   "

        with self.assertRaises(ResponseGenerationContractError):
            validate_final_email_response(payload)

    def test_rejects_non_string_model_name(self):
        payload = _valid_final_email_response()
        payload["model_name"] = None

        with self.assertRaises(ResponseGenerationContractError):
            validate_final_email_response(payload)

    def test_accepts_optional_model_name(self):
        payload = _valid_final_email_response()
        payload["model_name"] = "gpt-5-nano"

        rebuilt = FinalEmailResponse.from_dict(payload)

        self.assertEqual(rebuilt.to_dict()["model_name"], "gpt-5-nano")


if __name__ == "__main__":
    unittest.main()
