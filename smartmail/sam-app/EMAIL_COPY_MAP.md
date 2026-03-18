# Email Copy Map

This map points to the source of truth for outbound user-facing email copy and skill-owned LLM prompt text.

## User-Facing Outbound Email Copy

- Python service transactional copy registry: `email_service/email_copy.py` (`EmailCopy`)
- Registration lambda copy registry: `email_registration/email_copy.mjs` (`EMAIL_COPY`)

### Scenarios and keys

1. Registration required reply (unregistered sender)
- Keys:
  - `EmailCopy.REGISTRATION_REQUIRED_REPLY`
  - `EmailCopy.REGISTRATION_REQUIRED_REPLY_HTML`
- Used by: `email_service/app.py`

2. Verification email
- Keys:
  - `EmailCopy.VERIFY_SUBJECT`
  - `EmailCopy.VERIFY_TEXT_TEMPLATE`
  - `EmailCopy.VERIFY_HTML_TEMPLATE`
  - `EmailCopy.render_verify_email(...)`
- Used by: `email_service/auth.py`

3. Verified-user rate-limit notice
- Keys:
  - `EmailCopy.RATE_LIMIT_SUBJECT`
  - `EmailCopy.RATE_LIMIT_TEXT`
  - `EmailCopy.RATE_LIMIT_HTML`
- Used by: `email_service/rate_limits.py`

4. Reply wrapper formatting around outbound thread replies
- Keys:
  - `EmailCopy.REPLY_WRAPPER_SEPARATOR`
  - `EmailCopy.REPLY_WRAPPER_FROM`
  - `EmailCopy.REPLY_WRAPPER_SENT`
  - `EmailCopy.REPLY_WRAPPER_TO`
  - `EmailCopy.REPLY_WRAPPER_CC`
  - `EmailCopy.REPLY_WRAPPER_SUBJECT`
- Used by: `email_service/email_reply_sender.py`

5. Generic fallback text for retired legacy path
- Key:
  - `EmailCopy.FALLBACK_AI_ERROR_REPLY`

6. Waitlist/registration welcome email
- Keys:
  - `EMAIL_COPY.welcome.subject`
  - `EMAIL_COPY.welcome.text`
  - `EMAIL_COPY.welcome.source`
- Used by: `email_registration/app.mjs`

## Skill-Owned Communication Copy and Prompts

### Response-generation skill

- Clarification question copy helper:
  - `skills/response_generation/communication_copy.py`
  - `build_clarification_questions(...)`
- Final email generation prompt:
  - `skills/response_generation/prompt.py`
- Non-registered invite prompt/signature:
  - `skills/response_generation/non_registered_prompt.py`
- Evaluation prompt template:
  - `skills/response_generation/evaluation_prompt.py`

### Planner skill

- Conversation-intelligence prompt/schema/validator/runner:
  - `skills/planner/conversation_intelligence_*`
- Profile-extraction prompt/schema/validator/runner:
  - `skills/planner/profile_extraction_*`
- Session-checkin extraction prompt/schema/validator/runner:
  - `skills/planner/session_checkin_extraction_*`

## Compatibility Note

`email_service/openai_responder.py` is now a compatibility shim only. Active LLM prompt ownership is in skill packages.
