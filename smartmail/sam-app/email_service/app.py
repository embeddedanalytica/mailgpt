import os
import sys
import json
import logging
import base64
import boto3 # type: ignore
import email
import email.utils
import openai # type: ignore
import re
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email import message_from_string
from botocore.exceptions import ClientError # type: ignore
from typing import Optional, Dict, Any, List

sys.path.append("vendor")
sys.path.append(".")

# Import DynamoDB models
from dynamodb_models import (
    is_verified,
    create_action_token,
    claim_verified_quota_slot,
    atomically_set_verified_notice_cooldown_if_allowed,
    get_coach_profile,
    merge_coach_profile_fields,
)
import time

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
VERIFIED_HOURLY_QUOTA = int(os.getenv("VERIFIED_HOURLY_QUOTA", "2"))
VERIFIED_DAILY_QUOTA = int(os.getenv("VERIFIED_DAILY_QUOTA", "10"))
SEND_RATE_LIMIT_NOTICE = os.getenv("SEND_RATE_LIMIT_NOTICE", "false").lower() == "true"
RATE_LIMIT_NOTICE_COOLDOWN_MINUTES = int(
    os.getenv("RATE_LIMIT_NOTICE_COOLDOWN_MINUTES", "60")
)


def _contains_unknown_marker(text: str) -> bool:
    lowered = text.lower()
    return any(
        marker in lowered
        for marker in ("unknown", "not sure", "skip", "n/a", "na", "prefer not")
    )


class GoalExtractor:
    """Pluggable goal extraction strategy."""

    def extract_goal(self, email_body: str) -> Optional[str]:
        raise NotImplementedError()


class RegexGoalExtractor(GoalExtractor):
    """Default goal extraction using deterministic regex patterns."""

    def extract_goal(self, email_body: str) -> Optional[str]:
        return _extract_goal_with_regex(email_body)


_goal_extractor: GoalExtractor = RegexGoalExtractor()


def set_goal_extractor(extractor: GoalExtractor) -> None:
    """
    Overrides the default goal extractor strategy.

    This is intended for future LLM-based extraction replacement and tests.
    """
    global _goal_extractor
    _goal_extractor = extractor


def extract_goal_from_email(email_body: str) -> Optional[str]:
    return _goal_extractor.extract_goal(email_body)


class WeeklyTimeExtractor:
    """Pluggable weekly time extraction strategy."""

    def extract_weekly_minutes(self, email_body: str) -> Optional[int]:
        raise NotImplementedError()


class RegexWeeklyTimeExtractor(WeeklyTimeExtractor):
    """Default weekly time extraction using deterministic regex patterns."""

    def extract_weekly_minutes(self, email_body: str) -> Optional[int]:
        return _extract_weekly_minutes_with_regex(email_body)


_weekly_time_extractor: WeeklyTimeExtractor = RegexWeeklyTimeExtractor()


def set_weekly_time_extractor(extractor: WeeklyTimeExtractor) -> None:
    global _weekly_time_extractor
    _weekly_time_extractor = extractor


def extract_weekly_minutes_from_email(email_body: str) -> Optional[int]:
    return _weekly_time_extractor.extract_weekly_minutes(email_body)


class SportsExtractor:
    """Pluggable sports extraction strategy."""

    def extract_sports(self, email_body: str) -> List[str]:
        raise NotImplementedError()


class KeywordSportsExtractor(SportsExtractor):
    """Default sports extraction using keyword normalization."""

    def extract_sports(self, email_body: str) -> List[str]:
        return _extract_sports_with_keywords(email_body)


_sports_extractor: SportsExtractor = KeywordSportsExtractor()


def set_sports_extractor(extractor: SportsExtractor) -> None:
    global _sports_extractor
    _sports_extractor = extractor


def extract_sports_from_email(email_body: str) -> List[str]:
    return _sports_extractor.extract_sports(email_body)


def _extract_goal_with_regex(text: str) -> Optional[str]:
    goal_patterns = [
        r"\bgoal\s*[:\-]\s*([^\n\r]+)",
        r"\bmy goal is\s+([^\n\r]+)",
        r"\bi want to\s+([^\n\r]+)",
        r"\bi(?:'| a)?m training for\s+([^\n\r]+)",
    ]
    for pattern in goal_patterns:
        match = re.search(pattern, text, flags=re.IGNORECASE)
        if match:
            goal = match.group(1).strip(" .,!?:;")
            if goal:
                return goal
    return None


