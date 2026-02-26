import copy
import os
import sys
import threading
import types
import unittest
from unittest import mock

# Make tests runnable even when boto/openai aren't installed locally.
if "botocore.exceptions" not in sys.modules:
    botocore_module = types.ModuleType("botocore")
    botocore_exceptions_module = types.ModuleType("botocore.exceptions")

    class ClientError(Exception):
        def __init__(self, error_response, operation_name):
            super().__init__(operation_name)
            self.response = error_response

    botocore_exceptions_module.ClientError = ClientError
    botocore_module.exceptions = botocore_exceptions_module
    sys.modules["botocore"] = botocore_module
    sys.modules["botocore.exceptions"] = botocore_exceptions_module
else:
    from botocore.exceptions import ClientError  # type: ignore

if "boto3" not in sys.modules:
    boto3_module = types.ModuleType("boto3")

    class _Boto3Stub:
        def get_item(self, *args, **kwargs):
            return {}

        def update_item(self, *args, **kwargs):
            return {}

    class _Boto3ResourceStub:
        def Table(self, _name):  # noqa: N802
            return _Boto3Stub()

    class _Boto3ClientStub:
        def send_email(self, *args, **kwargs):
            return {"MessageId": "stub-message-id"}

        def send_raw_email(self, *args, **kwargs):
            return {"MessageId": "stub-message-id"}

    def _resource(*args, **kwargs):
        return _Boto3ResourceStub()

    def _client(*args, **kwargs):
        return _Boto3ClientStub()

    boto3_module.resource = _resource
    boto3_module.client = _client
    sys.modules["boto3"] = boto3_module

if "openai" not in sys.modules:
    openai_module = types.ModuleType("openai")

    class _OpenAIStub:
        class chat:
            class completions:
                @staticmethod
                def create(*args, **kwargs):
                    class _Choice:
                        class _Message:
                            content = "stub"

                        message = _Message()

                    class _Response:
                        choices = [_Choice()]

                    return _Response()

    openai_module.api_key = None
    openai_module.OpenAI = _OpenAIStub
    sys.modules["openai"] = openai_module

# Ensure sibling modules can be imported when run from repo root.
sys.path.insert(0, os.path.dirname(__file__))

import app
import dynamodb_models
import rate_limits


class _InMemoryRateLimitsTable:
    def __init__(self):
        self._lock = threading.Lock()
        self._items = {}

    def get_item(self, Key, ConsistentRead=False):  # noqa: N803
        with self._lock:
            email = Key["email"]
            if email not in self._items:
                return {}
            return {"Item": copy.deepcopy(self._items[email])}

    def update_item(  # noqa: N803
        self,
        Key,
        UpdateExpression=None,
        ConditionExpression=None,
        ExpressionAttributeValues=None,
        ReturnValues=None,
    ):
        with self._lock:
            email = Key["email"]
            item = copy.deepcopy(self._items.get(email, {}))
            values = ExpressionAttributeValues or {}

            # Minimal condition evaluator for claim_verified_quota_slot optimistic lock.
            if any(
                token in values
                for token in (
                    ":prev_hour_bucket",
                    ":prev_day_bucket",
                    ":prev_hour_count",
                    ":prev_day_count",
                )
            ):
                for attr_name, token in (
                    ("hour_bucket", ":prev_hour_bucket"),
                    ("day_bucket", ":prev_day_bucket"),
                    ("verified_requests_hour", ":prev_hour_count"),
                    ("verified_requests_day", ":prev_day_count"),
                ):
                    if token in values:
                        if attr_name not in item or item[attr_name] != values[token]:
                            raise ClientError(
                                {"Error": {"Code": "ConditionalCheckFailedException"}},
                                "UpdateItem",
                            )
                    elif attr_name in item:
                        raise ClientError(
                            {"Error": {"Code": "ConditionalCheckFailedException"}},
                            "UpdateItem",
                        )

            # Minimal condition evaluator for notice cooldown claim.
            if ":cooldown_until" in values and ":now" in values:
                active_until = item.get("verified_rate_limit_notice_cooldown_until")
                if active_until is not None and active_until > values[":now"]:
                    raise ClientError(
                        {"Error": {"Code": "ConditionalCheckFailedException"}},
                        "UpdateItem",
                    )

            if ":new_hour_bucket" in values:
                item["hour_bucket"] = values[":new_hour_bucket"]
            if ":new_day_bucket" in values:
                item["day_bucket"] = values[":new_day_bucket"]
            if ":new_hour_count" in values:
                item["verified_requests_hour"] = values[":new_hour_count"]
            if ":new_day_count" in values:
                item["verified_requests_day"] = values[":new_day_count"]
            if ":now" in values:
                item["last_verified_request_at"] = values[":now"]
            if ":cooldown_until" in values:
                item["verified_rate_limit_notice_cooldown_until"] = values[":cooldown_until"]
                item["last_rate_limit_notice_sent_at"] = values.get(":now")

            self._items[email] = item
            return {"Attributes": {}}


