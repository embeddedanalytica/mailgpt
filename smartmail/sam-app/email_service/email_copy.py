"""
Centralized outbound email copy and AI prompt text.

Update user-facing email wording and AI-facing prompt wording here.
"""
from typing import Dict, List


class EmailCopy:
    """User-facing copy that can be sent to end users."""

    REGISTRATION_REQUIRED_REPLY = (
        "Thanks for reaching out. To get personalized coaching from GeniML "
        "(Genius in the Machine), you'll need to register first.\n\n"
        "Learn more about the service and sign up here:\n\n"
        "  https://geniml.com\n\n"
        "After you've registered, reply to this email and we'll pick up from there.\n\n"
        "Truly yours,\n"
        "GeniML\n"
        "https://geniml.com"
    )
    REGISTRATION_REQUIRED_REPLY_HTML = (
        "<p>Thanks for reaching out. To get personalized coaching from GeniML "
        "(Genius in the Machine), you'll need to register first.</p>\n"
        "<p>Learn more about the service and sign up here:</p>\n"
        "<p><a href=\"https://geniml.com\">https://geniml.com</a></p>\n"
        "<p>After you've registered, reply to this email and we'll pick up from there.</p>\n"
        "<p>Truly yours,<br>GeniML<br>"
        "<a href=\"https://geniml.com\">geniml.com</a></p>"
    )

    VERIFY_SUBJECT = "Verify to access your coaching insights"
    VERIFY_TEXT_TEMPLATE = (
        "To protect your privacy and prevent abuse, we verify email addresses before sending coaching responses.\n\n"
        "Verify your email by clicking this link:\n\n{verification_link}\n\n"
        "Link expires in {verify_token_ttl_minutes} minutes.\n\n"
        "If you didn't request this, you can safely ignore this email.\n\nSmartMail Coach"
    )
    VERIFY_HTML_TEMPLATE = """<html>
<body>
<p>To protect your privacy and prevent abuse, we verify email addresses before sending coaching responses.</p>
<p>Verify your email by clicking this link:</p>
<p><a href="{verification_link}">{verification_link}</a></p>
<p>Link expires in {verify_token_ttl_minutes} minutes.</p>
<p>If you didn't request this, you can safely ignore this email.</p>
<p>SmartMail Coach</p>
</body>
</html>"""

    RATE_LIMIT_SUBJECT = "SmartMail usage limit reached"
    RATE_LIMIT_TEXT = (
        "You've reached your SmartMail request limit for now.\n\n"
        "Please try again later. Your limit resets automatically each hour/day.\n\n"
        "SmartMail Coach"
    )
    RATE_LIMIT_HTML = """<html>
<body>
<p>You've reached your SmartMail request limit for now.</p>
<p>Please try again later. Your limit resets automatically each hour/day.</p>
<p>SmartMail Coach</p>
</body>
</html>"""

    PROFILE_COLLECTION_INTRO = (
        "Thanks - before I can coach effectively, I need a bit more context.\n\n"
        "Please reply with:\n"
    )
    PROFILE_COLLECTION_UNKNOWN_HINT = (
        'If any item is unknown right now, you can say "unknown" for that item.'
    )
    PROFILE_PROMPT_PRIMARY_GOAL = (
        "- Your primary goal (e.g., first marathon, improve 10k time)"
    )
    PROFILE_PROMPT_TIME_AVAILABILITY = (
        "- Your time availability (sessions/week and/or hours/week)"
    )
    PROFILE_PROMPT_EXPERIENCE_LEVEL = (
        "- Your experience level (beginner, intermediate, advanced, or unknown)"
    )
    PROFILE_PROMPT_CONSTRAINTS = (
        "- Any constraints (injury, schedule, equipment, medical, preference). Empty is okay."
    )

    READY_FOR_COACHING_BASE = (
        "✅ You're ready for coaching. Share your latest training question "
        "or session details and I'll help you plan next steps."
    )
    READY_FOR_COACHING_CONNECT_STRAVA = (
        "\n\nCONNECT STRAVA FOR MORE PERSONALIZED COACHING:\n"
        "{connect_link}\n"
        "Benefit: synced workouts improve load and recovery guidance."
    )

    REPLY_WRAPPER_SEPARATOR = "---"
    REPLY_WRAPPER_FROM = "From"
    REPLY_WRAPPER_SENT = "Sent"
    REPLY_WRAPPER_TO = "To"
    REPLY_WRAPPER_CC = "CC"
    REPLY_WRAPPER_SUBJECT = "Subject"

    FALLBACK_AI_ERROR_REPLY = "I'm sorry, but I couldn't generate a response at this time."

    @staticmethod
    def render_verify_email(
        verification_link: str, verify_token_ttl_minutes: int
    ) -> Dict[str, str]:
        return {
            "subject": EmailCopy.VERIFY_SUBJECT,
            "text": EmailCopy.VERIFY_TEXT_TEMPLATE.format(
                verification_link=verification_link,
                verify_token_ttl_minutes=verify_token_ttl_minutes,
            ),
            "html": EmailCopy.VERIFY_HTML_TEMPLATE.format(
                verification_link=verification_link,
                verify_token_ttl_minutes=verify_token_ttl_minutes,
            ),
        }

    @staticmethod
    def build_profile_collection_lines(missing_fields: List[str]) -> List[str]:
        lines: List[str] = []
        if "primary_goal" in missing_fields:
            lines.append(EmailCopy.PROFILE_PROMPT_PRIMARY_GOAL)
        if "time_availability" in missing_fields:
            lines.append(EmailCopy.PROFILE_PROMPT_TIME_AVAILABILITY)
        if "experience_level" in missing_fields:
            lines.append(EmailCopy.PROFILE_PROMPT_EXPERIENCE_LEVEL)
        if "constraints" in missing_fields:
            lines.append(EmailCopy.PROFILE_PROMPT_CONSTRAINTS)
        return lines