def _extract_weekly_minutes_with_regex(text: str) -> Optional[int]:
    combined_match = re.search(
        r"(\d{1,3})\s*h(?:ours?)?\s*(\d{1,3})?\s*m(?:in(?:utes?)?)?",
        text,
        flags=re.IGNORECASE,
    )
    if combined_match:
        hours = int(combined_match.group(1))
        minutes = int(combined_match.group(2) or 0)
        return (hours * 60) + minutes

    hour_match = re.search(r"(\d{1,3})\s*h(?:ours?)?\b", text, flags=re.IGNORECASE)
    if hour_match:
        return int(hour_match.group(1)) * 60

    minute_match = re.search(
        r"(\d{1,4})\s*m(?:in(?:utes?)?)?\b", text, flags=re.IGNORECASE
    )
    if minute_match:
        return int(minute_match.group(1))

    weekly_numeric = re.search(
        r"\b(?:weekly|per week)\D{0,20}(\d{2,4})\b", text, flags=re.IGNORECASE
    )
    if weekly_numeric:
        return int(weekly_numeric.group(1))

    return None


def _extract_sports_with_keywords(text: str) -> List[str]:
    known = {
        "running": "running",
        "run": "running",
        "jogging": "running",
        "cycling": "cycling",
        "bike": "cycling",
        "biking": "cycling",
        "swimming": "swimming",
        "swim": "swimming",
        "triathlon": "triathlon",
        "strength": "strength",
        "weightlifting": "strength",
        "gym": "strength",
        "yoga": "yoga",
        "hiking": "hiking",
    }
    detected: List[str] = []

    explicit_line = re.search(r"\bsports?\s*[:\-]\s*([^\n\r]+)", text, flags=re.IGNORECASE)
    if explicit_line:
        parts = re.split(r"[,/]| and ", explicit_line.group(1), flags=re.IGNORECASE)
        for part in parts:
            token = part.strip().lower()
            if token in known:
                canonical = known[token]
                if canonical not in detected:
                    detected.append(canonical)

    lowered = text.lower()
    for keyword, canonical in known.items():
        if re.search(rf"\b{re.escape(keyword)}\b", lowered):
            if canonical not in detected:
                detected.append(canonical)
    return detected


def parse_profile_updates_from_email(body: str) -> Dict[str, Any]:
    updates: Dict[str, Any] = {}
    goal_value = extract_goal_from_email(body)
    if goal_value:
        updates["goal"] = goal_value
    elif _contains_unknown_marker(body) and re.search(r"\bgoal\b", body, re.IGNORECASE):
        updates["goal_unknown"] = True

    weekly_minutes = extract_weekly_minutes_from_email(body)
    if weekly_minutes is not None:
        updates["weekly_time_budget_minutes"] = weekly_minutes
    elif _contains_unknown_marker(body) and re.search(
        r"\b(week|weekly|hours?|minutes?|time)\b", body, re.IGNORECASE
    ):
        updates["weekly_time_budget_unknown"] = True

    sports = extract_sports_from_email(body)
    if sports:
        updates["sports"] = sports
    elif _contains_unknown_marker(body) and re.search(r"\bsports?\b", body, re.IGNORECASE):
        updates["sports_unknown"] = True

    return updates


def get_missing_required_profile_fields(profile: Optional[Dict[str, Any]]) -> List[str]:
    profile = profile or {}
    missing: List[str] = []

    goal = str(profile.get("goal", "")).strip()
    if not goal and not bool(profile.get("goal_unknown")):
        missing.append("goal")

    weekly_minutes = profile.get("weekly_time_budget_minutes")
    valid_weekly_minutes = isinstance(weekly_minutes, int) and weekly_minutes > 0
    if not valid_weekly_minutes and not bool(profile.get("weekly_time_budget_unknown")):
        missing.append("weekly_time_budget_minutes")

    sports = profile.get("sports")
    valid_sports = isinstance(sports, list) and len(sports) > 0
    if not valid_sports and not bool(profile.get("sports_unknown")):
        missing.append("sports")

    return missing


