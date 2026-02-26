# Test Coverage

## Summary

| Layer | Test file | Coverage | Notes |
|-------|------------|----------|--------|
| **E2E / handler** | `test_verified_quota_gate.py` | Handler flow (parse → auth → rate limit → business → send) | Mocks at module boundaries; quota + notice tests |
| **Rate limits (dynamodb_models)** | `test_verified_quota_gate.py` | `claim_verified_quota_slot`, `atomically_set_verified_notice_cooldown_if_allowed` | In-memory Dynamo; concurrency tests |
| **Profile** | `test_profile.py` | Extractors, `parse_profile_updates_from_email`, `get_missing_required_profile_fields`, `build_profile_collection_reply` | No DynamoDB/LLM |
| **Coaching** | `test_coaching.py` | `build_profile_gated_reply` (Dynamo/merge mocked) | Skipped if boto3/botocore not installed |
| **Business** | `test_business.py` | `get_reply_for_inbound` delegates to coaching | Skipped if boto3/botocore not installed |
| **Email parsing** | `test_email_processor.py` | `parse_sns_event`, `decode_email_content`, `clean_email_body` | No network |

## Running tests

From `email_service/`:

```bash
# All tests (coaching/business skipped if boto not installed)
python3 -m unittest discover -v

# Quota + handler (E2E-style) only
python3 -m unittest test_verified_quota_gate -v

# Unit tests that don't need boto
python3 -m unittest test_profile test_email_processor -v
```

With boto3/botocore installed (e.g. in Lambda or a venv), coaching and business tests run as well.

## Coverage by component

### In isolation (unit)

- **config** – Not tested; pure env/constants. Optional: test default values.
- **auth** – `is_registered`, `handle_unverified_sender`, cooldown, `VerificationEmailSender` – *no dedicated tests*. E2E only via handler (unverified path returns without sending reply). Add `test_auth.py` to test `is_registered` with mocked Dynamo and `handle_unverified_sender` with mocked token/email.
- **rate_limits** – Covered indirectly: `claim_verified_quota_slot` and notice cooldown in `dynamodb_models` are tested in `test_verified_quota_gate`; handler tests patch `rate_limits.claim_verified_quota_slot` and `RateLimitNoticeSender`.
- **profile** – ✅ `test_profile.py`: extractors, parse, get_missing, build_reply.
- **coaching** – ✅ `test_coaching.py` (with boto): build_profile_gated_reply with mocked get_coach_profile/merge.
- **business** – ✅ `test_business.py` (with boto): get_reply_for_inbound delegates to coaching.
- **openai_responder** – *No tests*. Add `test_openai_responder.py` with mocked `openai.OpenAI()` to test `generate_response`, `should_ai_respond` (and intention prompt).
- **response_evaluator** – *No tests*. Add `test_response_evaluator.py` with mocked OpenAI and DynamoDB.
- **email_processor** – ✅ `test_email_processor.py`: parse_sns_event, decode, clean.
- **email_reply_sender** – *No dedicated tests*. E2E uses mocked `send_reply`. Add `test_email_reply_sender.py` to test `format_reply`, `filter_valid_recipients`, `get_geniml_email` in isolation; mock SES and ResponseEvaluation for `send_reply`.

### E2E (handler)

- **test_verified_quota_gate.VerifiedPathGateTests**:
  - `test_handler_success_calls_business_and_send_reply` – happy path: parse → verified → registered → quota ok → get_reply_for_inbound → send_reply.
  - `test_handler_blocks_verified_over_limit_before_reply` – quota block; send_reply not called.
  - `test_blocked_request_triggers_notice_first_time` – quota block + notice sent.
  - `test_subsequent_blocked_requests_within_cooldown_do_not_send_notice` – cooldown suppresses second notice.
  - `test_dynamo_error_fails_closed_and_attempts_notice_with_logging` – quota_check_error blocks and logs.
  - `test_concurrency_multiple_blocked_requests_only_one_notice_sent` – notice cooldown concurrency.

## Gaps to fill (recommended)

1. **auth** – `test_auth.py`: mock Dynamo for `is_registered`; mock `create_action_token` and `VerificationEmailSender` for `handle_unverified_sender` (cooldown path vs sent path).
2. **openai_responder** – `test_openai_responder.py`: mock `openai.OpenAI().chat.completions.create`; assert prompts and that `generate_response` / `should_ai_respond` return expected shapes.
3. **response_evaluator** – `test_response_evaluator.py`: mock OpenAI and DynamoDB; assert eval prompt and Dynamo put_item.
4. **email_reply_sender** – `test_email_reply_sender.py`: unit tests for `format_reply`, `filter_valid_recipients`, `get_geniml_email`; mock `ResponseEvaluation.evaluate_response` and SES for `send_reply`.

After adding these, you’ll have **isolation tests for every component** and **E2E coverage** for the handler (auth, rate limit, business, send).
