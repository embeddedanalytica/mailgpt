# Email Copy Map

This map points to the single source of truth for outbound user-facing email copy and AI-generated email prompts.

## User-Facing Outbound Email Copy

- Python service copy registry: `email_service/email_copy.py` (`EmailCopy`)
- Registration lambda copy registry: `email_registration/email_copy.mjs` (`EMAIL_COPY`)

### Scenarios and keys

1. Registration required reply (unregistered sender)
- Key: `EmailCopy.REGISTRATION_REQUIRED_REPLY`
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

4. Profile detail prompts used to guide LLM clarification replies
- Keys:
  - `EmailCopy.build_profile_collection_lines(...)`
- Used by: `email_service/response_generation_assembly.py`

5. Reply wrapper formatting around outbound thread replies
- Keys:
  - `EmailCopy.REPLY_WRAPPER_SEPARATOR`
  - `EmailCopy.REPLY_WRAPPER_FROM`
  - `EmailCopy.REPLY_WRAPPER_SENT`
  - `EmailCopy.REPLY_WRAPPER_TO`
  - `EmailCopy.REPLY_WRAPPER_CC`
  - `EmailCopy.REPLY_WRAPPER_SUBJECT`
- Used by: `email_service/email_reply_sender.py`

6. Waitlist/registration welcome email
- Keys:
  - `EMAIL_COPY.welcome.subject`
  - `EMAIL_COPY.welcome.text`
  - `EMAIL_COPY.welcome.source`
- Used by: `email_registration/app.mjs`

## AI-Generated Email Copy (Prompts and Postfix)

- Key group: `AICopy` in `email_service/email_copy.py`
- Used by: `email_service/openai_responder.py`

Keys:
- `AICopy.REPLY_SYSTEM_PROMPT`
- `AICopy.INVITE_SYSTEM_PROMPT`
- `AICopy.INTENTION_CHECK_SYSTEM_PROMPT`
- `AICopy.PROFILE_EXTRACTION_SYSTEM_PROMPT`
- `AICopy.RESPONSE_SIGNATURE_HTML`
- `AICopy.RESPONSE_DISCLAIMER_HTML`
- `AICopy.INVITE_SIGNATURE_TEXT`
- `EmailCopy.FALLBACK_AI_ERROR_REPLY`

## AI Evaluation Prompt (Not user-facing outbound email body)

- Key: `AIEvaluationCopy.EVAL_SYSTEM_PROMPT_TEMPLATE`
- Used by: `email_service/response_evaluator.py`