def build_profile_collection_reply(missing_fields: List[str]) -> str:
    prompts = []
    if "goal" in missing_fields:
        prompts.append("- Your training goal (e.g., 10k PR, first marathon, improve fitness)")
    if "weekly_time_budget_minutes" in missing_fields:
        prompts.append("- Your weekly time budget (minutes or hours per week)")
    if "sports" in missing_fields:
        prompts.append("- Sports you want coaching for (e.g., running, cycling)")

    joined_prompts = "\n".join(prompts)
    return (
        "Thanks - before I can coach effectively, I need a bit more context.\n\n"
        "Please reply with:\n"
        f"{joined_prompts}\n\n"
        "If any item is unknown right now, you can say \"unknown\" for that item."
    )

def is_registered(email_address):
    """
    Checks if the email exists in the DynamoDB 'users' table.
    Returns True if found, False if not found or on error.
    """
    try:
        table = dynamodb.Table(USERS_TABLE)
        response = table.get_item(Key={"email_address": email_address.lower()})
        if "Item" in response:
            logger.info(f"User {email_address} is registered.")
            return True  # User is registered
        logger.info(f"User {email_address} is not registered.")
        return False
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
            signature = (
                "<br><br>Truly yours,<br>"
                "GeniML<br>"
                '<a href="https://geniml.com">geniml.com</a>'
            )
            disclaimer = (
                "<br><br><hr><small>"
                "Disclaimer: This response is AI-generated and may contain errors. "
                "Please verify all information provided. For feedback, email "
                '<a href="mailto:feedback@geniml.com">feedback@geniml.com</a>.'
                "</small><hr>"
            )
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

def atomically_set_cooldown_if_allowed(email: str, cooldown_until: int, now: int) -> bool:
    """
    Atomically sets cooldown only if it doesn't exist or is in the past.
    This prevents race conditions where multiple requests try to send verification emails.
    
    Args:
        email: Email address
        cooldown_until: Epoch seconds when cooldown expires
        now: Current epoch seconds
    
    Returns:
        True if cooldown was successfully set (this request "won"), False if cooldown already active
    """
    try:
        table_name = os.getenv("RATE_LIMITS_TABLE_NAME")
        if not table_name:
            logger.error("RATE_LIMITS_TABLE_NAME environment variable not set")
            return False
        
        table = dynamodb.Table(table_name)
        
        # Atomic conditional update: only succeeds if cooldown doesn't exist or is expired
        table.update_item(
            Key={"email": email.lower()},
            UpdateExpression="""
                SET verify_email_cooldown_until = :cooldown_until,
                    last_verify_token_sent_at = :now
            """,
            ConditionExpression="""
                attribute_not_exists(verify_email_cooldown_until) OR 
                verify_email_cooldown_until <= :now
            """,
            ExpressionAttributeValues={
                ":cooldown_until": cooldown_until,
                ":now": now
            }
        )
        return True
    except ClientError as e:
        error_code = e.response.get("Error", {}).get("Code", "")
        if error_code == "ConditionalCheckFailedException":
            # Cooldown is active (another request set it first)
            return False
        else:
            logger.error(f"Error setting cooldown for {email}: {e}")
            return False


def get_cooldown_until(email: str) -> Optional[int]:
    """
    Gets the cooldown_until value for an email.
    
    Args:
        email: Email address
    
    Returns:
        Cooldown until epoch seconds, or None if not set
    """
    try:
        table_name = os.getenv("RATE_LIMITS_TABLE_NAME")
        if not table_name:
            return None
        
        table = dynamodb.Table(table_name)
        response = table.get_item(Key={"email": email.lower()})
        
        if "Item" in response:
            return response["Item"].get("verify_email_cooldown_until")
        return None
    except ClientError as e:
        logger.error(f"Error getting cooldown for {email}: {e}")
        return None


