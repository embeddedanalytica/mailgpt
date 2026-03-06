import sys
import types
import unittest
from unittest import mock

# Make tests runnable even when boto/botocore are not installed locally.
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

from botocore.exceptions import ClientError

if "boto3" not in sys.modules:
    boto3_module = types.ModuleType("boto3")
    dynamodb_module = types.ModuleType("boto3.dynamodb")
    dynamodb_conditions_module = types.ModuleType("boto3.dynamodb.conditions")
    dynamodb_types_module = types.ModuleType("boto3.dynamodb.types")

    class _KeyCondition:
        def between(self, *_args, **_kwargs):
            return self

        def eq(self, *_args, **_kwargs):
            return self

        def __and__(self, _other):
            return self

    class Key:
        def __init__(self, _name):
            pass

        def eq(self, *_args, **_kwargs):
            return _KeyCondition()

    class TypeSerializer:
        def serialize(self, value):
            return {"S": str(value)}

    class _Boto3StubTable:
        def update_item(self, *args, **kwargs):
            return {}

        def put_item(self, *args, **kwargs):
            return {}

    class _Boto3StubResource:
        def Table(self, _name):  # noqa: N802
            return _Boto3StubTable()

    def _resource(*args, **kwargs):
        return _Boto3StubResource()

    boto3_module.resource = _resource
    class _Boto3ClientStub:
        def send_email(self, *args, **kwargs):
            return {"MessageId": "stub-message-id"}

        def send_raw_email(self, *args, **kwargs):
            return {"MessageId": "stub-message-id"}

    boto3_module.client = lambda *args, **kwargs: _Boto3ClientStub()
    dynamodb_conditions_module.Key = Key
    dynamodb_types_module.TypeSerializer = TypeSerializer
    dynamodb_module.conditions = dynamodb_conditions_module
    dynamodb_module.types = dynamodb_types_module
    sys.modules["boto3"] = boto3_module
    sys.modules["boto3.dynamodb"] = dynamodb_module
    sys.modules["boto3.dynamodb.conditions"] = dynamodb_conditions_module
    sys.modules["boto3.dynamodb.types"] = dynamodb_types_module

import dynamodb_models


class _AthleteIdentityTable:
    def __init__(self):
        self.last_key = None

    def update_item(self, **kwargs):
        self.last_key = kwargs.get("Key")
        return {"Attributes": {"athlete_id": "ath_fixed123"}}

    def get_item(self, **kwargs):
        self.last_key = kwargs.get("Key")
        return {"Item": {"athlete_id": "ath_fixed123"}}


class _ProfileSeedTable:
    def __init__(self):
        self.last_update_kwargs = None

    def update_item(self, **kwargs):
        self.last_update_kwargs = kwargs
        return {}


class _ActivitiesTable:
    def __init__(self):
        self.seen = set()

    def put_item(self, **kwargs):
        item = kwargs["Item"]
        key = (item["athlete_id"], item["provider_activity_key"])
        if key in self.seen:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.seen.add(key)
        return {}


class _RecommendationTable:
    def __init__(self):
        self.seen = set()

    def put_item(self, **kwargs):
        item = kwargs["Item"]
        key = (item["athlete_id"], item["created_at"])
        if key in self.seen:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.seen.add(key)
        return {}


class _ConversationIntelligenceTable:
    def __init__(self):
        self.seen = set()

    def put_item(self, **kwargs):
        item = kwargs["Item"]
        key = (item["athlete_id"], item["message_id"])
        if key in self.seen:
            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.seen.add(key)
        return {}


class _RoutingDynamo:
    def __init__(self, tables):
        self.tables = tables

    def Table(self, name):  # noqa: N802
        return self.tables[name]


