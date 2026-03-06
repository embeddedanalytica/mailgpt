"""Unit tests for business.get_reply_for_inbound (single entry point for reply logic)."""
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


@unittest.skipIf(business is None, "boto3/botocore not installed; skip business tests")


class TestGetReplyForInbound(unittest.TestCase):
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


if __name__ == "__main__":
    unittest.main()
