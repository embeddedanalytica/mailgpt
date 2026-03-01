"""
Parsing of inbound emails from SNS: decode content, extract body, build email_data dict.
No auth, no LLM—pure parsing.
"""
import json
import base64
import logging
from email import message_from_string

logger = logging.getLogger(__name__)


class EmailProcessor:
    """Handles parsing of received emails from SNS and preparing reply context."""

    @staticmethod
    def parse_sns_event(event):
        """Extracts sender, subject, recipients (To & CC), and decoded email body from SNS event."""
        try:
            sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
            sender_email = sns_message["mail"]["source"]
            recipient_email = sns_message["mail"]["destination"][0]
            subject = sns_message["mail"]["commonHeaders"]["subject"]
            message_id = sns_message["mail"]["messageId"]
            date_received = sns_message["mail"]["commonHeaders"]["date"]
            to_recipients = sns_message["mail"]["commonHeaders"].get("to", [])
            cc_recipients = sns_message["mail"]["commonHeaders"].get("cc", [])
            in_reply_to = sns_message["mail"]["commonHeaders"].get("inReplyTo")
            references = sns_message["mail"]["commonHeaders"].get("references")

            logger.info(
                "Email received sender_email %s, to_recipients: %s, cc_recipients: %s, recipient_email: %s",
                sender_email, to_recipients, cc_recipients, recipient_email,
            )

            encoded_content = sns_message.get("content", "")
            email_body = (
                EmailProcessor.decode_email_content(encoded_content)
                if encoded_content
                else "No content found."
            )
            logger.info("Parsed email from %s with subject: %s", sender_email, subject)

            return {
                "sender": sender_email,
                "recipient": recipient_email,
                "subject": subject,
                "body": email_body,
                "message_id": message_id,
                "date_received": date_received,
                "to_recipients": to_recipients,
                "cc_recipients": cc_recipients,
                "in_reply_to": in_reply_to,
                "references": references,
            }
        except Exception as e:
            logger.error("Error parsing SNS event: %s", e)
            return None

    @staticmethod
    def decode_email_content(encoded_content):
        """Decodes base64 email content and extracts text/plain body."""
        decoded_bytes = base64.b64decode(encoded_content)
        decoded_content = decoded_bytes.decode("utf-8", errors="ignore")
        return EmailProcessor.extract_text_from_email(decoded_content)

    @staticmethod
    def extract_text_from_email(email_content):
        """Extracts the plain text body from a multipart email."""
        email_msg = message_from_string(email_content)
        if email_msg.is_multipart():
            for part in email_msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(
                    part.get("Content-Disposition")
                ):
                    return EmailProcessor.clean_email_body(
                        part.get_payload(decode=True).decode("utf-8", errors="ignore")
                    )
        return EmailProcessor.clean_email_body(
            email_msg.get_payload(decode=True).decode("utf-8", errors="ignore")
        )

    @staticmethod
    def clean_email_body(body):
        """Removes signatures and unnecessary text."""
        return body.strip().split("-- \n")[0]
