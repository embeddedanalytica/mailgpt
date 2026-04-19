"""
Centralized outbound transactional email copy.

Update user-facing transactional email wording here.
"""
from typing import Dict


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

    REPLY_WRAPPER_SEPARATOR = "---"
    REPLY_WRAPPER_FROM = "From"
    REPLY_WRAPPER_SENT = "Sent"
    REPLY_WRAPPER_TO = "To"
    REPLY_WRAPPER_CC = "CC"
    REPLY_WRAPPER_SUBJECT = "Subject"

    FALLBACK_AI_ERROR_REPLY = (
        "I hit a temporary issue generating your full coaching reply.\n\n"
        "Please resend your note or reply with the single most important update or question, "
        "and I'll pick it up from there.\n\n"
        "SmartMail Coach"
    )

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
