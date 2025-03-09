import os
import sys
import json
import logging
import base64
import boto3
import email
import email.utils
import openai
import re
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
        """Extracts sender email, subject, recipients (To & CC), and decoded email body from SNS event."""
        try:
            sns_message = json.loads(event["Records"][0]["Sns"]["Message"])
            sender_email = sns_message["mail"]["source"]
            recipient_email = sns_message["mail"]["destination"][0]
            subject = sns_message["mail"]["commonHeaders"]["subject"]
            message_id = sns_message["mail"]["messageId"]
            date_received = sns_message["mail"]["commonHeaders"]["date"]

            # Extract "To" and "CC" recipients
            to_recipients = sns_message["mail"]["commonHeaders"].get("to", [])
            cc_recipients = sns_message["mail"]["commonHeaders"].get("cc", [])

            logger.info(f"Email received sender_email {sender_email}, to_recipients: {to_recipients}, cc_recipients: {cc_recipients}, recipient_email: {recipient_email}")

            # Extract and clean email content
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
                "to_recipients": to_recipients,
                "cc_recipients": cc_recipients,
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
        "and conversational responses. Your task is to identify the main question in the email and craft a response "
        "that feels warm, engaging, and helpful—just like a thoughtful human assistant would. Avoid robotic or overly "
        "formal phrasing. Instead of explicitly stating ‘Extracted Question’ or ‘Comprehensive Answer,’ naturally "
        "acknowledge the user’s inquiry *without repeating the question*, and respond in a way that feels conversational and friendly. "
        "If the email lacks a clear question, ask for clarifications. Keep responses concise and structured."
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
        

    SYSTEM_PROMPT_FOR_INTENTION_CHECK = (
        "You are an intelligent email assistant analyzing the latest email in a thread to determine if an AI-generated "
        "response is necessary. Only evaluate content **until the first occurrence of common delimiters** such as `---`, `FROM`, `TO`, or `SUBJECT`, "
        "which indicate the start of previous messages. Do not analyze the full thread.\n\n"
        "Reply with ONLY `true` (if AI should respond) or `false` (if AI should NOT respond). No explanations.\n\n"
        "**Respond `true` if the latest email:**\n"
        "- Contains a clear, AI-answerable question.\n"
        "- Explicitly requests AI’s help, advice, or factual input.\n"
        "- Introduces a new topic or request that AI has not yet addressed.\n\n"
        "**Respond `false` if the latest email:**\n"
        "- Is part of a human-to-human conversation without requesting AI input.\n"
        "- Replies to AI’s previous response without adding a new question or request.\n"
        "- Mentions AI but does not ask for assistance.\n"
        "- Is a confirmation, acknowledgment, or casual remark (e.g., 'Thanks!', 'Got it!').\n"
        "- Is redundant, meaning AI has already answered a similar query in one of the last three messages."
    )

    @staticmethod
    def should_ai_respond(email_body, recipient, to_recipients, cc_recipients):
        """
        Determines if AI should respond:
        1. Always respond if the only recipient in 'To' is a geniml.com email.
        2. Otherwise, check if AI is mentioned and a question is asked.
        3. Avoid responding if the last email in the thread was AI's response.
        """
        ai_keywords = ["ai", "bot", "geniml", "@ai", "assistant"]

        # Ensure all email addresses are lowercase for comparison
        to_recipients = [email.lower() for email in to_recipients]
        cc_recipients = [email.lower() for email in cc_recipients]
        recipient = recipient.lower()

        # Condition 1: If the only recipient in "To" is a geniml.com email, always respond
        is_only_geniml_recipient = (
            len(to_recipients) == 1 and recipient.endswith("@geniml.com")
        )
        if is_only_geniml_recipient:
            logger.info(f"Only geniml.com recipient found. AI will respond.")
            return True

        """
        Determines if AI should respond using OpenAI classification.
        """
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT_FOR_INTENTION_CHECK},
                    {"role": "user", "content": f"{email_body}"}
                ],
                temperature=0  # Keep it deterministic
            )
            
            decision = response.choices[0].message.content.strip().lower()
            logger.info(f"AI decision: {decision}")
            return decision == "true"  # Only return True if OpenAI explicitly says "true"

        except Exception as e:
            logger.error(f"Error checking AI response necessity: {str(e)}")
            return False  # Fail-safe: Do not respond if OpenAI check fails

