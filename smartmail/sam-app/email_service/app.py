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
from botocore.exceptions import ClientError

sys.path.append("vendor")

# === CONFIGURATION ===
AWS_REGION = "us-west-2"
OPENAI_GENERIC_MODEL = "gpt-4o-mini-2024-07-18"
OPENAI_CLASIFICATION_MODEL = "gpt-4o-mini-2024-07-18"
OPENAI_REASONING_MODEL = "gpt-4o-mini-2024-07-18"
# OPENAI_REASONING_MODEL = "o3-mini-2025-01-31"
NO_RESPONSE_MODEL = "gpt-4o-mini-2024-07-18"

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize AWS SES client
ses_client = boto3.client("ses", region_name=AWS_REGION)

# Initialize OpenAI client
openai.api_key = os.getenv("OPENAI_API_KEY")

dynamodb = boto3.resource("dynamodb")
USERS_TABLE = "users"
RESPONSE_EVALUAION_TABLE = "response_evaluations"

def is_registered(email_address):
    """
    Checks if the email exists in the DynamoDB 'users' table.
    Returns True if found, None if not found, and False if there's an error.
    """
    try:
        table = dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={"email_address": email_address.lower()})
        if "Item" in response:
            logger.info(f"User {email_address} is registered.")
            return True  # User is registered
        logger.info(f"User {email_address} is not registered. But who cares? Let's send the email anyway.")
        return True  # User is not registered but we'll send the email anyway (TODO: change to "None" later to enforce registration)
    except ClientError as e:
        logger.error(f"Error checking registration for {email_address}: {e}")
        return False  # Fail-safe: Return False on error


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
        "You are an AI assistant that writes natural, friendly, and conversational replies to user emails as part of an ongoing email thread. "
        "The emails are shown in reverse-chronological order (latest message at the top). To understand the conversation correctly, "
        "**you must read the messages from bottom to top** (oldest to newest). Your primary task is to identify the latest user question or intent "
        "and craft a warm, concise, and helpful response that continues the conversation fluidly.\n\n"
        "DO:\n"
        "- Focus on the most recent message at the top while using the full context below to inform your reply.\n"
        "- Match the tone of the sender: keep it casual for informal emails, and provide more structure and depth for serious or high-stakes inquiries.\n"
        "- Acknowledge the user’s intent naturally—avoid repeating their message, and instead build on it to move the conversation forward.\n"
        "- Keep responses short, clear, and engaging—like a thoughtful human assistant would.\n"
        "- Ask for clarification if the user's message is vague or ambiguous.\n\n"
        "DO NOT:\n"
        "- Greet the user again (e.g., “Hi there,” “Hope you're well”)—this is a thread.\n"
        "- Summarize previous messages or repeat earlier context unless asked explicitly.\n"
        "- Use robotic, formal, or overly verbose language.\n"
        "- Use phrases like “Extracted Question” or “Here is your response.”\n\n"
        "Your tone should be warm and conversational. Focus on clarity, empathy, and being genuinely helpful while respecting the context of an ongoing thread."
    )

    NOT_REGISTERED_SYSTEM_PROMPT = (
    "You must inform the user that they are not registered and cannot receive a response. "
    "Be polite, acknowledge their email, and direct them to register at [https://geniml.com]. "
    "Do not repeat the link more than once. End the response by inviting them to ask again after registration."
)

    @staticmethod
    def generate_response(subject, body):
        """Generates an AI-crafted email response based on the original email content."""
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=OPENAI_GENERIC_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.SYSTEM_PROMPT},
                    {"role": "user", "content": f"{subject}\n{body}"},
                ],
            )
            ai_reply = response.choices[0].message.content.strip()
            signature = "\n\nTruly yours,\nGeniML\nhttps://geniml.com"
            disclaimer = "\n\n###\nDisclaimer: This response is AI-generated and may contain errors. Please verify all information provided. For feedback, email mailto:feedback@geniml.com \n###"
            return ai_reply + signature + disclaimer
        except Exception as e:
            logger.error(f"Error generating OpenAI response: {str(e)}")
            return "I'm sorry, but I couldn't generate a response at this time."
        
    @staticmethod
    def generate_invite_response(subject, body):
        """Generates an AI-crafted email response inviting a user to register."""
        try:
            client = openai.OpenAI()
            response = client.chat.completions.create(
                model=NO_RESPONSE_MODEL,
                messages=[
                    {"role": "system", "content": OpenAIResponder.NOT_REGISTERED_SYSTEM_PROMPT},
                    {"role": "user", "content": f"{subject}"},
                ],
            )
            return response.choices[0].message.content.strip() + "\n\nTruly yours,\nGeniML\nhttps://geniml.com"
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
                model=OPENAI_GENERIC_MODEL,
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

            # Evaluate the AI-generated response
            ResponseEvaluation.evaluate_response(email_data["body"], reply_content)

            # Get AI's reply-from email (must be @geniml.com)
            from_ai_address = EmailReplySender.get_geniml_email(email_data["to_recipients"] + email_data["cc_recipients"])

            # Filter out invalid recipients
            to_recipients = EmailReplySender.filter_valid_recipients(email_data["to_recipients"])
            cc_recipients = EmailReplySender.filter_valid_recipients(email_data["cc_recipients"])

            # Ensure the original sender is always in TO
            if email_data["sender"] not in to_recipients:
                to_recipients.append(email_data["sender"])

            subject = email_data["subject"]
            if not subject.lower().startswith("re:"):
                subject = f"Re: {subject}"    

            # Construct email with threading metadata
            msg = MIMEMultipart()
            msg["Subject"] = subject
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
        cc_text = f"CC: {', '.join(email_data['cc_recipients'])}\n" if email_data["cc_recipients"] else ""
        return (
            f"{reply_content}\n\n"
            f"---\n"
            f"From: {email_data['sender']}\n"
            f"Sent: {email_data['date_received']}\n"
            f"To: {email_data['to_recipients']} :\n"
            f"{cc_text}"
            f"Subject: {email_data['subject']} :\n\n"
            f"{email_data['body']}\n"
        )


        