class _InMemoryDynamoResource:
    def __init__(self, table):
        self._table = table

    def Table(self, _name):  # noqa: N802
        return self._table


class VerifiedQuotaClaimTests(unittest.TestCase):
    def setUp(self):
        self.table = _InMemoryRateLimitsTable()
        self.patcher = mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _InMemoryDynamoResource(self.table),
        )
        self.patcher.start()

    def tearDown(self):
        self.patcher.stop()

    def test_under_limit_allowed(self):
        now_epoch = 1735732800  # 2025-01-01T12:00:00Z
        result = dynamodb_models.claim_verified_quota_slot(
            email="user@example.com",
            hourly_limit=5,
            daily_limit=10,
            now_epoch=now_epoch,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["hour_count"], 1)
        self.assertEqual(result["day_count"], 1)

    def test_hourly_limit_exceeded_blocked(self):
        now_epoch = 1735732800
        buckets = dynamodb_models._current_utc_buckets(now_epoch=now_epoch)
        self.table._items["user@example.com"] = {
            "email": "user@example.com",
            "hour_bucket": buckets["hour_bucket"],
            "day_bucket": buckets["day_bucket"],
            "verified_requests_hour": 2,
            "verified_requests_day": 2,
        }

        result = dynamodb_models.claim_verified_quota_slot(
            email="user@example.com",
            hourly_limit=2,
            daily_limit=10,
            now_epoch=now_epoch,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "hourly_limit_exceeded")

    def test_daily_limit_exceeded_blocked(self):
        now_epoch = 1735732800
        buckets = dynamodb_models._current_utc_buckets(now_epoch=now_epoch)
        self.table._items["user@example.com"] = {
            "email": "user@example.com",
            "hour_bucket": buckets["hour_bucket"],
            "day_bucket": buckets["day_bucket"],
            "verified_requests_hour": 1,
            "verified_requests_day": 3,
        }

        result = dynamodb_models.claim_verified_quota_slot(
            email="user@example.com",
            hourly_limit=10,
            daily_limit=3,
            now_epoch=now_epoch,
        )
        self.assertFalse(result["allowed"])
        self.assertEqual(result["reason"], "daily_limit_exceeded")

    def test_bucket_rollover_resets_and_allows(self):
        previous_hour_epoch = 1735732800  # 2025-01-01T12:00:00Z
        current_hour_epoch = 1735736400  # 2025-01-01T13:00:00Z
        old_buckets = dynamodb_models._current_utc_buckets(now_epoch=previous_hour_epoch)
        self.table._items["user@example.com"] = {
            "email": "user@example.com",
            "hour_bucket": old_buckets["hour_bucket"],
            "day_bucket": old_buckets["day_bucket"],
            "verified_requests_hour": 99,
            "verified_requests_day": 99,
        }

        result = dynamodb_models.claim_verified_quota_slot(
            email="user@example.com",
            hourly_limit=2,
            daily_limit=200,
            now_epoch=current_hour_epoch,
        )
        self.assertTrue(result["allowed"])
        self.assertEqual(result["hour_count"], 1)
        self.assertEqual(result["day_count"], 100)

        previous_day_epoch = 1735775400  # 2025-01-01T23:50:00Z
        current_day_epoch = 1735777200  # 2025-01-02T00:20:00Z
        old_day_buckets = dynamodb_models._current_utc_buckets(now_epoch=previous_day_epoch)
        self.table._items["dayroll@example.com"] = {
            "email": "dayroll@example.com",
            "hour_bucket": old_day_buckets["hour_bucket"],
            "day_bucket": old_day_buckets["day_bucket"],
            "verified_requests_hour": 9,
            "verified_requests_day": 9,
        }

        day_result = dynamodb_models.claim_verified_quota_slot(
            email="dayroll@example.com",
            hourly_limit=20,
            daily_limit=3,
            now_epoch=current_day_epoch,
        )
        self.assertTrue(day_result["allowed"])
        self.assertEqual(day_result["day_count"], 1)

    def test_concurrency_one_slot_allows_only_one(self):
        now_epoch = 1735732800
        buckets = dynamodb_models._current_utc_buckets(now_epoch=now_epoch)
        self.table._items["race@example.com"] = {
            "email": "race@example.com",
            "hour_bucket": buckets["hour_bucket"],
            "day_bucket": buckets["day_bucket"],
            "verified_requests_hour": 0,
            "verified_requests_day": 0,
        }

        results = []
        barrier = threading.Barrier(2)

        def _run_claim():
            barrier.wait()
            result = dynamodb_models.claim_verified_quota_slot(
                email="race@example.com",
                hourly_limit=1,
                daily_limit=1,
                now_epoch=now_epoch,
            )
            results.append(result)

        t1 = threading.Thread(target=_run_claim)
        t2 = threading.Thread(target=_run_claim)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        allowed_count = sum(1 for item in results if item["allowed"])
        self.assertEqual(allowed_count, 1)

    def test_notice_cooldown_concurrency_only_one_can_send(self):
        now_epoch = 1735732800
        results = []
        barrier = threading.Barrier(2)

        def _run_notice_claim():
            barrier.wait()
            result = dynamodb_models.atomically_set_verified_notice_cooldown_if_allowed(
                email="notice-race@example.com",
                cooldown_until=now_epoch + 3600,
                now=now_epoch,
            )
            results.append(result)

        t1 = threading.Thread(target=_run_notice_claim)
        t2 = threading.Thread(target=_run_notice_claim)
        t1.start()
        t2.start()
        t1.join()
        t2.join()

        send_count = sum(1 for item in results if item["send_notice"])
        self.assertEqual(send_count, 1)


