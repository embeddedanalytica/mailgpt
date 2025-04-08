import logging
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import boto3
from response_evaluator import ResponseEvaluation

logger = logging.getLogger()
logger.setLevel(logging.INFO)

ses_client = boto3.client("ses", region_name="us-west-2")

class EmailReplySender:

    @staticmethod
    def filter_valid_recipients(recipients):
        invalid_domains = ["amazonses.com", "amazonaws.com", "geniml.com"]
        return [email for email in recipients if not any(domain in email for domain in invalid_domains)]

    @staticmethod
    def get_geniml_email(recipients):
        for email in recipients:
            if email.endswith("@geniml.com"):
                return email
        return "hello@geniml.com"

    @staticmethod
    def send_reply(email_data, reply_content):
        try:
            formatted_reply = EmailReplySender.format_reply(email_data, reply_content)
            ResponseEvaluation.evaluate_response(email_data["body"], reply_content)

            from_ai = EmailReplySender.get_geniml_email(email_data["to_recipients"] + email_data["cc_recipients"])
            to_list = EmailReplySender.filter_valid_recipients(email_data["to_recipients"])
            cc_list = EmailReplySender.filter_valid_recipients(email_data["cc_recipients"])

            if email_data["sender"] not in to_list:
                to_list.append(email_data["sender"])

            subject = email_data["subject"]
            if not subject.lower().startswith("re:"):
                subject = "Re: " + subject

            msg = MIMEMultipart()
            msg["Subject"] = subject
            msg["From"] = from_ai
            msg["To"] = ", ".join(to_list)
            msg["Cc"] = ", ".join(cc_list)
            msg["Reply-To"] = from_ai
            msg["In-Reply-To"] = email_data["message_id"]
            msg["References"] = email_data["message_id"]
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg["Message-ID"] = email.utils.make_msgid(domain=from_ai.split("@")[-1])

            msg.attach(MIMEText(formatted_reply, "plain", "utf-8"))

            all_recipients = list(set(to_list + cc_list))
            if not all_recipients:
                logger.warning("No valid recipients.")
                return None

            response = ses_client.send_raw_email(
                Source=from_ai,
                Destinations=all_recipients,
                RawMessage={"Data": msg.as_string()},
            )
            return response["MessageId"]
        except Exception as e:
            logger.error(f"Failed to send reply: {e}")
            return None

    @staticmethod
    def format_reply(email_data, reply_content):
        cc_text = f"CC: {', '.join(email_data['cc_recipients'])}\n" if email_data["cc_recipients"] else ""
        return (
            f"{reply_content}\n\n"
            f"---\n"
            f"From: {email_data['sender']}\n"
            f"Sent: {email_data['date_received']}\n"
            f"To: {email_data['to_recipients']}\n"
            f"{cc_text}"
            f"Subject: {email_data['subject']}\n\n"
            f"{email_data['body']}\n"
        )