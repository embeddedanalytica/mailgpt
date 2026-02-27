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

    class _Boto3StubTable:
        def update_item(self, *args, **kwargs):
            return {}

    class _Boto3StubResource:
        def Table(self, _name):  # noqa: N802
            return _Boto3StubTable()

    def _resource(*args, **kwargs):
        return _Boto3StubResource()

    boto3_module.resource = _resource
    sys.modules["boto3"] = boto3_module

import dynamodb_models


class _CapturingTable:
    def __init__(self):
        self.last_update_kwargs = None

    def update_item(self, **kwargs):
        self.last_update_kwargs = kwargs
        return {}


class _CapturingDynamoResource:
    def __init__(self, table):
        self._table = table

    def Table(self, _name):  # noqa: N802
        return self._table


class TestCurrentPlanHelpers(unittest.TestCase):
    def test_build_default_current_plan_has_required_fields(self):
        plan = dynamodb_models._build_default_current_plan(goal="10k PR", now_epoch=1735732800)
        self.assertEqual(plan["goal"], "10k PR")
        self.assertEqual(plan["start_date"], "2025-01-01")
        self.assertEqual(plan["week_index"], 1)
        self.assertEqual(plan["revision"], 1)
        self.assertIsInstance(plan["sessions"], list)
        self.assertGreaterEqual(len(plan["sessions"]), 1)
        first_session = plan["sessions"][0]
        self.assertIn("date", first_session)
        self.assertIn("type", first_session)
        self.assertIn("target", first_session)

    def test_fetch_current_plan_summary_formats_required_fields(self):
        with mock.patch.object(dynamodb_models, "get_current_plan") as get_plan:
            get_plan.return_value = {
                "goal": "Build endurance",
                "start_date": "2026-02-20",
                "week_index": 3,
                "revision": 2,
                "sessions": [
                    {"date": "2026-02-21", "type": "easy", "target": "45 minutes"},
                    {"date": "2026-02-23", "type": "tempo", "target": "3 x 10 min"},
                ],
            }
            summary = dynamodb_models.fetch_current_plan_summary("user@example.com")

        self.assertIsNotNone(summary)
        self.assertIn("Goal: Build endurance", summary)
        self.assertIn("Start: 2026-02-20", summary)
        self.assertIn("Week: 3", summary)
        self.assertIn("Revision: 2", summary)
        self.assertIn("2026-02-21: easy (45 minutes)", summary)

    def test_ensure_current_plan_writes_default_when_missing(self):
        table = _CapturingTable()
        with mock.patch.object(dynamodb_models, "get_coach_profile") as get_profile, \
             mock.patch.object(
                 dynamodb_models,
                 "dynamodb",
                 _CapturingDynamoResource(table),
             ):
            get_profile.return_value = {}
            ok = dynamodb_models.ensure_current_plan(
                "new-user@example.com",
                fallback_goal="First marathon",
            )

        self.assertTrue(ok)
        self.assertIsNotNone(table.last_update_kwargs)
        values = table.last_update_kwargs["ExpressionAttributeValues"]
        self.assertIn(":current_plan", values)
        current_plan = values[":current_plan"]
        self.assertEqual(current_plan["goal"], "First marathon")
        self.assertIn("start_date", current_plan)
        self.assertEqual(current_plan["week_index"], 1)
        self.assertEqual(current_plan["revision"], 1)
        self.assertGreaterEqual(len(current_plan["sessions"]), 1)


if __name__ == "__main__":
    unittest.main()