class VerifiedPathGateTests(unittest.TestCase):
    def _verified_email_data(self):
        return {
            "sender": "verified@example.com",
            "recipient": "hello@geniml.com",
            "subject": "Need help",
            "body": "Question",
            "message_id": "msg-1",
            "date_received": "Wed, 1 Jan 2025 12:00:00 +0000",
            "to_recipients": ["hello@geniml.com"],
            "cc_recipients": [],
        }

    def test_handler_success_calls_business_and_send_reply(self):
        """E2E-style: verified, registered, under quota -> get_reply_for_inbound and send_reply called."""
        email_data = self._verified_email_data()
        with mock.patch.object(app.EmailProcessor, "parse_sns_event", return_value=email_data), \
            mock.patch.object(app, "is_verified", return_value=True), \
            mock.patch.object(app, "is_registered", return_value=True), \
            mock.patch.object(app, "check_verified_quota_or_block", return_value=None), \
            mock.patch.object(app, "get_reply_for_inbound", return_value="Reply body here") as get_reply_mock, \
            mock.patch.object(app.EmailReplySender, "send_reply", return_value="msg-123") as send_reply_mock:
            response = app.lambda_handler(event={"Records": []}, context=None)
        self.assertEqual(response["statusCode"], 200)
        self.assertIn("Reply sent!", response["body"])
        get_reply_mock.assert_called_once()
        send_reply_mock.assert_called_once_with(email_data, "Reply body here")

    def test_handler_blocks_verified_over_limit_before_reply(self):
        email_data = self._verified_email_data()
        block_response = {"statusCode": 200, "body": "Dropped (verified quota exceeded)"}

        with mock.patch.object(app.EmailProcessor, "parse_sns_event", return_value=email_data), \
            mock.patch.object(app, "is_verified", return_value=True), \
            mock.patch.object(app, "is_registered", return_value=True), \
            mock.patch.object(
                app,
                "check_verified_quota_or_block",
                return_value=block_response,
            ), \
            mock.patch.object(app.EmailReplySender, "send_reply") as send_reply_mock:
            response = app.lambda_handler(event={"Records": []}, context=None)

        self.assertEqual(response["statusCode"], 200)
        self.assertIn("Dropped", response["body"])
        send_reply_mock.assert_not_called()

    def test_blocked_request_triggers_notice_first_time(self):
        email_data = self._verified_email_data()

        with mock.patch.object(rate_limits, "SEND_RATE_LIMIT_NOTICE", True), \
            mock.patch.object(app.EmailProcessor, "parse_sns_event", return_value=email_data), \
            mock.patch.object(app, "is_verified", return_value=True), \
            mock.patch.object(app, "is_registered", return_value=True), \
            mock.patch.object(
                rate_limits,
                "claim_verified_quota_slot",
                return_value={"allowed": False, "reason": "hourly_limit_exceeded"},
            ), \
            mock.patch.object(
                rate_limits,
                "atomically_set_verified_notice_cooldown_if_allowed",
                return_value={"send_notice": True, "reason": "notice_allowed", "cooldown_until": 1234},
            ), \
            mock.patch.object(rate_limits.RateLimitNoticeSender, "send_rate_limit_notice", return_value=True) as send_notice_mock, \
            mock.patch.object(app.EmailReplySender, "send_reply") as send_reply_mock:
            response = app.lambda_handler(event={"Records": []}, context=None)

        self.assertEqual(response["statusCode"], 200)
        send_notice_mock.assert_called_once_with("verified@example.com")
        send_reply_mock.assert_not_called()

    def test_subsequent_blocked_requests_within_cooldown_do_not_send_notice(self):
        email_data = self._verified_email_data()

        with mock.patch.object(rate_limits, "SEND_RATE_LIMIT_NOTICE", True), \
            mock.patch.object(app.EmailProcessor, "parse_sns_event", return_value=email_data), \
            mock.patch.object(app, "is_verified", return_value=True), \
            mock.patch.object(app, "is_registered", return_value=True), \
            mock.patch.object(
                rate_limits,
                "claim_verified_quota_slot",
                return_value={"allowed": False, "reason": "daily_limit_exceeded"},
            ), \
            mock.patch.object(
                rate_limits,
                "atomically_set_verified_notice_cooldown_if_allowed",
                return_value={"send_notice": False, "reason": "notice_cooldown_active"},
            ), \
            mock.patch.object(rate_limits.RateLimitNoticeSender, "send_rate_limit_notice") as send_notice_mock:
            response = app.lambda_handler(event={"Records": []}, context=None)

        self.assertEqual(response["statusCode"], 200)
        send_notice_mock.assert_not_called()

    def test_dynamo_error_fails_closed_and_attempts_notice_with_logging(self):
        email_data = self._verified_email_data()

        with mock.patch.object(rate_limits, "SEND_RATE_LIMIT_NOTICE", True), \
            mock.patch.object(app.EmailProcessor, "parse_sns_event", return_value=email_data), \
            mock.patch.object(app, "is_verified", return_value=True), \
            mock.patch.object(app, "is_registered", return_value=True), \
            mock.patch.object(
                rate_limits,
                "claim_verified_quota_slot",
                return_value={"allowed": False, "reason": "quota_check_error"},
            ), \
            mock.patch.object(
                rate_limits,
                "atomically_set_verified_notice_cooldown_if_allowed",
                return_value={"send_notice": True, "reason": "notice_allowed", "cooldown_until": 999},
            ), \
            mock.patch.object(rate_limits.RateLimitNoticeSender, "send_rate_limit_notice", return_value=True) as send_notice_mock, \
            mock.patch.object(rate_limits.logger, "info") as rate_limit_log_mock, \
            mock.patch.object(app.EmailReplySender, "send_reply") as send_reply_mock:
            response = app.lambda_handler(event={"Records": []}, context=None)

        self.assertEqual(response["statusCode"], 200)
        self.assertIn("Dropped", response["body"])
        send_reply_mock.assert_not_called()
        send_notice_mock.assert_called_once_with("verified@example.com")
        logged_messages = " ".join(
            call[0][0] if call[0] else ""
            for call in rate_limit_log_mock.call_args_list
        )
        self.assertIn("quota_check_error", logged_messages)

    def test_concurrency_multiple_blocked_requests_only_one_notice_sent(self):
        results = []
        barrier = threading.Barrier(2)

        def _blocked_request():
            with mock.patch.object(rate_limits, "SEND_RATE_LIMIT_NOTICE", True):
                barrier.wait()
                results.append(rate_limits.maybe_send_rate_limit_notice(
                    "verified@example.com", "hourly_limit_exceeded"
                ))

        in_memory = _InMemoryRateLimitsTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _InMemoryDynamoResource(in_memory),
        ), mock.patch.object(
            rate_limits,
            "atomically_set_verified_notice_cooldown_if_allowed",
            wraps=dynamodb_models.atomically_set_verified_notice_cooldown_if_allowed,
        ):
            t1 = threading.Thread(target=_blocked_request)
            t2 = threading.Thread(target=_blocked_request)
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        sent_count = sum(1 for item in results if item.get("status") == "sent")
        self.assertEqual(sent_count, 1)

if __name__ == "__main__":
    unittest.main()
