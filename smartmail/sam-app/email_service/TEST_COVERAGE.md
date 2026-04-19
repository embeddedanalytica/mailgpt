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
| **Recommendation contract** | `test_recommendation_contract.py` | `AthleteState`, `Recommendation`, `RecommendationContext` validation + serialization | No network |
| **Data request policy** | `test_data_request_policy.py` | Liberal policy decisions, validation, hard-cap normalization | No network |
| **Connector gateway** | `test_connector_gateway.py` | Policy gating, provider dispatch, error handling | No network |

## Running tests

From the repo root, with `email_service` on `PYTHONPATH` (see merge bar in [`AGENTS.md`](../../../AGENTS.md#merge-bar)):

```bash
# All tests (coaching/business skipped if boto not installed)
PYTHONPATH=sam-app/email_service python3 -m unittest discover -v -s sam-app/tests/email_service -p "test_*.py"

# Quota + handler (E2E-style) only
PYTHONPATH=sam-app/email_service python3 -m unittest -v sam-app/tests/email_service/test_verified_quota_gate.py

# Unit tests that don't need boto
PYTHONPATH=sam-app/email_service python3 -m unittest -v \
  sam-app/tests/email_service/test_profile.py \
  sam-app/tests/email_service/test_email_processor.py \
  sam-app/tests/email_service/test_recommendation_contract.py \
  sam-app/tests/email_service/test_data_request_policy.py \
  sam-app/tests/email_service/test_connector_gateway.py
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
- **skills/planner workflow runners** – ✅ `test_planner_skill_workflows.py`: conversation intelligence, profile extraction, and session-checkin extraction success/failure paths.
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
2. **response_evaluator** – `test_response_evaluator.py`: mock OpenAI and DynamoDB; assert eval prompt and Dynamo put_item.
3. **email_reply_sender** – `test_email_reply_sender.py`: unit tests for `format_reply`, `filter_valid_recipients`, `get_geniml_email`; mock `ResponseEvaluation.evaluate_response` and SES for `send_reply`.

After adding these, you’ll have **isolation tests for every component** and **E2E coverage** for the handler (auth, rate limit, business, send).
