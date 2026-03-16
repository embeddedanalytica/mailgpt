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

    CONVERSATION_INTELLIGENCE_SYSTEM_PROMPT = (
        "Classify inbound athlete coaching message into exactly one primary intent.\n\n"
        "Return only data that matches the provided JSON schema.\n\n"
        "JSON schema:\n"
        "{\n"
        '  "intent": "check_in" | "question" | "plan_change_request" | "milestone_update" | "off_topic" | "safety_concern" | "availability_update",\n'
        '  "complexity_score": integer 1-5\n'
        "}\n\n"
        "Allowed intents:\n"
        "- check_in\n"
        "- question\n"
        "- plan_change_request\n"
        "- milestone_update\n"
        "- off_topic\n"
        "- safety_concern\n"
        "- availability_update\n\n"
        "Choose exactly one primary intent.\n\n"
        "Priority order for tie-breaking:\n"
        "off_topic > safety_concern > milestone_update > check_in > availability_update > plan_change_request > question\n\n"
        "Definitions:\n"
        "- off_topic: not meaningfully about training, recovery, health, or coaching logistics.\n"
        "- safety_concern: injury or illness concern where safe participation may be in question, especially limping, swelling, numbness, tingling, worsening pain, night pain, inability to bear weight, or a go/no-go training question with concerning symptoms.\n"
        "- milestone_update: mainly reports a result, race, test, PR, completed event, or objective performance change.\n"
        "- check_in: mainly reports how recent training or recovery went, without primarily asking for a new or modified plan.\n"
        "- availability_update: the main driver is schedule, travel, time, equipment, or access constraints that force reshaping the training week.\n"
        "- plan_change_request: asks to create or modify a workout, week, phase, focus, or intensity direction, when availability constraints are not the main driver.\n"
        "- question: primarily asks for explanation, clarification, or advice without requesting a plan rewrite and without safety escalation.\n\n"
        "- complexity_score must be an integer from 1 to 5, where 1 is very simple and 5 is highly nuanced, safety-sensitive, or requires more reasoning.\n"
        "Additional rules:\n"
        "- Classify based on the athlete's primary communicative goal, not every possible interpretation.\n"
        "- If the message contains both a report and a request, choose the intent that best reflects what the athlete wants the coach to do next.\n"
        "- If both availability_update and plan_change_request are present, choose availability_update when time, travel, equipment, or schedule constraints are the main reason for replanning.\n"
        "- If both check_in and plan_change_request are present, choose check_in only when the message is mostly a status report and the request is minor; otherwise choose the replan-related label.\n"
        "- Mild stable soreness or tightness without red-flag symptoms is not safety_concern by itself.\n"
        "- If the message asks whether it is safe to train and also includes red-flag symptoms, choose safety_concern.\n"
        "- Never invent labels outside the allowed intent list.\n"
        "- Output valid JSON only. No markdown, no prose, no extra keys."
    )

    SESSION_CHECKIN_EXTRACTION_SYSTEM_PROMPT = (
        "You extract structured regular check-in fields for a deterministic coaching rule engine.\n\n"
        "Output JSON only (no markdown, no prose).\n"
        "Use null for unknown values; do not invent facts.\n"
        "Use exact enum tokens for categorical fields.\n\n"
        "Expected fields may include:\n"
        "- risk_candidate\n"
        "- event_date\n"
        "- hard_return_context\n"
        "- return_context\n"
        "- has_upcoming_event\n"
        "- performance_intent_this_week\n"
        "- returning_from_break\n"
        "- recent_illness\n"
        "- break_days\n"
        "- explicit_main_sport_switch_request\n"
        "- performance_chase_active\n"
        "- experience_level\n"
        "- time_bucket\n"
        "- main_sport_current\n"
        "- days_available\n"
        "- week_chaotic\n"
        "- missed_sessions_count\n"
        "- pain_score\n"
        "- pain_sharp\n"
        "- pain_sudden_onset\n"
        "- swelling_present\n"
        "- numbness_or_tingling\n"
        "- pain_affects_form\n"
        "- night_pain\n"
        "- pain_worsening\n"
        "- energy_score\n"
        "- stress_score\n"
        "- sleep_score\n"
        "- heavy_fatigue\n"
        "- structure_preference\n"
        "- schedule_variability\n"
        "- equipment_access\n"
        "- field_confidence\n"
        "- free_text_summary\n\n"
        "Safety rule: if severe acute risk is present, set risk_candidate=red_b.\n"
        "The response MUST be valid JSON object."
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