class EmailReplySender:
    """Handles formatting and sending replies via AWS SES."""

    @staticmethod
    def filter_valid_recipients(recipients):
        """Filters out SES system-generated emails from recipient list."""
        invalid_domains = ["amazonses.com", "amazonaws.com", "geniml.com"]  # Avoid system-generated emails
        return [email for email in recipients if not any(domain in email for domain in invalid_domains)]
    
    @staticmethod
    def get_geniml_email(recipients):
        """Finds the first geniml.com email in recipients; defaults to hello@geniml.com if not found."""
        for email in recipients:
            if email.endswith("@geniml.com"):
                return email
        return "hello@geniml.com"

    @staticmethod
    def send_reply(email_data, reply_content):
        """Sends a reply email using AWS SES, ensuring TO includes the original sender, and TO/CC lists are preserved."""
        try:
            formatted_reply = EmailReplySender.format_reply(email_data, reply_content)

            # Get AI's reply-from email (must be @geniml.com)
            from_ai_address = EmailReplySender.get_geniml_email(email_data["to_recipients"] + email_data["cc_recipients"])

            # Filter out invalid recipients
            to_recipients = EmailReplySender.filter_valid_recipients(email_data["to_recipients"])
            cc_recipients = EmailReplySender.filter_valid_recipients(email_data["cc_recipients"])

            # Ensure the original sender is always in TO
            if email_data["sender"] not in to_recipients:
                to_recipients.append(email_data["sender"])

            # Construct email with threading metadata
            msg = MIMEMultipart()
            msg["Subject"] = f"Re: {email_data['subject']}"
            msg["From"] = from_ai_address  # AI replies from geniml.com email
            msg["To"] = ", ".join(to_recipients)
            msg["Cc"] = ", ".join(cc_recipients)
            msg["Reply-To"] = from_ai_address  # Ensures future replies go to AI
            msg["In-Reply-To"] = email_data["message_id"]
            msg["References"] = email_data["message_id"]
            msg["Date"] = email.utils.formatdate(localtime=True)
            msg["Message-ID"] = email.utils.make_msgid(domain=from_ai_address.split("@")[-1])

            # **Attach the reply content properly**
            msg.attach(MIMEText(formatted_reply, "plain", "utf-8"))

            # Ensure there is at least one recipient
            all_recipients = list(set(to_recipients + cc_recipients))
            if not all_recipients:
                logger.error("No valid recipients found. Aborting email send.")
                return None

            # Send email using SES
            response = ses_client.send_raw_email(
                Source=from_ai_address,
                Destinations=to_recipients + cc_recipients,
                RawMessage={"Data": msg.as_string()},
            )

            logger.info(f"From: {from_ai_address}, To: {to_recipients}, CC: {cc_recipients}")
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
            f"To: {email_data["recipient"]} :\n"
            f"Subject: {email_data['subject']} :\n\n"
            f"{email_data['body']}\n"
        )


def lambda_handler(event, context):
    """AWS Lambda function handler."""
    try:
        email_data = EmailProcessor.parse_sns_event(event)
        if not email_data:
            return {"statusCode": 400, "body": "Invalid email data."}

        # Decide if OpenAI should generate a response
        if OpenAIResponder.should_ai_respond(
            email_data["body"], email_data["recipient"], email_data["to_recipients"], email_data["cc_recipients"]
        ):
            reply_content = OpenAIResponder.generate_response(email_data["subject"], email_data["body"])
        else:
            logger.info("AI was not mentioned, skipping response generation.")
            reply_content = None  # Do not generate a response

        # If AI should reply, send the email

        logger.info(f"Reply content: {reply_content}")

        if reply_content:
            message_id = EmailReplySender.send_reply(email_data, reply_content)
            return {"statusCode": 200, "body": f"Reply sent! Message ID: {message_id}"}
        else:
            return {"statusCode": 204, "body": "No AI response needed."} 

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
    