class ResponseEvaluation:
    """Handles evaluation and storage of AI-generated email responses using the OPENAI_REASONING_MODEL."""

    @staticmethod
    def evaluate_response(original_email, ai_response):
        """
        Evaluates the AI-generated response given the original email using the OPENAI_REASONING_MODEL, and stores the evaluation in the 'response_evaluations' DynamoDB table.
 
        Parameters:
            original_email (str): The original email content.
            ai_response (str): The AI-generated email response.
 
        Returns:
            str: The evaluation result from the LLM, or None if an error occurred.
        """
        import uuid
        import time
        try:
            client = openai.OpenAI()
            prompt = (
                "You are a strict evaluator of email replies. Here is the email thread. *Rread it in reverse chronological order to understand the entire thread* :\n\n" +
                original_email + "\n\n" +
                "Here is the suggested reply from the agent:\n\n" +
                ai_response + "\n\n" +
                "Please do the following:\n"
                "1. Assign a score from 1-5 for each of the following categories: Accuracy, Relevance, Clarity, Helpfulness, and Tone.\n"
                "2. For each category, provide one or two sentences explaining why you gave that score.\n\n"
                "Respond in JSON only, with the following structure:\n"
                "{\n"
                "  \"accuracy_score\": X,\n"
                "  \"accuracy_justification\": \"...\",\n"
                "  \"relevance_score\": X,\n"
                "  \"relevance_justification\": \"...\",\n"
                "  \"clarity_score\": X,\n"
                "  \"clarity_justification\": \"...\",\n"
                "  \"helpfulness_score\": X,\n"
                "  \"helpfulness_justification\": \"...\",\n"
                "  \"tone_score\": X,\n"
                "  \"tone_justification\": \"...\"\n"
                "}"
            )
            response = client.chat.completions.create(
                model=OPENAI_REASONING_MODEL,
                messages=[
                    {"role": "system", "content": prompt},
                ],
            )
            evaluation_result = response.choices[0].message.content.strip()

            logger.info(f"Evaluation result: {evaluation_result}")
            
            # Store the evaluation in DynamoDB table 'response_evaluations'
            table = dynamodb.Table(RESPONSE_EVALUAION_TABLE)
            evaluation_id = str(uuid.uuid4())
            timestamp = int(time.time())
            table.put_item(
                Item={
                    "evaluation_id": evaluation_id,
                    "original_email": original_email,
                    "ai_response": ai_response,
                    "evaluation": evaluation_result,
                    "timestamp": timestamp
                }
            )
            return evaluation_result
        except Exception as e:
            logger.error("Error evaluating AI response: " + str(e))
            return None

def lambda_handler(event, context):
    """AWS Lambda function handler."""
    try:
        email_data = EmailProcessor.parse_sns_event(event)
        if not email_data:
            return {"statusCode": 400, "body": "Invalid email data."}

        # Verify if the recipient (TO email) is registered in DynamoDB
        recipient_email = email_data['sender']
        registration_status = is_registered(recipient_email)
        if registration_status is None:
            logger.info(f"Recipient {recipient_email} is not registered. Generating follow-up email.")
            reply_content = OpenAIResponder.generate_invite_response(email_data["subject"], email_data["body"])
        elif registration_status is False:
            logger.error(f"Error checking registration for {recipient_email}. Aborting request.")
            return {"statusCode": 500, "body": "Internal error checking registration."}
        else:
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
