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

        def get_item(self, *args, **kwargs):
            return {}

    class _Boto3StubClient:
        def transact_write_items(self, **kwargs):
            return {}

    class _Boto3StubResource:
        def __init__(self):
            self.meta = types.SimpleNamespace(client=_Boto3StubClient())

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


class _CapturingTable:
    def __init__(self):
        self.last_update_kwargs = None

    def update_item(self, **kwargs):
        self.last_update_kwargs = kwargs
        return {}


class _RoutingDynamo:
    def __init__(self, tables, transact_side_effect=None):
        self.tables = tables
        self.meta = types.SimpleNamespace(
            client=types.SimpleNamespace(transact_write_items=self._transact_write_items)
        )
        self._transact_side_effect = transact_side_effect
        self.last_transact = None

    def Table(self, name):  # noqa: N802
        return self.tables[name]

    def _transact_write_items(self, **kwargs):
        self.last_transact = kwargs
        if self._transact_side_effect is not None:
            raise self._transact_side_effect
        return {}


class TestCurrentPlanHelpers(unittest.TestCase):
    def test_build_default_current_plan_has_required_fields(self):
        plan = dynamodb_models._build_default_current_plan(goal="10k PR", now_epoch=1735732800)
        self.assertEqual(plan["primary_goal"], "10k PR")
        self.assertEqual(plan["plan_version"], 1)
        self.assertEqual(plan["current_phase"], "base")
        self.assertEqual(plan["current_focus"], "Build consistency")
        self.assertEqual(plan["plan_status"], "active")

    def test_ensure_current_plan_writes_default_once(self):
        profile_table = _CapturingTable()
        dynamo = _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table})
        with mock.patch.object(dynamodb_models, "dynamodb", dynamo), mock.patch.object(
            dynamodb_models, "_get_raw_coach_profile", return_value={}
        ), mock.patch.object(dynamodb_models, "append_plan_history", return_value=True) as append_history:
            ok = dynamodb_models.ensure_current_plan("ath_new_1", fallback_goal="First marathon")

        self.assertTrue(ok)
        self.assertIsNotNone(profile_table.last_update_kwargs)
        append_history.assert_called_once()
        self.assertEqual(
            profile_table.last_update_kwargs["ConditionExpression"],
            "attribute_not_exists(#current_plan)",
        )

    def test_ensure_current_plan_existing_plan_is_idempotent(self):
        with mock.patch.object(
            dynamodb_models,
            "_get_raw_coach_profile",
            return_value={"current_plan": {"plan_version": 5}},
        ), mock.patch.object(dynamodb_models, "append_plan_history") as append_history:
            ok = dynamodb_models.ensure_current_plan("ath_1", fallback_goal="ignored")

        self.assertTrue(ok)
        append_history.assert_not_called()

    def test_update_current_plan_requires_logical_request_id(self):
        result = dynamodb_models.update_current_plan(
            "ath_1",
            updates={"current_phase": "build"},
            logical_request_id="",
        )
        self.assertEqual(result["status"], "validation_error")
        self.assertEqual(result["error_code"], "missing_logical_request_id")

    def test_update_current_plan_applies_transaction(self):
        profile_table = _CapturingTable()
        request_table = _CapturingTable()
        history_table = _CapturingTable()
        dynamo = _RoutingDynamo(
            {
                dynamodb_models.COACH_PROFILES_TABLE: profile_table,
                dynamodb_models.PLAN_UPDATE_REQUESTS_TABLE: request_table,
                dynamodb_models.PLAN_HISTORY_TABLE: history_table,
            }
        )

        with mock.patch.object(dynamodb_models, "dynamodb", dynamo), mock.patch.object(
            dynamodb_models,
            "get_current_plan",
            return_value={
                "primary_goal": "Marathon",
                "plan_version": 1,
                "current_phase": "base",
                "current_focus": "consistency",
                "next_recommended_session": {
                    "date": "2026-03-10",
                    "type": "easy",
                    "target": "40 minutes",
                },
                "plan_status": "active",
                "updated_at": 1735732800,
            },
        ):
            result = dynamodb_models.update_current_plan(
                "ath_1",
                {
                    "current_phase": "build",
                    "current_focus": "threshold",
                    "plan_status": "adjusting",
                },
                logical_request_id="req-123",
                rationale="phase_shift",
                changes_from_previous=["phase->build"],
            )

        self.assertEqual(result["status"], "applied")
        self.assertEqual(result["plan_version"], 2)
        self.assertIsNotNone(dynamo.last_transact)

    def test_update_current_plan_returns_idempotent_replay_for_same_payload(self):
        collision = ClientError({"Error": {"Code": "TransactionCanceledException"}}, "TransactWriteItems")
        profile_table = _CapturingTable()
        request_table = _CapturingTable()
        history_table = _CapturingTable()
        dynamo = _RoutingDynamo(
            {
                dynamodb_models.COACH_PROFILES_TABLE: profile_table,
                dynamodb_models.PLAN_UPDATE_REQUESTS_TABLE: request_table,
                dynamodb_models.PLAN_HISTORY_TABLE: history_table,
            },
            transact_side_effect=collision,
        )

        with mock.patch.object(dynamodb_models, "dynamodb", dynamo), mock.patch.object(
            dynamodb_models,
            "get_current_plan",
            return_value={
                "primary_goal": "Marathon",
                "plan_version": 1,
                "current_phase": "base",
                "current_focus": "consistency",
                "next_recommended_session": {
                    "date": "2026-03-10",
                    "type": "easy",
                    "target": "40 minutes",
                },
                "plan_status": "active",
                "updated_at": 1735732800,
            },
        ), mock.patch.object(
            dynamodb_models,
            "_get_plan_update_request",
            return_value={"payload_hash": "expected", "resulting_plan_version": 2},
        ):
            with mock.patch.object(
                dynamodb_models,
                "_compute_plan_update_payload_hash",
                return_value="expected",
            ):
                result = dynamodb_models.update_current_plan(
                    "ath_1",
                    {"current_phase": "build"},
                    logical_request_id="req-123",
                )

        self.assertEqual(result["status"], "idempotent_replay")
        self.assertEqual(result["plan_version"], 2)


if __name__ == "__main__":
    unittest.main()
