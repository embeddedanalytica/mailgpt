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
        with mock.patch.object(business, "build_profile_gated_reply") as build:
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

    def test_passes_log_outcome_and_aws_request_id(self):
        with mock.patch.object(business, "build_profile_gated_reply") as build:
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
            build.assert_called_once_with(
                athlete_id="ath_1",
                from_email="u@example.com",
                inbound_body="Hi",
                inbound_message_id=None,
                aws_request_id="req-123",
                log_outcome=log_outcome,
            )


if __name__ == "__main__":
    unittest.main()
