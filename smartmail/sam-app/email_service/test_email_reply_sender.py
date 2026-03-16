"""Unit tests for email reply sending/formatting behavior."""
import sys
import types
import unittest
from unittest import mock

# Make tests runnable when boto3 is unavailable locally.
if "boto3" not in sys.modules:
    boto3_module = types.ModuleType("boto3")

    class _Boto3ClientStub:
        def send_raw_email(self, *args, **kwargs):
            return {"MessageId": "stub-message-id"}

    class _Boto3ResourceStub:
        def Table(self, _name):  # noqa: N802
            return object()

    def _client(*args, **kwargs):
        return _Boto3ClientStub()

    def _resource(*args, **kwargs):
        return _Boto3ResourceStub()

    boto3_module.client = _client
    boto3_module.resource = _resource
    sys.modules["boto3"] = boto3_module

if "openai" not in sys.modules:
    openai_module = types.ModuleType("openai")
    openai_module.api_key = None
    sys.modules["openai"] = openai_module

import email_reply_sender
from email_copy import EmailCopy
from email_reply_sender import EmailReplySender


class EmailReplySenderTests(unittest.TestCase):
    def setUp(self):
        self.email_data = {
            "sender": "user@example.com",
            "subject": "Training question",
            "body": "Original inbound body",
            "message_id": "<msg-123@example.com>",
            "date_received": "Wed, 1 Jan 2025 12:00:00 +0000",
            "to_recipients": ["hello@geniml.com"],
            "cc_recipients": [],
        }

    def test_format_reply_new_thread_skips_wrapped_history(self):
        html = EmailReplySender.format_reply(
            self.email_data,
            "Thanks for reaching out.",
            include_thread_context=False,
        )
        self.assertIn("Thanks for reaching out.", html)
        self.assertNotIn(EmailCopy.REPLY_WRAPPER_SEPARATOR, html)
        self.assertNotIn("Original inbound body", html)

    def test_format_reply_thread_context_keeps_wrapped_history(self):
        html = EmailReplySender.format_reply(
            self.email_data,
            "Reply body.",
            include_thread_context=True,
        )
        self.assertIn(EmailCopy.REPLY_WRAPPER_SEPARATOR, html)
        self.assertIn("Original inbound body", html)

    def test_format_reply_strips_control_characters(self):
        noisy_reply = "Hi\x00 there\x07"
        noisy_data = dict(self.email_data, body="Bod\x01y")
        html = EmailReplySender.format_reply(
            noisy_data,
            noisy_reply,
            include_thread_context=True,
        )
        self.assertNotIn("\x00", html)
        self.assertNotIn("\x07", html)
        self.assertNotIn("\x01", html)
        self.assertIn("Hi there", html)
        self.assertIn("Body", html)

    def test_send_reply_new_thread_omits_thread_headers(self):
        with mock.patch.object(email_reply_sender, "ses_client") as ses_client_mock:
            ses_client_mock.send_raw_email.return_value = {"MessageId": "m-1"}
            message_id = EmailReplySender.send_reply(self.email_data, "Hello")

        self.assertEqual(message_id, "m-1")
        raw_data = ses_client_mock.send_raw_email.call_args.kwargs["RawMessage"]["Data"]
        self.assertNotIn("In-Reply-To:", raw_data)
        self.assertNotIn("References:", raw_data)

    def test_send_reply_existing_thread_sets_thread_headers(self):
        existing_thread_email = dict(self.email_data, in_reply_to="<prior@example.com>")
        with mock.patch.object(email_reply_sender, "ses_client") as ses_client_mock:
            ses_client_mock.send_raw_email.return_value = {"MessageId": "m-2"}
            message_id = EmailReplySender.send_reply(existing_thread_email, "Hello again")

        self.assertEqual(message_id, "m-2")
        raw_data = ses_client_mock.send_raw_email.call_args.kwargs["RawMessage"]["Data"]
        self.assertIn("In-Reply-To: <msg-123@example.com>", raw_data)
        self.assertIn("References: <msg-123@example.com>", raw_data)

    def test_send_reply_can_force_skip_thread_context(self):
        existing_thread_email = dict(self.email_data, in_reply_to="<prior@example.com>")
        with mock.patch.object(email_reply_sender, "ses_client") as ses_client_mock:
            ses_client_mock.send_raw_email.return_value = {"MessageId": "m-3"}
            message_id = EmailReplySender.send_reply(
                existing_thread_email,
                "Canned response",
                include_thread_context=False,
            )

        self.assertEqual(message_id, "m-3")
        raw_data = ses_client_mock.send_raw_email.call_args.kwargs["RawMessage"]["Data"]
        self.assertNotIn("In-Reply-To:", raw_data)
        self.assertNotIn("References:", raw_data)
        self.assertNotIn(EmailCopy.REPLY_WRAPPER_SEPARATOR, raw_data)

    def test_format_reply_empty_content_raises(self):
        with self.assertRaises(ValueError):
            EmailReplySender.format_reply(
                self.email_data,
                None,
                include_thread_context=False,
            )


if __name__ == "__main__":
    unittest.main()
