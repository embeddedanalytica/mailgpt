"""
Sending replies via SES: format (HTML), evaluate via ResponseEvaluation, send.
Depends on business/LLM only for the reply content; no auth or rate-limit logic here.
"""
import logging
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto3  # type: ignore

from config import AWS_REGION
from response_evaluator import ResponseEvaluation

logger = logging.getLogger(__name__)
ses_client = boto3.client("ses", region_name=AWS_REGION)


class EmailReplySender:
    """Handles formatting and sending replies via AWS SES."""

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
    def send_reply(email_data, reply_content):
        """Sends a reply email using AWS SES; evaluates and stores the reply via ResponseEvaluation."""
        try:
            formatted_reply = EmailReplySender.format_reply(email_data, reply_content)
            #ResponseEvaluation.evaluate_response(email_data["body"], reply_content) #TODO: Uncomment this when we have a way to store the evaluation results

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
            msg["In-Reply-To"] = email_data["message_id"]
            msg["References"] = email_data["message_id"]
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
    def format_reply(email_data, reply_content):
        """Formats the reply email with original message context (HTML)."""
        cc_text = f"CC: {', '.join(email_data['cc_recipients'])}<br>" if email_data["cc_recipients"] else ""
        return (
            f"<html><body>"
            f"{reply_content.replace(chr(10), '<br>')}<br>"
            f"---<br>"
            f"From: {email_data['sender']}<br>"
            f"Sent: {email_data['date_received']}<br>"
            f"To: {', '.join(email_data['to_recipients'])}<br>"
            f"{cc_text}"
            f"Subject: {email_data['subject']}<br><br>"
            f"{email_data['body'].replace(chr(10), '<br>')}"
            f"</body></html>"
        )
