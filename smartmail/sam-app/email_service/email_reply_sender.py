"""
Sending replies via SES: format as HTML and send.
Depends on business/LLM only for the reply content; no auth or rate-limit logic here.
"""
import logging
import re
from html import escape
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto3  # type: ignore

from config import AWS_REGION
from email_copy import EmailCopy
logger = logging.getLogger(__name__)
ses_client = boto3.client("ses", region_name=AWS_REGION)
_CONTROL_CHARS_RE = re.compile(r"[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]")


class EmailReplySender:
    """Handles formatting and sending replies via AWS SES."""

    @staticmethod
    def _clean_text(value):
        """Removes non-printable control chars and escapes HTML."""
        text = _CONTROL_CHARS_RE.sub("", str(value or ""))
        return escape(text)

    @staticmethod
    def _is_existing_thread(email_data):
        """True when inbound mail indicates this is part of an existing thread."""
        subject = str(email_data.get("subject", "")).strip().lower()
        in_reply_to = email_data.get("in_reply_to")
        references = email_data.get("references")
        return bool(in_reply_to or references or subject.startswith("re:"))

    @staticmethod
    def filter_valid_recipients(recipients):
        """Filters out SES system-generated emails from recipient list."""
        invalid_domains = ["amazonses.com", "amazonaws.com", "geniml.com"]
        return [e for e in recipients if not any(d in e for d in invalid_domains)]

    @staticmethod
    def get_geniml_email(recipients):
        """Finds the first geniml.com email in recipients; defaults to hello@geniml.com if not found."""
        for e in recipients:
            if e.endswith("@geniml.com"):
                return e
        return "hello@geniml.com"

    @staticmethod
    def send_reply(email_data, reply_content, include_thread_context=None):
        """Sends a reply email using AWS SES."""
        try:
            should_include_thread_context = (
                EmailReplySender._is_existing_thread(email_data)
                if include_thread_context is None
                else bool(include_thread_context)
            )
            formatted_reply = EmailReplySender.format_reply(
                email_data,
                reply_content,
                include_thread_context=should_include_thread_context,
            )

            from_ai_address = EmailReplySender.get_geniml_email(
                email_data["to_recipients"] + email_data["cc_recipients"]
            )
            to_recipients = EmailReplySender.filter_valid_recipients(email_data["to_recipients"])
            cc_recipients = EmailReplySender.filter_valid_recipients(email_data["cc_recipients"])
            if email_data["sender"] not in to_recipients:
                to_recipients.append(email_data["sender"])

            subject = email_data["subject"]
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = from_ai_address
            msg["To"] = ", ".join(to_recipients)
            msg["Cc"] = ", ".join(cc_recipients)
            msg["Reply-To"] = from_ai_address
            if should_include_thread_context:
                message_id = str(email_data.get("message_id", "")).strip()
                if message_id:
                    msg["In-Reply-To"] = message_id
                    msg["References"] = message_id
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg["Message-ID"] = email.utils.make_msgid(domain=from_ai_address.split("@")[-1])
            msg.attach(MIMEText(formatted_reply, "html", "utf-8"))

            all_recipients = list(set(to_recipients + cc_recipients))
            if not all_recipients:
                logger.error("No valid recipients found. Aborting email send.")
                return None

            response = ses_client.send_raw_email(
                Source=from_ai_address,
                Destinations=to_recipients + cc_recipients,
                RawMessage={"Data": msg.as_string()},
            )
            logger.info("From: %s, To: %s, CC: %s", from_ai_address, to_recipients, cc_recipients)
            logger.info("Reply sent successfully! Message ID: %s", response["MessageId"])
            return response["MessageId"]
        except Exception as e:
            logger.error("Error sending reply: %s", e)
            return None

    @staticmethod
    def format_reply(email_data, reply_content, include_thread_context=True):
        """Formats the reply email with original message context (HTML).
        reply_content may be a string (escaped and newlines→br) or a dict with
        'html' (used as-is) and optionally 'text' (fallback)."""
        if isinstance(reply_content, dict) and reply_content.get("html") is not None:
            safe_reply_content = reply_content["html"]
        else:
            text = reply_content.get("text", reply_content) if isinstance(reply_content, dict) else reply_content
            safe_reply_content = EmailReplySender._clean_text(text).replace(chr(10), "<br>")
            if not safe_reply_content.strip():
                raise ValueError("reply_content must be non-empty")
        if not include_thread_context:
            return f"<html><body>{safe_reply_content}</body></html>"

        safe_sender = EmailReplySender._clean_text(email_data.get("sender", ""))
        safe_date_received = EmailReplySender._clean_text(email_data.get("date_received", ""))
        safe_subject = EmailReplySender._clean_text(email_data.get("subject", ""))
        safe_body = EmailReplySender._clean_text(email_data.get("body", "")).replace(chr(10), "<br>")
        safe_to = ", ".join(
            EmailReplySender._clean_text(recipient)
            for recipient in email_data.get("to_recipients", [])
        )
        safe_cc = ", ".join(
            EmailReplySender._clean_text(recipient)
            for recipient in email_data.get("cc_recipients", [])
        )
        cc_text = (
            f"{EmailCopy.REPLY_WRAPPER_CC}: {safe_cc}<br>"
            if email_data.get("cc_recipients")
            else ""
        )
        return (
            f"<html><body>"
            f"{safe_reply_content}<br>"
            f"{EmailCopy.REPLY_WRAPPER_SEPARATOR}<br>"
            f"{EmailCopy.REPLY_WRAPPER_FROM}: {safe_sender}<br>"
            f"{EmailCopy.REPLY_WRAPPER_SENT}: {safe_date_received}<br>"
            f"{EmailCopy.REPLY_WRAPPER_TO}: {safe_to}<br>"
            f"{cc_text}"
            f"{EmailCopy.REPLY_WRAPPER_SUBJECT}: {safe_subject}<br><br>"
            f"{safe_body}"
            f"</body></html>"
        )
