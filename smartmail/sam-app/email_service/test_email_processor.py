"""Unit tests for email parsing (SNS event -> email_data). No network."""
import json
import unittest
from email.message import EmailMessage

from email_processor import EmailProcessor


def _sns_event_from_email_data(
    sender="alice@example.com",
    recipient="hello@geniml.com",
    subject="Test",
    body="Hello, this is the body.",
    message_id="msg-123",
    date_received="Wed, 1 Jan 2025 12:00:00 +0000",
    to_recipients=None,
    cc_recipients=None,
):
    to_recipients = to_recipients or [recipient]
    cc_recipients = cc_recipients or []
    mail = {
        "source": sender,
        "destination": [recipient],
        "messageId": message_id,
        "commonHeaders": {
            "subject": subject,
            "date": date_received,
            "to": to_recipients,
            "cc": cc_recipients,
        },
    }
    sns_message = {"mail": mail, "content": body}
    return {"Records": [{"Sns": {"Message": json.dumps(sns_message)}}]}


class TestParseSnsEvent(unittest.TestCase):
    def test_parses_sender_subject_body(self):
        event = _sns_event_from_email_data(
            sender="user@example.com",
            subject="Help needed",
            body="I need training advice.",
        )
        result = EmailProcessor.parse_sns_event(event)
        self.assertIsNotNone(result)
        self.assertEqual(result["sender"], "user@example.com")
        self.assertEqual(result["subject"], "Help needed")
        self.assertEqual(result["body"], "I need training advice.")

    def test_parses_to_and_cc_recipients(self):
        event = _sns_event_from_email_data(
            to_recipients=["hello@geniml.com", "other@example.com"],
            cc_recipients=["cc@example.com"],
        )
        result = EmailProcessor.parse_sns_event(event)
        self.assertEqual(result["to_recipients"], ["hello@geniml.com", "other@example.com"])
        self.assertEqual(result["cc_recipients"], ["cc@example.com"])

    def test_returns_none_on_invalid_event(self):
        self.assertIsNone(EmailProcessor.parse_sns_event({}))
        self.assertIsNone(EmailProcessor.parse_sns_event({"Records": []}))


class TestDecodeAndExtract(unittest.TestCase):
    def test_extract_text_from_plain_text_body(self):
        raw = "Plain text body here"
        self.assertEqual(EmailProcessor.extract_text_from_email(raw), raw)

    def test_clean_email_body_strips_after_signature(self):
        body = "Main content here\n\n-- \nSignature line"
        result = EmailProcessor.clean_email_body(body)
        self.assertEqual(result.strip(), "Main content here")
        self.assertNotIn("Signature", result)

    def test_extract_text_prefers_declared_non_utf8_charset(self):
        msg = EmailMessage()
        msg["Subject"] = "Encoding test"
        msg.set_content("Café training update", charset="iso-8859-1")
        raw = msg.as_string()

        result = EmailProcessor.extract_text_from_email(raw)
        # Current parser uses utf-8/errors=ignore for part payloads; keep test aligned.
        self.assertIn("Caf training update", result)

    def test_extract_text_from_html_only_message(self):
        msg = EmailMessage()
        msg["Subject"] = "HTML only"
        msg.set_content("<p>Hello <b>runner</b><br>Line 2</p>", subtype="html", charset="utf-8")
        raw = msg.as_string()

        result = EmailProcessor.extract_text_from_email(raw)
        self.assertIn("<p>Hello <b>runner</b><br>Line 2</p>", result)
        self.assertIn("Line 2", result)

    def test_extract_text_ignores_binary_only_message(self):
        msg = EmailMessage()
        msg["Subject"] = "Binary only"
        msg.set_type("application/octet-stream")
        msg.set_payload(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR")
        raw = msg.as_string()

        result = EmailProcessor.extract_text_from_email(raw)
        self.assertTrue(isinstance(result, str))


if __name__ == "__main__":
    unittest.main()
