import os
import sys
import json
import logging
import base64
import boto3
import email
import email.utils
import openai
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import message_from_string

sys.path.append("vendor")

# === CONFIGURATION ===
AWS_REGION = "us-west-2"  # Change to your SES region
OPENAI_MODEL = "gpt-4o-mini-2024-07-18"

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS SES client
ses_client = boto3.client("ses", region_name=AWS_REGION)

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")


class EmailProcessor:
    """Handles parsing of received emails from SNS and preparing replies."""

    @staticmethod
    def parse_sns_event(event):
        """Extracts sender email, subject, and decoded email body from SNS event."""
        try:
            sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
            sender_email = sns_message["mail"]["source"]
            recipient_email = sns_message["mail"]["destination"][0]
            subject = sns_message["mail"]["commonHeaders"]["subject"]
            message_id = sns_message["mail"]["messageId"]
            date_received = sns_message["mail"]["commonHeaders"]["date"]

            # Extract base64-encoded email body
            encoded_content = sns_message.get("content", "")
            email_body = (
                EmailProcessor.decode_email_content(encoded_content)
                if encoded_content
                else "No content found."
            )

            logger.info(f"Parsed email from {sender_email} with subject: {subject}")

            return {
                "sender": sender_email,
                "recipient": recipient_email,
                "subject": subject,
                "body": email_body,
                "message_id": message_id,
                "date_received": date_received,
            }

        except Exception as e:
            logger.error(f"Error parsing SNS event: {str(e)}")
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
        return EmailProcessor.clean_email_body(email_msg.get_payload(decode=True).decode("utf-8", errors="ignore"))

    @staticmethod
    def clean_email_body(body):
        """Removes signatures and unnecessary text."""
        return body.strip().split("-- \n")[0]


class OpenAIResponder:
    """Handles generating AI responses using OpenAI."""

    SYSTEM_PROMPT = (
        "You are an AI assistant designed to read user emails, understand their intent, and provide natural, friendly, "
        "and conversational responses. Your task is to identify the main question(s) in the email and craft a response "
        "that feels warm, engaging, and helpful—just like a thoughtful human assistant would. Avoid robotic or overly "
        "formal phrasing. Instead of explicitly stating ‘Extracted Question’ or ‘Comprehensive Answer,’ naturally "
        "acknowledge the user’s inquiry and respond in a way that feels conversational and friendly. If the email lacks "
        "a clear question, infer the intent and offer a relevant response. Keep responses concise and structured."
    )

    @staticmethod
    def generate_response(subject, body):
        """Generates an AI-crafted email response based on the original email content."""
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT},
                    {"role": "user", "content": f"{subject}\n{body}"},
                ],
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {str(e)}")
            return "I'm sorry, but I couldn't generate a response at this time."


class EmailReplySender:
    """Handles formatting and sending replies via AWS SES."""

    @staticmethod
    def send_reply(email_data, reply_content):
        """Sends a reply email using AWS SES, preserving email threading."""
        try:
            formatted_reply = EmailReplySender.format_reply(email_data, reply_content)

            # Construct email with threading metadata
            msg = MIMEMultipart()
            msg["Subject"] = f"Re: {email_data['subject']}"
            msg["From"] = email_data["recipient"]  # The original recipient becomes the sender
            msg["To"] = email_data["sender"]  # Reply to the original sender
            msg["Reply-To"] = email_data["recipient"]
            msg["In-Reply-To"] = email_data["message_id"]
            msg["References"] = email_data["message_id"]
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg["Message-ID"] = email.utils.make_msgid(domain=email_data["recipient"].split("@")[-1])

            # Attach formatted reply
            msg.attach(MIMEText(formatted_reply, "plain"))

            # Send via AWS SES
            response = ses_client.send_raw_email(
                Source=email_data["recipient"],
                Destinations=[email_data["sender"]],
                RawMessage={"Data": msg.as_string()},
            )

            logger.info(f"Reply sent successfully! Message ID: {response['MessageId']}")
            return response["MessageId"]

        except Exception as e:
            logger.error(f"Error sending reply: {str(e)}")
            return None

    @staticmethod
    def format_reply(email_data, reply_content):
        """Formats the reply email with original message context."""
        return (
            f"{reply_content}\n\n"
            f"---\n"
            f"From: {email_data['sender']}\n"
            f"Sent: {email_data['date_received']}\n"
            f"To: {email_data["recipient"]} wrote:\n"
            f"Subject: {email_data['subject']} wrote:\n\n"
            f"{email_data['body']}\n"
        )

def lambda_handler(event, context):
    """AWS Lambda function handler."""
    try:
        email_data = EmailProcessor.parse_sns_event(event)
        if not email_data:
            return {"statusCode": 400, "body": "Invalid email data."}

        # Generate AI response
        reply_content = OpenAIResponder.generate_response(email_data["subject"], email_data["body"])

        # Send reply via SES
        message_id = EmailReplySender.send_reply(email_data, reply_content)

        return (
            {"statusCode": 200, "body": f"Reply sent! Message ID: {message_id}"}
            if message_id
            else {"statusCode": 500, "body": "Failed to send reply."}
        )

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}