class TestConnectorDataModels(unittest.TestCase):
    def test_ensure_athlete_id_returns_id(self):
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo(
                {
                    dynamodb_models.ATHLETE_IDENTITIES_TABLE: _AthleteIdentityTable(),
                    dynamodb_models.COACH_PROFILES_TABLE: _ProfileSeedTable(),
                }
            ),
        ):
            athlete_id = dynamodb_models.ensure_athlete_id("user@example.com")

        self.assertEqual(athlete_id, "ath_fixed123")

    def test_identity_helpers_canonicalize_email(self):
        identity_table = _AthleteIdentityTable()
        profile_table = _ProfileSeedTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo(
                {
                    dynamodb_models.ATHLETE_IDENTITIES_TABLE: identity_table,
                    dynamodb_models.COACH_PROFILES_TABLE: profile_table,
                }
            ),
        ):
            ensured = dynamodb_models.ensure_athlete_id_for_email(" User@Example.com ")
            looked_up = dynamodb_models.get_athlete_id_for_email("USER@example.COM ")

        self.assertEqual(ensured, "ath_fixed123")
        self.assertEqual(looked_up, "ath_fixed123")
        self.assertEqual(identity_table.last_key, {"email": "user@example.com"})
        self.assertEqual(
            profile_table.last_update_kwargs["ExpressionAttributeValues"][
                ":response_cadence_expectation"
            ],
            "unknown",
        )

    def test_put_normalized_activity_is_idempotent(self):
        activities = _ActivitiesTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.ACTIVITIES_TABLE: activities}),
        ):
            first = dynamodb_models.put_normalized_activity(
                athlete_id="ath_1",
                provider="strava",
                provider_activity_id="12345",
                activity_start_ts=1735732800,
                sport="running",
                metrics={"duration_s": 1800},
            )
            second = dynamodb_models.put_normalized_activity(
                athlete_id="ath_1",
                provider="strava",
                provider_activity_id="12345",
                activity_start_ts=1735732800,
                sport="running",
                metrics={"duration_s": 1800},
            )

        self.assertTrue(first["inserted"])
        self.assertEqual(first["reason"], "inserted")
        self.assertFalse(second["inserted"])
        self.assertEqual(second["reason"], "duplicate")

    def test_log_recommendation_collision_returns_false(self):
        recs = _RecommendationTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.RECOMMENDATION_LOG_TABLE: recs}),
        ):
            first = dynamodb_models.log_recommendation(
                athlete_id="ath_9",
                recommendation_text="Run easy tomorrow",
                evidence_window_days=7,
                created_at=1735732800,
            )
            second = dynamodb_models.log_recommendation(
                athlete_id="ath_9",
                recommendation_text="Run easy tomorrow",
                evidence_window_days=7,
                created_at=1735732800,
            )

        self.assertTrue(first)
        self.assertFalse(second)

    def test_put_message_intelligence_collision_returns_false(self):
        intelligence = _ConversationIntelligenceTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.CONVERSATION_INTELLIGENCE_TABLE: intelligence}),
        ):
            first = dynamodb_models.put_message_intelligence(
                athlete_id="ath_9",
                message_id="msg-1",
                intent="question",
                complexity_score=3,
                model_name="gpt-5-mini",
            )
            second = dynamodb_models.put_message_intelligence(
                athlete_id="ath_9",
                message_id="msg-1",
                intent="question",
                complexity_score=3,
                model_name="gpt-5-mini",
            )

        self.assertTrue(first)
        self.assertFalse(second)

    def test_normalize_profile_record_enforces_defaults(self):
        normalized = dynamodb_models.normalize_profile_record(
            {
                "primary_goal": "  ",
                "experience_level": "invalid",
                "constraints": "not-a-list",
            }
        )
        self.assertEqual(normalized["primary_goal"], "")
        self.assertEqual(normalized["experience_level"], "unknown")
        self.assertEqual(normalized["constraints"], [])
        self.assertEqual(normalized["time_availability"], {})
        self.assertEqual(normalized["goal_why"], "")
        self.assertEqual(normalized["success_definition"], "")
        self.assertEqual(normalized["barriers_summary"], "")
        self.assertEqual(normalized["lifestyle_baseline"], "")
        self.assertEqual(normalized["accountability_preferences"], "")
        self.assertEqual(normalized["feedback_style_preference"], "")
        self.assertEqual(normalized["coach_expectations"], "")
        self.assertEqual(normalized["response_cadence_expectation"], "unknown")

    def test_normalize_profile_record_enum_validation(self):
        invalid = dynamodb_models.normalize_profile_record(
            {"response_cadence_expectation": "sometime"}
        )
        valid = dynamodb_models.normalize_profile_record(
            {"response_cadence_expectation": "few_times_per_week"}
        )
        self.assertEqual(invalid["response_cadence_expectation"], "unknown")
        self.assertEqual(valid["response_cadence_expectation"], "few_times_per_week")

    def test_normalize_profile_record_truncates_new_text_fields(self):
        oversized = "x" * 1200
        normalized = dynamodb_models.normalize_profile_record(
            {
                "goal_why": oversized,
                "success_definition": oversized,
                "barriers_summary": oversized,
                "lifestyle_baseline": oversized,
                "accountability_preferences": oversized,
                "feedback_style_preference": oversized,
                "coach_expectations": oversized,
            }
        )
        self.assertEqual(len(normalized["goal_why"]), 1024)
        self.assertEqual(len(normalized["success_definition"]), 1024)
        self.assertEqual(len(normalized["barriers_summary"]), 1024)
        self.assertEqual(len(normalized["lifestyle_baseline"]), 1024)
        self.assertEqual(len(normalized["accountability_preferences"]), 1024)
        self.assertEqual(len(normalized["feedback_style_preference"]), 1024)
        self.assertEqual(len(normalized["coach_expectations"]), 1024)

    def test_normalize_profile_updates_new_fields(self):
        oversized = " y " * 700
        normalized = dynamodb_models.normalize_profile_updates(
            {
                "goal_why": oversized,
                "success_definition": "  finish healthy  ",
                "barriers_summary": " work + kids ",
                "lifestyle_baseline": 10,
                "accountability_preferences": "daily check-ins",
                "feedback_style_preference": "direct",
                "coach_expectations": "clear plan",
                "response_cadence_expectation": "invalid",
            }
        )
        self.assertEqual(len(normalized["goal_why"]), 1024)
        self.assertEqual(normalized["success_definition"], "finish healthy")
        self.assertEqual(normalized["barriers_summary"], "work + kids")
        self.assertNotIn("lifestyle_baseline", normalized)
        self.assertEqual(normalized["accountability_preferences"], "daily check-ins")
        self.assertEqual(normalized["feedback_style_preference"], "direct")
        self.assertEqual(normalized["coach_expectations"], "clear plan")
        self.assertEqual(normalized["response_cadence_expectation"], "unknown")

    def test_normalize_profile_updates_preserves_valid_enum(self):
        normalized = dynamodb_models.normalize_profile_updates(
            {"response_cadence_expectation": "daily"}
        )
        self.assertEqual(normalized["response_cadence_expectation"], "daily")

    def test_merge_coach_profile_fields_writes_sanitized_values(self):
        profile_table = _ProfileSeedTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            ok = dynamodb_models.merge_coach_profile_fields(
                "ath_123",
                {
                    "goal_why": "x" * 1100,
                    "response_cadence_expectation": "not_real",
                },
            )

        self.assertTrue(ok)
        values = profile_table.last_update_kwargs["ExpressionAttributeValues"]
        self.assertEqual(len(values[":v_goal_why"]), 1024)
        self.assertEqual(values[":v_response_cadence_expectation"], "unknown")


if __name__ == "__main__":
    unittest.main()
