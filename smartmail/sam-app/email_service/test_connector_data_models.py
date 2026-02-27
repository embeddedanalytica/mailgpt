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
    sys.modules["boto3"] = boto3_module

import dynamodb_models


class _AthleteIdTable:
    def update_item(self, **kwargs):
        return {"Attributes": {"athlete_id": "ath_fixed123"}}


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
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: _AthleteIdTable()}),
        ):
            athlete_id = dynamodb_models.ensure_athlete_id("user@example.com")

        self.assertEqual(athlete_id, "ath_fixed123")

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


if __name__ == "__main__":
    unittest.main()
