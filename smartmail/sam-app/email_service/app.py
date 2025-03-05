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

# Initialize logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize SES client
ses_client = boto3.client('ses', region_name="us-west-2")  # Change to your SES region

import boto3
import email
import email.utils
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Initialize SES client
ses_client = boto3.client('ses', region_name="us-west-2")

def send_reply(event, reply_content):
    """Sends a reply email using AWS SES `send_raw_email`, dynamically setting 'From' and 'Reply-To'."""

    # Extract details from SNS event (SES Notification)
    ses_message = event["Records"][0]["Sns"]["Message"]
    ses_data = json.loads(ses_message)

    sender_email = ses_data["mail"]["source"]  # Original sender
    recipient_email = ses_data["mail"]["destination"][0]  # Extracts the recipient (who was emailed)
    original_subject = ses_data["mail"]["commonHeaders"]["subject"]
    original_message_id = ses_data["mail"]["commonHeaders"]["messageId"]

    # Create email message
    msg = MIMEMultipart()
    msg["Subject"] = f"Re: {original_subject}"
    msg["From"] = recipient_email  # Use the original recipient dynamically
    msg["To"] = sender_email  # Reply back to the original sender
    msg["Reply-To"] = recipient_email  # Ensures further replies go to the same email
    msg["In-Reply-To"] = original_message_id
    msg["References"] = original_message_id
    msg["Date"] = email.utils.formatdate(localtime=True)
    msg["Message-ID"] = email.utils.make_msgid(domain=recipient_email.split('@')[-1])  # Use domain dynamically

    # Email body
    msg.attach(MIMEText(reply_content, "plain"))

    try:
        # Send email using SES
        response = ses_client.send_raw_email(
            Source=recipient_email,  # Uses the same email the user initially contacted
            Destinations=[sender_email],
            RawMessage={"Data": msg.as_string()}
        )

        print(f"Reply sent successfully! Message ID: {response['MessageId']}")
        return response["MessageId"]
    
    except Exception as e:
        print(f"Error sending reply: {str(e)}")
        return None

def extract_text_from_email(email_content):
    """Extracts the plain text body from a multipart email."""
    email_msg = message_from_string(email_content)
    
    if email_msg.is_multipart():
        for part in email_msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                email_body = part.get_payload(decode=True).decode("utf-8", errors="ignore")
                return clean_email_body(email_body)

    return clean_email_body(email_msg.get_payload(decode=True).decode("utf-8", errors="ignore"))

def clean_email_body(body):
    """Cleans email text by removing signatures and extra newlines."""
    body = body.strip()
    body = body.split("-- \n")[0]  # Remove signature block
    return body

def generate_message(email_content):
    """Calls OpenAI API to generate an email message."""
    openai.api_key = os.getenv("OPENAI_API_KEY")

    client = openai.OpenAI()

    response = client.chat.completions.create(
        model="gpt-4o-mini-2024-07-18",
        messages=[
            {"role": "system", "content": "You are an AI assistant designed to read user emails, understand their intent, and provide natural, friendly, and conversational responses. Your task is to identify the main question(s) in the email and craft a response that feels warm, engaging, and helpful—just like a thoughtful human assistant would. Avoid robotic or overly formal phrasing. Instead of explicitly stating ‘Extracted Question’ or ‘Comprehensive Answer,’ naturally acknowledge the user’s inquiry and respond in a way that feels conversational and friendly. If the email lacks a clear question, infer the intent and offer a relevant response. Always keep the response structured, concise, and easy to read."},
            {"role": "user", "content": email_content}
        ]
    )

    return response.choices[0].message.content

def load_conversion(event):
    """Extracts subject, sender, and decoded email body from SNS event."""
    try:
        sns_record = event["Records"][0]["Sns"]
        sns_message = sns_record["Message"]
        parsed_message = json.loads(sns_message)  # Parse SNS message

        # Extract sender email, subject, and message ID for threading
        sender_email = parsed_message["mail"]["source"]
        email_subject = parsed_message["mail"]["commonHeaders"]["subject"]
        message_id = parsed_message["mail"]["messageId"]

        # Extract base64-encoded email body
        encoded_content = parsed_message.get("content", "")
        if encoded_content:
            decoded_bytes = base64.b64decode(encoded_content)
            decoded_content = decoded_bytes.decode("utf-8", errors="ignore")
            cleaned_content = extract_text_from_email(decoded_content)
        else:
            cleaned_content = "No content found."

        logger.info(f"Email Subject: {email_subject}")
        logger.info(f"Sender: {sender_email}")
        logger.info(f"Cleaned Email Content: {cleaned_content}")

        return {"sender": sender_email, "subject": email_subject, "body": cleaned_content, "message_id": message_id}

    except Exception as e:
        logger.error(f"Error parsing SNS message: {str(e)}")
        return None

def lambda_handler(event, context):
    """Lambda function handler."""
    try:
        email_data = load_conversion(event)
        if not email_data:
            return {"statusCode": 400, "body": "Invalid email data."}

        # Generate AI reply
        reply_content = generate_message(email_data["body"])

        # Send the reply email
        message_id = send_reply(event, reply_content)

        if message_id:
            return {"statusCode": 200, "body": f"Reply sent! Message ID: {message_id}"}
        else:
            return {"statusCode": 500, "body": "Failed to send reply."}

    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}