class VerificationEmailSender:
    """Handles sending verification emails."""

    @staticmethod
    def send_verification_email(email: str, token_id: str) -> bool:
        """
        Sends a verification email with the action link.
        
        Args:
            email: Recipient email address
            token_id: Token ID to include in the link
        
        Returns:
            True if successful, False otherwise
        """
        try:
            action_base_url = os.getenv("ACTION_BASE_URL", "")
            if not action_base_url:
                logger.error("ACTION_BASE_URL environment variable not set")
                return False
            
            verification_link = f"{action_base_url}{token_id}"
            
            # Get the geniml.com email to send from
            from_address = "hello@geniml.com"
            
            # Get TTL from environment for display
            verify_ttl_minutes = int(os.getenv("VERIFY_TOKEN_TTL_MINUTES", "30"))
            
            subject = "Verify to access your coaching insights"
            
            body_text = f"""To protect your privacy and prevent abuse, we verify email addresses before sending coaching responses.

Verify your email by clicking this link:

{verification_link}

Link expires in {verify_ttl_minutes} minutes.

If you didn't request this, you can safely ignore this email.

SmartMail Coach
"""
            
            body_html = f"""<html>
<body>
<p>To protect your privacy and prevent abuse, we verify email addresses before sending coaching responses.</p>
<p>Verify your email by clicking this link:</p>
<p><a href="{verification_link}">{verification_link}</a></p>
<p>Link expires in {verify_ttl_minutes} minutes.</p>
<p>If you didn't request this, you can safely ignore this email.</p>
<p>SmartMail Coach</p>
</body>
</html>"""
            
            # Send email using SES
            response = ses_client.send_email(
                Source=from_address,
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body_text, "Charset": "UTF-8"},
                        "Html": {"Data": body_html, "Charset": "UTF-8"}
                    }
                }
            )
            
            logger.info(f"Verification email sent to {email}, Message ID: {response['MessageId']}")
            return True
            
        except Exception as e:
            logger.error(f"Error sending verification email to {email}: {str(e)}")
            return False


class RateLimitNoticeSender:
    """Handles sending throttled rate-limit notices to verified users."""

    @staticmethod
    def send_rate_limit_notice(email: str) -> bool:
        try:
            subject = "SmartMail usage limit reached"
            body_text = (
                "You've reached your SmartMail request limit for now.\n\n"
                "Please try again later. Your limit resets automatically each hour/day.\n\n"
                "SmartMail Coach"
            )
            body_html = """<html>
<body>
<p>You've reached your SmartMail request limit for now.</p>
<p>Please try again later. Your limit resets automatically each hour/day.</p>
<p>SmartMail Coach</p>
</body>
</html>"""
            response = ses_client.send_email(
                Source="hello@geniml.com",
                Destination={"ToAddresses": [email]},
                Message={
                    "Subject": {"Data": subject, "Charset": "UTF-8"},
                    "Body": {
                        "Text": {"Data": body_text, "Charset": "UTF-8"},
                        "Html": {"Data": body_html, "Charset": "UTF-8"},
                    },
                },
            )
            logger.info(
                f"Rate-limit notice sent to {email}, Message ID: {response['MessageId']}"
            )
            return True
        except Exception as e:
            logger.error(f"Error sending rate-limit notice to {email}: {str(e)}")
            return False


def maybe_send_rate_limit_notice(
    email: str,
    block_reason: str,
    aws_request_id: Optional[str] = None,
) -> Dict[str, str]:
    """
    Sends a throttled rate-limit notice when enabled.

    Returns a small outcome object for structured logging.
    """
    if not SEND_RATE_LIMIT_NOTICE:
        return {"status": "notice_disabled"}

    now = int(time.time())
    cooldown_until = now + (RATE_LIMIT_NOTICE_COOLDOWN_MINUTES * 60)
    notice_claim = atomically_set_verified_notice_cooldown_if_allowed(
        email=email,
        cooldown_until=cooldown_until,
        now=now,
    )

    if not notice_claim.get("send_notice", False):
        log_parts = [
            f"from_email={email}",
            "verified=true",
            "result=rate_limit_notice_suppressed",
            f"reason={notice_claim.get('reason')}",
            f"block_reason={block_reason}",
        ]
        if aws_request_id:
            log_parts.append(f"aws_request_id={aws_request_id}")
        logger.info(", ".join(log_parts))
        return {"status": "suppressed", "reason": str(notice_claim.get("reason"))}

    notice_sent = RateLimitNoticeSender.send_rate_limit_notice(email)
    log_parts = [
        f"from_email={email}",
        "verified=true",
        "result=rate_limit_notice_attempted",
        f"notice_sent={str(notice_sent).lower()}",
        f"block_reason={block_reason}",
        f"cooldown_until={notice_claim.get('cooldown_until')}",
    ]
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(log_parts))

    return {"status": "sent" if notice_sent else "send_failed"}


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
            msg.attach(MIMEText(formatted_reply, "html", "utf-8"))

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
            f"<html><body>"
            f"{reply_content.replace('\n', '<br>')}<br>"
            f"---<br>"
            f"From: {email_data['sender']}<br>"
            f"Sent: {email_data['date_received']}<br>"
            f"To: {', '.join(email_data['to_recipients'])}<br>"
            f"{cc_text}"
            f"Subject: {email_data['subject']}<br><br>"
            f"{email_data['body'].replace('\n', '<br>')}"
            f"</body></html>"
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


