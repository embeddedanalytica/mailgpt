import json
import base64
import logging
from email import message_from_string

logger = logging.getLogger()
logger.setLevel(logging.INFO)

class EmailProcessor:
    """Handles parsing of received emails from SNS and preparing replies."""

    @staticmethod
    def parse_sns_event(event):
        try:
            sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
            sender_email = sns_message["mail"]["source"]
            recipient_email = sns_message["mail"]["destination"][0]
            subject = sns_message["mail"]["commonHeaders"]["subject"]
            message_id = sns_message["mail"]["messageId"]
            date_received = sns_message["mail"]["commonHeaders"]["date"]
            to_recipients = sns_message["mail"]["commonHeaders"].get("to", [])
            cc_recipients = sns_message["mail"]["commonHeaders"].get("cc", [])

            logger.info(f"Email from {sender_email} with subject '{subject}'")

            encoded_content = sns_message.get("content", "")
            email_body = (
                EmailProcessor.decode_email_content(encoded_content)
                if encoded_content else "No content found."
            )

            return {
                "sender": sender_email,
                "recipient": recipient_email,
                "subject": subject,
                "body": email_body,
                "message_id": message_id,
                "date_received": date_received,
                "to_recipients": to_recipients,
                "cc_recipients": cc_recipients,
            }

        except Exception as e:
            logger.error(f"Error parsing SNS event: {e}")
            return None

    @staticmethod
    def decode_email_content(encoded_content):
        decoded_bytes = base64.b64decode(encoded_content)
        decoded_content = decoded_bytes.decode("utf-8", errors="ignore")
        return EmailProcessor.extract_text_from_email(decoded_content)

    @staticmethod
    def extract_text_from_email(email_content):
        email_msg = message_from_string(email_content)
        if email_msg.is_multipart():
            for part in email_msg.walk():
                if part.get_content_type() == "text/plain" and "attachment" not in str(part.get("Content-Disposition")):
                    return EmailProcessor.clean_email_body(part.get_payload(decode=True).decode("utf-8", errors="ignore"))
        return EmailProcessor.clean_email_body(email_msg.get_payload(decode=True).decode("utf-8", errors="ignore"))

    @staticmethod
    def clean_email_body(body):
        return body.strip().split("-- \n")[0]