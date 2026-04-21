"""Unit tests for business.get_reply_for_inbound (single entry point for reply logic)."""
from contextlib import ExitStack
from datetime import date
import sys
import unittest
from unittest import mock

from sectioned_memory_contract import empty_sectioned_memory

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
    def setUp(self):
        patcher = mock.patch.object(
            coaching, "run_coaching_reasoning_workflow",
            return_value={
                "directive": {
                    "reply_action": "send",
                    "opening": "Test opening",
                    "main_message": "Test message",
                    "content_plan": ["present the plan"],
                    "avoid": [],
                    "tone": "calm and direct",
                    "recommend_material": None,
                },
                "doctrine_files_loaded": [],
                "continuity_recommendation": {
                    "recommended_goal_horizon_type": "general_fitness",
                    "recommended_phase": "base",
                    "recommended_block_focus": "controlled_load_progression",
                    "recommended_transition_action": "keep",
                    "recommended_transition_reason": "stable training",
                    "recommended_goal_event_date": None,
                },
            },
        )
        self._mock_coaching_reasoning = patcher.start()
        self.addCleanup(patcher.stop)

    def _profile_ready_patches(self):
        return (
            mock.patch.object(
                coaching,
                "get_coach_profile",
                return_value={
                    "primary_goal": "10k",
                    "time_availability": {"availability_notes": "About 2 hours per week"},
                    "experience_level": "unknown",
                    "injury_status": {"has_injuries": False},
                },
            ),
            mock.patch.object(coaching, "parse_profile_updates_from_email", return_value={}),
            mock.patch.object(coaching, "parse_manual_activity_snapshot_from_email", return_value=None),
            mock.patch.object(coaching, "put_manual_activity_snapshot", return_value=True),
            mock.patch.object(coaching, "get_progress_snapshot", return_value={"data_quality": "low"}),
            mock.patch.object(coaching, "merge_coach_profile_fields", return_value=True),
            mock.patch.object(coaching, "ensure_current_plan", return_value=True),
            mock.patch.object(coaching, "fetch_current_plan_summary", return_value="Current plan - Goal: 10k."),
            mock.patch.object(coaching, "get_current_plan", return_value=None),
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
                metadata=mock.ANY,
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
                metadata=mock.ANY,
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

    def test_passes_effective_today_when_provided(self):
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
        ), mock.patch.object(
            business,
            "route_inbound_with_rule_engine",
            return_value={"intent": "question", "mode": "read_only"},
        ), mock.patch.object(business, "build_profile_gated_reply") as build:
            build.return_value = "Ok"
            effective_today = date(2026, 1, 15)

            business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hi"},
                effective_today=effective_today,
            )

            self.assertEqual(
                build.call_args.kwargs["effective_today"],
                effective_today,
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
            self.assertIsNone(reply)
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
            self.assertIsNone(reply)
            persist.assert_called_once()
            build.assert_not_called()

    def test_propagates_suppressed_reply_sentinel(self):
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
        ), mock.patch.object(
            business,
            "route_inbound_with_rule_engine",
            return_value={"intent": "question", "mode": "read_only"},
        ), mock.patch.object(
            business,
            "build_profile_gated_reply",
            return_value=business.SUPPRESSED_REPLY,
        ):
            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "No need to reply unless needed"},
            )

        self.assertIs(reply, business.SUPPRESSED_REPLY)

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

    def test_coaching_reply_keeps_selected_model_without_rule_engine_payload(self):
        guided_decision = {
            "intent": "coaching",
            "mode": "mutate",
        }
        with mock.patch.object(
            business,
            "analyze_conversation_intelligence",
            return_value={
                "intent": "coaching",
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
    def test_business_no_longer_threads_rule_engine_payload_into_response_generation(self):
        guided_decision = {
            "intent": "coaching",
            "mode": "mutate",
        }
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    business,
                    "analyze_conversation_intelligence",
                    return_value={"intent": "coaching", "complexity_score": 2, "model_name": "gpt-5-mini"},
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
            stack.enter_context(
                mock.patch.object(
                    coaching,
                    "get_memory_context_for_response_generation",
                    return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None},
                )
            )
            stack.enter_context(mock.patch.object(coaching, "maybe_post_reply_memory_refresh"))
            runner = stack.enter_context(mock.patch.object(coaching, "run_response_generation_workflow"))
            for patcher in self._profile_ready_patches():
                stack.enter_context(patcher)
            runner.return_value = {"final_email_body": "Composed guided reply."}

            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Hello", "subject": "Hi", "message_id": "msg-1"},
            )

        self.assertEqual(reply, "Composed guided reply.")
        runner.assert_called_once()
        brief = runner.call_args.args[0]
        self.assertEqual(brief["reply_mode"], "normal_coaching")
        response_brief = self._mock_coaching_reasoning.call_args.args[0]
        self.assertNotIn("track", response_brief["decision_context"])
        self.assertEqual(brief["plan_data"], {"plan_summary": "Current plan - Goal: 10k."})

    @unittest.skipIf(coaching is None, "coaching module unavailable")
    def test_safety_intent_routes_without_rule_engine_guided_payload(self):
        guided_decision = {
            "intent": "safety_concern",
            "mode": "skip",
        }
        with ExitStack() as stack:
            stack.enter_context(
                mock.patch.object(
                    business,
                    "analyze_conversation_intelligence",
                    return_value={"intent": "coaching", "complexity_score": 2, "model_name": "gpt-5-mini"},
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
            stack.enter_context(
                mock.patch.object(
                    coaching,
                    "get_memory_context_for_response_generation",
                    return_value={"sectioned_memory": empty_sectioned_memory(), "continuity_summary": None},
                )
            )
            stack.enter_context(mock.patch.object(coaching, "maybe_post_reply_memory_refresh"))
            runner = stack.enter_context(mock.patch.object(coaching, "run_response_generation_workflow"))
            for patcher in self._profile_ready_patches():
                stack.enter_context(patcher)
            runner.return_value = {"final_email_body": "Safety-composed guided reply."}

            reply = business.get_reply_for_inbound(
                "ath_1",
                "u@example.com",
                {"body": "Sharp knee pain today", "subject": "Help", "message_id": "msg-2"},
            )

        self.assertEqual(reply, "Safety-composed guided reply.")
        runner.assert_called_once()
        brief = runner.call_args.args[0]
        self.assertEqual(brief["reply_mode"], "safety_risk_managed")
        self.assertEqual(brief["plan_data"], {"plan_summary": "Current plan - Goal: 10k."})


if __name__ == "__main__":
    unittest.main()