def _aws_request_id_from_context(context: Any) -> Optional[str]:
    if context and hasattr(context, "aws_request_id"):
        return context.aws_request_id
    return None


def _log_inbound_outcome(
    from_email: str,
    verified: bool,
    result: str,
    aws_request_id: Optional[str] = None,
    **metadata: Any,
) -> None:
    log_parts = [
        f"from_email={from_email}",
        f"verified={str(verified).lower()}",
        f"result={result}",
    ]
    for key, value in metadata.items():
        if value is None:
            continue
        log_parts.append(f"{key}={value}")
    if aws_request_id:
        log_parts.append(f"aws_request_id={aws_request_id}")
    logger.info(", ".join(log_parts))


def _handle_unverified_sender(from_email: str, aws_request_id: Optional[str]) -> Dict[str, Any]:
    now = int(time.time())
    cooldown_minutes = int(os.getenv("VERIFY_EMAIL_COOLDOWN_MINUTES", "30"))
    cooldown_seconds = cooldown_minutes * 60
    cooldown_until = now + cooldown_seconds

    existing_cooldown_until = get_cooldown_until(from_email)
    if existing_cooldown_until and existing_cooldown_until > now:
        _log_inbound_outcome(
            from_email=from_email,
            verified=False,
            result="unverified_dropped_cooldown",
            aws_request_id=aws_request_id,
            cooldown_until=existing_cooldown_until,
        )
        return {"statusCode": 200, "body": "Dropped (cooldown active)"}

    cooldown_set = atomically_set_cooldown_if_allowed(from_email, cooldown_until, now)
    if not cooldown_set:
        _log_inbound_outcome(
            from_email=from_email,
            verified=False,
            result="cooldown_race_lost",
            aws_request_id=aws_request_id,
        )
        return {"statusCode": 200, "body": "Dropped (race condition)"}

    verify_ttl_minutes = int(os.getenv("VERIFY_TOKEN_TTL_MINUTES", "30"))
    verify_ttl_seconds = verify_ttl_minutes * 60
    token_id = create_action_token(
        email=from_email,
        action_type="VERIFY_SESSION",
        expires_in_seconds=verify_ttl_seconds,
        source="email_inbound",
    )
    if not token_id:
        logger.error(f"Failed to create verification token for {from_email}")
        return {"statusCode": 500, "body": "Failed to create verification token."}

    email_sent = VerificationEmailSender.send_verification_email(from_email, token_id)
    if not email_sent:
        logger.error(f"Failed to send verification email to {from_email}")
        return {"statusCode": 500, "body": "Failed to send verification email."}

    _log_inbound_outcome(
        from_email=from_email,
        verified=False,
        result="verification_email_sent",
        aws_request_id=aws_request_id,
        cooldown_until=cooldown_until,
    )
    return {"statusCode": 200, "body": "Verification email sent."}


def _check_verified_quota_or_block(from_email: str, aws_request_id: Optional[str]) -> Optional[Dict[str, Any]]:
    quota_result = claim_verified_quota_slot(
        email=from_email,
        hourly_limit=VERIFIED_HOURLY_QUOTA,
        daily_limit=VERIFIED_DAILY_QUOTA,
    )
    if quota_result.get("allowed", False):
        return None

    block_reason = str(quota_result.get("reason"))
    fail_closed = block_reason in {"quota_check_error", "quota_claim_conflict"}
    _log_inbound_outcome(
        from_email=from_email,
        verified=True,
        result="verified_quota_blocked",
        aws_request_id=aws_request_id,
        reason=block_reason,
        fail_closed=str(fail_closed).lower(),
        hour_bucket=quota_result.get("hour_bucket"),
        day_bucket=quota_result.get("day_bucket"),
        hour_count=quota_result.get("hour_count"),
        day_count=quota_result.get("day_count"),
    )
    maybe_send_rate_limit_notice(
        email=from_email,
        block_reason=block_reason,
        aws_request_id=aws_request_id,
    )
    return {"statusCode": 200, "body": "Dropped (verified quota exceeded)"}