class AICopy:
    """AI-generated content prompts and AI-only post-processing strings."""

    REPLY_SYSTEM_PROMPT = (
        "You are an AI assistant that writes natural, friendly, and conversational replies to user emails as part of an ongoing email thread. "
        "The emails are shown in reverse-chronological order (latest message at the top). To understand the conversation correctly, "
        "**you must read the messages from bottom to top** (oldest to newest). Your primary task is to identify the latest user question or intent "
        "and craft a warm, concise, and helpful response that continues the conversation fluidly.\n\n"
        "DO:\n"
        "- Focus on the most recent message at the top while using the full context below to inform your reply.\n"
        "- Match the tone of the sender: keep it casual for informal emails, and provide more structure and depth for serious or high-stakes inquiries.\n"
        "- Acknowledge the user's intent naturally—avoid repeating their message, and instead build on it to move the conversation forward.\n"
        "- Keep responses short, clear, and engaging—like a thoughtful human assistant would.\n"
        "- Ask for clarification if the user's message is vague or ambiguous.\n\n"
        "DO NOT:\n"
        "- Greet the user again (e.g., 'Hi there,' 'Hope you're well')—this is a thread.\n"
        "- Summarize previous messages or repeat earlier context unless asked explicitly.\n"
        "- Use robotic, formal, or overly verbose language.\n"
        "- Use phrases like 'Extracted Question' or 'Here is your response.'\n\n"
        "Your tone should be warm and conversational. Focus on clarity, empathy, and being genuinely helpful while respecting the context of an ongoing thread."
    )

    INVITE_SYSTEM_PROMPT = (
        "You must inform the user that they are not registered and cannot receive a response. "
        "Be polite, acknowledge their email, and direct them to register at [https://geniml.com]. "
        "Do not repeat the link more than once. End the response by inviting them to ask again after registration."
    )

    INTENTION_CHECK_SYSTEM_PROMPT = (
        "You are an intelligent email assistant analyzing the latest email in a thread to determine if an AI-generated "
        "response is necessary. Only evaluate content **until the first occurrence of common delimiters** such as `---`, `FROM`, `TO`, or `SUBJECT`, "
        "which indicate the start of previous messages. Do not analyze the full thread.\n\n"
        "Reply with ONLY `true` (if AI should respond) or `false` (if AI should NOT respond). No explanations.\n\n"
        "**Respond `true` if the latest email:**\n"
        "- Contains a clear, AI-answerable question.\n"
        "- Explicitly requests AI's help, advice, or factual input.\n"
        "- Introduces a new topic or request that AI has not yet addressed.\n\n"
        "**Respond `false` if the latest email:**\n"
        "- Is part of a human-to-human conversation without requesting AI input.\n"
        "- Replies to AI's previous response without adding a new question or request.\n"
        "- Mentions AI but does not ask for assistance.\n"
        "- Is a confirmation, acknowledgment, or casual remark (e.g., 'Thanks!', 'Got it!').\n"
        "- Is redundant, meaning AI has already answered a similar query in one of the last three messages."
    )

    PROFILE_EXTRACTION_SYSTEM_PROMPT = (
        "You are a personal coach assistant that reads user's email and extracts ONLY the user's "
        "training context needed for coaching. The email may contain a thread in reverse chronological order. You must read the thread from bottom to top to best capture the user's training goal and intent.\n\n"
        "Return a single JSON object with up to these keys:\n"
        "- primary_goal: string | null\n"
        "- time_availability: object | null\n"
        "  - sessions_per_week: integer | null\n"
        "  - hours_per_week: number | null\n"
        "- experience_level: \"beginner\" | \"intermediate\" | \"advanced\" | \"unknown\"\n"
        "- experience_level_note: string | null\n"
        "- constraints: array | null\n"
        "  - each item: {type, summary, severity, active}\n"
        "  - type: \"injury\" | \"schedule\" | \"equipment\" | \"medical\" | \"preference\" | \"other\"\n"
        "  - severity: \"low\" | \"medium\" | \"high\"\n"
        "  - active: boolean\n\n"
        "Rules:\n"
        "- If experience level is unclear, set it to \"unknown\".\n"
        "- Constraints may be an empty array.\n"
        "- Do NOT infer details that are not clearly stated.\n"
        "- If a field is not mentioned, either omit it or set it to null.\n"
        "- The response MUST be valid JSON and MUST NOT contain any explanatory text."
    )

    RESPONSE_SIGNATURE_HTML = (
        "<br><br>Truly yours,<br>"
        "GeniML<br>"
        '<a href="https://geniml.com">geniml.com</a>'
    )
    RESPONSE_DISCLAIMER_HTML = (
        "<br><br><hr><small>"
        "Disclaimer: This response is AI-generated and may contain errors. "
        "Please verify all information provided. For feedback, email "
        '<a href="mailto:feedback@geniml.com">feedback@geniml.com</a>.'
        "</small><hr>"
    )
    INVITE_SIGNATURE_TEXT = "\n\nTruly yours,\nGeniML\nhttps://geniml.com"


class AIEvaluationCopy:
    """AI reply-evaluation prompts (not user-facing outbound mail text)."""

    EVAL_SYSTEM_PROMPT_TEMPLATE = (
        "You are a strict evaluator of email replies. Here is the email thread. "
        "Read it in reverse chronological order to understand the entire thread:\n\n{original_email}\n\n"
        "Here is the suggested reply from the agent:\n\n{ai_response}\n\n"
        "Please do the following:\n"
        "1. Assign a score from 1-5 for each of the following categories: Accuracy, Relevance, Clarity, Helpfulness, and Tone.\n"
        "2. For each category, provide one or two sentences explaining why you gave that score.\n\n"
        "Respond in JSON only, with the following structure:\n"
        "{{\n"
        '  "accuracy_score": X,\n'
        '  "accuracy_justification": "...",\n'
        '  "relevance_score": X,\n'
        '  "relevance_justification": "...",\n'
        '  "clarity_score": X,\n'
        '  "clarity_justification": "...",\n'
        '  "helpfulness_score": X,\n'
        '  "helpfulness_justification": "...",\n'
        '  "tone_score": X,\n'
        '  "tone_justification": "..."\n'
        "}}"
    )
