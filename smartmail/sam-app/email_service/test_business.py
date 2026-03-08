"""Unit tests for business.get_reply_for_inbound (single entry point for reply logic)."""
from contextlib import ExitStack
import sys
import unittest
from unittest import mock

try:
    import business
except ModuleNotFoundError as e:
    if "boto" in str(e).lower() or "botocore" in str(e).lower():
        business = None  # type: ignore
    else:
        raise

try:
    import coaching
except ModuleNotFoundError as e:
    if "boto" in str(e).lower() or "botocore" in str(e).lower():
        coaching = None  # type: ignore
    else:
        raise


@unittest.skipIf(business is None, "boto3/botocore not installed; skip business tests")


class TestGetReplyForInbound(unittest.TestCase):
    def _profile_ready_patches(self):
        return (
            mock.patch.object(
                coaching,
                "get_coach_profile",
                return_value={
                    "primary_goal": "10k",
                    "time_availability": {"hours_per_week": 2.0},
                    "experience_level": "unknown",
                    "constraints": [],
                },
            ),
            mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}),
            mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None),
            mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True),
            mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}),
            mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True),
            mock.patch.object(coaching, "ensure_current_plan", return_value=True),
            mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."),
            mock.patch.object(coaching, "create_action_token", return_value=None),
        )

    def test_delegates_to_build_profile_gated_reply(self):
        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            return_value={
                "intent": "question",
                "complexity_score": 3,
                "model_name": "gpt-5-mini",
            },
        ) as analyze, mock.patch.object(
            business,
            "put_message_intelligence",
            return_value=True,
        ) as persist, mock.patch.object(
            business,
            "route_inbound_with_rule_engine",
            return_value={"intent": "question", "mode": "read_only"},
        ) as route_re, mock.patch.object(business, "build_profile_gated_reply") as build:
            build.return_value = "Ready for coaching!"
            email_data = {
                "sender": "u@example.com",
                "body": "Hello",
                "subject": "Hi",
                "message_id": "msg-1",
            }
            reply = business.get_reply_for_inbound("ath_1", "u@example.com", email_data)
            self.assertEqual(reply, "Ready for coaching!")
            build.assert_called_once()
            call_kw = build.call_args[1]
            self.assertEqual(call_kw["athlete_id"], "ath_1")
            self.assertEqual(call_kw["from_email"], "u@example.com")
            self.assertEqual(call_kw["inbound_body"], "Hello")
            self.assertEqual(call_kw["inbound_message_id"], "msg-1")
            self.assertEqual(call_kw["inbound_subject"], "Hi")
            self.assertEqual(call_kw["selected_model_name"], business.ADVANCED_RESPONSE_MODEL)
            self.assertEqual(call_kw["rule_engine_decision"], {"intent": "question", "mode": "read_only"})
            analyze.assert_called_once_with("Hello")
            route_re.assert_called_once()
            persist.assert_called_once_with(
                athlete_id="ath_1",
                message_id="msg-1",
                intent="question",
                complexity_score=3,
                model_name="gpt-5-mini",
                routing_decision="advanced",
                selected_model=business.ADVANCED_RESPONSE_MODEL,
            )

    def test_passes_log_outcome_and_aws_request_id(self):
        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            return_value={
                "intent": "question",
                "complexity_score": 2,
                "model_name": "gpt-5-mini",
            },
        ), mock.patch.object(
            business,
            "put_message_intelligence",
            return_value=True,
        ) as persist, mock.patch.object(
            business,
            "route_inbound_with_rule_engine",
            return_value={"intent": "question", "mode": "read_only"},
        ), mock.patch.object(business, "build_profile_gated_reply") as build:
            build.return_value = "Ok"
            email_data = {"body": "Hi"}
            log_outcome = lambda **kw: None
            business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                email_data,
                aws_request_id="req-123",
                log_outcome=log_outcome,
            )
            persist.assert_called_once_with(
                athlete_id="ath_1",
                message_id=mock.ANY,
                intent="question",
                complexity_score=2,
                model_name="gpt-5-mini",
                routing_decision="lightweight",
                selected_model=business.LIGHTWEIGHT_RESPONSE_MODEL,
            )
            build.assert_called_once_with(
                athlete_id="ath_1",
                from_email="u@example.com",
                inbound_body="Hi",
                inbound_message_id=None,
                inbound_subject="",
                selected_model_name=business.LIGHTWEIGHT_RESPONSE_MODEL,
                rule_engine_decision={"intent": "question", "mode": "read_only"},
                aws_request_id="req-123",
                log_outcome=log_outcome,
            )

    def test_returns_fallback_when_intelligence_fails(self):
        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            side_effect=business.ConversationIntelligenceError("llm_intelligence_failed"),
        ), mock.patch.object(
            business,
            "put_message_intelligence",
        ) as persist, mock.patch.object(business, "build_profile_gated_reply") as build:
            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hi"},
            )
            self.assertEqual(reply, business.EmailCopy.FALLBACK_AI_ERROR_REPLY)
            persist.assert_not_called()
            build.assert_not_called()

    def test_returns_fallback_when_intelligence_cannot_be_stored(self):
        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            return_value={
                "intent": "question",
                "complexity_score": 2,
                "model_name": "gpt-5-mini",
            },
        ), mock.patch.object(
            business,
            "put_message_intelligence",
            return_value=False,
        ) as persist, mock.patch.object(business, "build_profile_gated_reply") as build:
            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hi"},
            )
            self.assertEqual(reply, business.EmailCopy.FALLBACK_AI_ERROR_REPLY)
            persist.assert_called_once()
            build.assert_not_called()

    def test_persists_intelligence_before_rule_engine_router(self):
        call_order = []

        def _persist(*args, **kwargs):
            call_order.append("persist")
            return True

        def _route(*args, **kwargs):
            call_order.append("router")
            return {"intent": "question", "mode": "read_only"}

        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            return_value={
                "intent": "question",
                "complexity_score": 2,
                "model_name": "gpt-5-mini",
            },
        ), mock.patch.object(
            business,
            "put_message_intelligence",
            side_effect=_persist,
        ), mock.patch.object(
            business,
            "route_inbound_with_rule_engine",
            side_effect=_route,
        ), mock.patch.object(
            business,
            "build_profile_gated_reply",
            return_value="Ok",
        ):
            business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hi"},
            )

        self.assertEqual(call_order, ["persist", "router"])

    def test_rule_engine_guided_reply_keeps_selected_model_but_uses_deterministic_reply_path(self):
        guided_decision = {
            "intent": "check_in",
            "mode": "mutate",
            "reply_strategy": "rule_engine_guided",
            "engine_output": {
                "track": "main_build",
                "risk_flag": "green",
                "plan_update_status": "updated",
                "next_email_payload": {
                    "subject_hint": "This week: execute with control",
                    "summary": "Training can continue.",
                    "sessions": ["session_1: easy_aerobic"],
                    "plan_focus_line": "Hit the key sessions without forcing extra load.",
                    "technique_cue": "Keep effort smooth, relaxed, and technically tidy.",
                    "recovery_target": "Support the work with steady sleep and simple recovery habits.",
                    "if_then_rules": ["Do not make up missed intensity later in the week."],
                    "disclaimer_short": "",
                    "safety_note": "No hard sessions when risk is red-tier.",
                },
            },
        }
        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            return_value={
                "intent": "check_in",
                "complexity_score": 2,
                "model_name": "gpt-5-mini",
            },
        ), mock.patch.object(
            business,
            "put_message_intelligence",
            return_value=True,
        ), mock.patch.object(
            business,
            "route_inbound_with_rule_engine",
            return_value=guided_decision,
        ), mock.patch.object(business, "build_profile_gated_reply") as build:
            build.return_value = "deterministic guided reply"
            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hello", "subject": "Hi"},
            )

        self.assertEqual(reply, "deterministic guided reply")
        build.assert_called_once()
        self.assertEqual(build.call_args.kwargs["selected_model_name"], business.LIGHTWEIGHT_RESPONSE_MODEL)
        self.assertEqual(build.call_args.kwargs["rule_engine_decision"], guided_decision)

    @unittest.skipIf(coaching is None, "coaching module unavailable")
    def test_rule_engine_guided_reply_renders_payload_through_business(self):
        guided_decision = {
            "intent": "check_in",
            "mode": "mutate",
            "reply_strategy": "rule_engine_guided",
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
                    "sessions": ["Priority: long easy aerobic session", "Priority: strength session"],
                    "plan_focus_line": "Use safety and consistency as the primary filter.",
                    "technique_cue": "Keep cadence light and posture tall.",
                    "recovery_target": "Prioritize recovery basics before adding any load.",
                    "if_then_rules": ["If symptoms rise, remove intensity immediately."],
                    "disclaimer_short": "",
                    "safety_note": "No hard sessions when risk is red-tier.",
                },
            },
        }
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    business,
                    "analyze_conversation_intelligence",
                    return_value={"intent": "check_in", "complexity_score": 2, "model_name": "gpt-5-mini"},
                )
            )
            stack.enter_context(
                mock.patch.object(
                    business,
                    "put_message_intelligence",
                    return_value=True,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    business,
                    "route_inbound_with_rule_engine",
                    return_value=guided_decision,
                )
            )
            responder = stack.enter_context(mock.patch.object(coaching, "OpenAIResponder"))
            for patcher in self._profile_ready_patches():
                stack.enter_context(patcher)

            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hello", "subject": "Hi", "message_id": "msg-1"},
            )

        self.assertIn("This week: stay safe and keep it steady", reply)
        self.assertIn("Current plan - Goal: 10k.", reply)
        self.assertIn("Priority: long easy aerobic session", reply)
        responder.generate_response.assert_not_called()

    @unittest.skipIf(coaching is None, "coaching module unavailable")
    def test_red_b_guided_reply_includes_disclaimer_and_clinician_guidance_through_business(self):
        guided_decision = {
            "intent": "check_in",
            "mode": "mutate",
            "reply_strategy": "rule_engine_guided",
            "engine_output": {
                "classification_label": "deterministic_re3_transition",
                "track": "return_or_risk_managed",
                "phase": "build",
                "risk_flag": "red_b",
                "weekly_skeleton": ["easy_aerobic"],
                "today_action": "stop_training_intensity_low_impact_only_if_pain_free",
                "plan_update_status": "updated",
                "adjustments": ["consult_clinician"],
                "next_email_payload": {
                    "subject_hint": "This week: stop intensity and get assessed",
                    "summary": "Pain is the highest-priority signal. Stop training intensity and get clinical input.",
                    "sessions": ["Optional short mobility/recovery touch only."],
                    "plan_focus_line": "Protect health first. Training progression is paused.",
                    "technique_cue": "Keep cadence light and posture tall.",
                    "recovery_target": "Rest, reduce load, and seek clinical guidance before resuming training.",
                    "if_then_rules": ["If symptoms persist or worsen, contact a clinician/physio immediately."],
                    "disclaimer_short": "Please stop training and consult a clinician/physio.",
                    "safety_note": "Please stop training and consult a clinician/physio.",
                },
            },
        }
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    business,
                    "analyze_conversation_intelligence",
                    return_value={"intent": "check_in", "complexity_score": 2, "model_name": "gpt-5-mini"},
                )
            )
            stack.enter_context(
                mock.patch.object(
                    business,
                    "put_message_intelligence",
                    return_value=True,
                )
            )
            stack.enter_context(
                mock.patch.object(
                    business,
                    "route_inbound_with_rule_engine",
                    return_value=guided_decision,
                )
            )
            responder = stack.enter_context(mock.patch.object(coaching, "OpenAIResponder"))
            for patcher in self._profile_ready_patches():
                stack.enter_context(patcher)

            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Sharp knee pain today", "subject": "Help", "message_id": "msg-2"},
            )

        self.assertIn("This week: stop intensity and get assessed", reply)
        self.assertIn("Please stop training and consult a clinician/physio.", reply)
        self.assertIn("Current plan - Goal: 10k.", reply)
        responder.generate_response.assert_not_called()


if __name__ == "__main__":
    unittest.main()