def _handle_unregistered_verified_sender(
    email_data: Dict[str, Any],
    aws_request_id: Optional[str],
) -> Dict[str, Any]:
    from_email = email_data["sender"]
    _log_inbound_outcome(
        from_email=from_email,
        verified=True,
        result="verified_unregistered_blocked",
        aws_request_id=aws_request_id,
    )
    registration_prompt = (
        "Please register your SmartMail account first to continue. "
        "Visit https://geniml.com and complete registration, then email me again."
    )
    message_id = EmailReplySender.send_reply(email_data, registration_prompt)
    return {"statusCode": 200, "body": f"Registration required. Message ID: {message_id}"}


def _build_profile_gated_reply(
    from_email: str,
    inbound_body: str,
    aws_request_id: Optional[str],
) -> str:
    profile_before = get_coach_profile(from_email) or {}
    missing_before = get_missing_required_profile_fields(profile_before)

    parsed_updates = parse_profile_updates_from_email(inbound_body)
    if parsed_updates:
        update_ok = merge_coach_profile_fields(from_email, parsed_updates)
        _log_inbound_outcome(
            from_email=from_email,
            verified=True,
            result="profile_updated",
            aws_request_id=aws_request_id,
            fields="|".join(sorted(parsed_updates.keys())),
        )
        if not update_ok:
            logger.error(
                "from_email=%s, verified=true, result=profile_update_failed%s",
                from_email,
                f", aws_request_id={aws_request_id}" if aws_request_id else "",
            )

    profile_after = get_coach_profile(from_email) or profile_before
    missing_after = get_missing_required_profile_fields(profile_after)

    if missing_after:
        _log_inbound_outcome(
            from_email=from_email,
            verified=True,
            result="profile_missing_context",
            aws_request_id=aws_request_id,
            missing_fields="|".join(missing_after),
            missing_count=len(missing_after),
        )
        profile_response = build_profile_collection_reply(missing_after)
    else:
        _log_inbound_outcome(
            from_email=from_email,
            verified=True,
            result="profile_ready_for_coaching",
            aws_request_id=aws_request_id,
        )
        profile_response = (
            "✅ You're ready for coaching. Share your latest training question "
            "or session details and I'll help you plan next steps."
        )

    _log_inbound_outcome(
        from_email=from_email,
        verified=True,
        result="profile_gate_evaluated",
        aws_request_id=aws_request_id,
        missing_before=len(missing_before),
        missing_after=len(missing_after),
    )
    return profile_response


def lambda_handler(event, context):
    """AWS Lambda function handler."""
    try:
        email_data = EmailProcessor.parse_sns_event(event)
        if not email_data:
            return {"statusCode": 400, "body": "Invalid email data."}

        from_email = email_data["sender"]
        aws_request_id = _aws_request_id_from_context(context)

        if not is_verified(from_email):
            return _handle_unverified_sender(from_email, aws_request_id)

        logger.info(f"User {from_email} is verified. Proceeding with response.")

        if not is_registered(from_email):
            return _handle_unregistered_verified_sender(email_data, aws_request_id)

        quota_block_response = _check_verified_quota_or_block(from_email, aws_request_id)
        if quota_block_response is not None:
            return quota_block_response

        profile_response = _build_profile_gated_reply(
            from_email=from_email,
            inbound_body=email_data.get("body", ""),
            aws_request_id=aws_request_id,
        )

        # Send profile-gated response while preserving original inbound body for thread context.
        message_id = EmailReplySender.send_reply(email_data, profile_response)
        return {"statusCode": 200, "body": f"Reply sent! Message ID: {message_id}"} 

    except Exception as e:
        logger.error(f"Lambda execution error: {str(e)}")
        return {"statusCode": 500, "body": f"Error: {str(e)}"}
