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

        def get_item(self, *args, **kwargs):
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


class _ProgressTable:
    def __init__(self):
        self.last_update = None
        self.last_put = None

    def update_item(self, **kwargs):
        self.last_update = kwargs
        return {}

    def put_item(self, **kwargs):
        self.last_put = kwargs["Item"]
        return {}

    def get_item(self, **kwargs):
        return {"Item": self.last_put} if self.last_put else {}


class _SnapshotsTable:
    def __init__(self):
        self.items = []
        self.keys = set()

    def put_item(self, **kwargs):
        item = kwargs["Item"]
        snapshot_key = item.get("snapshot_key")
        if snapshot_key in self.keys and kwargs.get("ConditionExpression"):
            from botocore.exceptions import ClientError

            raise ClientError(
                {"Error": {"Code": "ConditionalCheckFailedException", "Message": "duplicate"}},
                "PutItem",
            )
        self.keys.add(snapshot_key)
        self.items.append(item)
        return {}


class _RoutingDynamo:
    def __init__(self, tables):
        self.tables = tables

    def Table(self, name):  # noqa: N802
        return self.tables[name]


class TestProgressSnapshotModels(unittest.TestCase):
    def test_ensure_progress_snapshot_exists_writes_defaults(self):
        progress = _ProgressTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.PROGRESS_SNAPSHOTS_TABLE: progress}),
        ):
            ok = dynamodb_models.ensure_progress_snapshot_exists("ath_1")

        self.assertTrue(ok)
        self.assertIsNotNone(progress.last_update)
        values = progress.last_update["ExpressionAttributeValues"]
        self.assertEqual(values[":last_activity_type"], "unknown")
        self.assertEqual(values[":last_7d_activity_count"], 0)

    def test_put_manual_activity_snapshot_writes_and_recomputes(self):
        snapshots = _SnapshotsTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.MANUAL_ACTIVITY_SNAPSHOTS_TABLE: snapshots}),
        ), mock.patch.object(dynamodb_models, "recompute_progress_snapshot", return_value=True) as recompute:
            ok = dynamodb_models.put_manual_activity_snapshot(
                athlete_id="ath_1",
                activity_type="running",
                timestamp=1735732800,
                duration="45m",
                key_metric="distance:8km",
                subjective_feedback="felt good",
                subjective_state={"energy": "high", "soreness": "low", "sleep": "good"},
            )

        self.assertTrue(ok)
        self.assertEqual(len(snapshots.items), 1)
        self.assertEqual(snapshots.items[0]["source"], "manual")
        recompute.assert_called_once()

    def test_put_manual_activity_snapshot_is_idempotent_on_same_event_id(self):
        snapshots = _SnapshotsTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.MANUAL_ACTIVITY_SNAPSHOTS_TABLE: snapshots}),
        ), mock.patch.object(dynamodb_models, "recompute_progress_snapshot", return_value=True):
            first = dynamodb_models.put_manual_activity_snapshot(
                athlete_id="ath_1",
                activity_type="running",
                timestamp=1735732800,
                snapshot_event_id="msg-1",
            )
            second = dynamodb_models.put_manual_activity_snapshot(
                athlete_id="ath_1",
                activity_type="running",
                timestamp=1735732800,
                snapshot_event_id="msg-1",
            )

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(len(snapshots.items), 1)

    def test_put_manual_activity_snapshot_allows_same_timestamp_different_event_ids(self):
        snapshots = _SnapshotsTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.MANUAL_ACTIVITY_SNAPSHOTS_TABLE: snapshots}),
        ), mock.patch.object(dynamodb_models, "recompute_progress_snapshot", return_value=True):
            first = dynamodb_models.put_manual_activity_snapshot(
                athlete_id="ath_1",
                activity_type="running",
                timestamp=1735732800,
                snapshot_event_id="msg-1",
            )
            second = dynamodb_models.put_manual_activity_snapshot(
                athlete_id="ath_1",
                activity_type="cycling",
                timestamp=1735732800,
                snapshot_event_id="msg-2",
            )

        self.assertTrue(first)
        self.assertTrue(second)
        self.assertEqual(len(snapshots.items), 2)

    def test_recompute_progress_snapshot_writes_aggregate(self):
        progress = _ProgressTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.PROGRESS_SNAPSHOTS_TABLE: progress}),
        ), mock.patch.object(
            dynamodb_models,
            "_latest_manual_snapshot",
            return_value={
                "timestamp": 1735732800,
                "activity_type": "running",
                "subjective_state": {"energy": "ok", "soreness": "medium", "sleep": "good"},
            },
        ), mock.patch.object(
            dynamodb_models, "_count_recent_snapshots", side_effect=[3, 5]
        ), mock.patch.object(
            dynamodb_models, "_trend_direction", return_value="improving"
        ):
            ok = dynamodb_models.recompute_progress_snapshot("ath_1", now_epoch=1735732900)

        self.assertTrue(ok)
        self.assertIsNotNone(progress.last_put)
        self.assertEqual(progress.last_put["last_7d_activity_count"], 3)
        self.assertEqual(progress.last_put["trend_direction"], "improving")
        self.assertEqual(progress.last_put["goal_alignment"], "on_track")

    def test_normalize_progress_snapshot_repairs_sparse_record(self):
        normalized = dynamodb_models.normalize_progress_snapshot(
            {
                "athlete_id": "ath_1",
                "last_activity_type": "",
                "consistency_status": "broken",
                "trend_direction": "not-valid",
                "goal_alignment": "weird",
                "last_reported_energy": "meh",
                "updated_at": "bad",
            },
            athlete_id="ath_1",
        )
        self.assertEqual(normalized["last_activity_type"], "unknown")
        self.assertEqual(normalized["consistency_status"], "low")
        self.assertEqual(normalized["trend_direction"], "unknown")
        self.assertEqual(normalized["goal_alignment"], "unknown")
        self.assertEqual(normalized["last_reported_energy"], "unknown")
        self.assertIn(normalized["data_quality"], {"low", "medium", "high"})


if __name__ == "__main__":
    unittest.main()
