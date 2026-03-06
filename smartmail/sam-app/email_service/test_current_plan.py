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
        self.all_transacts = []

    def Table(self, name):  # noqa: N802
        return self.tables[name]

    def _transact_write_items(self, **kwargs):
        self.last_transact = kwargs
        self.all_transacts.append(kwargs)
        if self._transact_side_effect is not None:
            if isinstance(self._transact_side_effect, list):
                effect = self._transact_side_effect.pop(0) if self._transact_side_effect else None
            else:
                effect = self._transact_side_effect
            if effect is not None:
                raise effect
        return {}


class TestCurrentPlanHelpers(unittest.TestCase):
    def test_build_default_current_plan_has_required_fields(self):
        plan = dynamodb_models._build_default_current_plan(goal="10k PR", now_epoch=1735732800)
        self.assertEqual(plan["primary_goal"], "10k PR")
        self.assertEqual(plan["plan_version"], 1)
        self.assertEqual(plan["current_phase"], "base")
        self.assertEqual(plan["current_focus"], "Build consistency")
        self.assertEqual(plan["plan_status"], "active")
        self.assertEqual(plan["weekly_skeleton"], [])
        self.assertEqual(plan["plan_adjustments"], [])
        self.assertEqual(plan["plan_update_status"], "updated")

    def test_normalize_current_plan_keeps_optional_re2_fields(self):
        normalized = dynamodb_models.normalize_current_plan(
            {
                "primary_goal": "Marathon",
                "plan_version": 3,
                "current_phase": "build",
                "current_focus": "threshold",
                "next_recommended_session": {
                    "date": "2026-03-15",
                    "type": "easy",
                    "target": "45 minutes",
                },
                "plan_status": "adjusting",
                "weekly_skeleton": ["easy_aerobic", "tempo", "strength"],
                "plan_adjustments": ["reduce_intensity"],
                "plan_update_status": "updated",
                "updated_at": 1735732800,
            }
        )
        self.assertEqual(normalized["weekly_skeleton"], ["easy_aerobic", "tempo", "strength"])
        self.assertEqual(normalized["plan_adjustments"], ["reduce_intensity"])
        self.assertEqual(normalized["plan_update_status"], "updated")

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

    def test_update_current_plan_accepts_re2_optional_fields(self):
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
                    "weekly_skeleton": ["easy_aerobic", "tempo", "strength"],
                    "plan_adjustments": ["reduce_intensity"],
                    "plan_update_status": "updated",
                },
                logical_request_id="req-re2-fields",
            )

        self.assertEqual(result["status"], "applied")
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

    def test_two_plan_updates_produce_two_history_records(self):
        """Updating plan twice results in two distinct history records (DoD: immutable plan history)."""
        plan_v1 = {
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
        }
        plan_v2 = dict(plan_v1, plan_version=2, current_phase="build", updated_at=1735732900)
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
            side_effect=[plan_v1, plan_v2],
        ):
            r1 = dynamodb_models.update_current_plan(
                "ath_1",
                {"current_phase": "build"},
                logical_request_id="req-1",
            )
            r2 = dynamodb_models.update_current_plan(
                "ath_1",
                {"current_focus": "threshold"},
                logical_request_id="req-2",
            )
        self.assertEqual(r1["status"], "applied")
        self.assertEqual(r1["plan_version"], 2)
        self.assertEqual(r2["status"], "applied")
        self.assertEqual(r2["plan_version"], 3)
        self.assertEqual(len(dynamo.all_transacts), 2)
        for i, transact_kwargs in enumerate(dynamo.all_transacts):
            transact_items = transact_kwargs.get("TransactItems", [])
            history_puts = [
                t["Put"] for t in transact_items
                if t.get("Put", {}).get("TableName") == dynamodb_models.PLAN_HISTORY_TABLE
            ]
            self.assertEqual(len(history_puts), 1, f"transact {i} should have one history Put")
            item = history_puts[0].get("Item", {})
            plan_version_serialized = item.get("plan_version", {})
            raw = plan_version_serialized.get("N") or plan_version_serialized.get("S")
            self.assertIsNotNone(raw, "plan_version should be serialized")
            self.assertEqual(int(raw), i + 2)

    def test_get_plan_history_returns_items_ascending_plan_version(self):
        """History can be retrieved by athlete_id in ascending plan_version order (DoD)."""
        history_table = _PlanHistoryQueryTable(
            items=[
                {
                    "athlete_id": "ath_1",
                    "plan_version": 1,
                    "updated_at": 1735732800,
                    "logical_request_id": "req-1",
                    "plan": {"primary_goal": "Marathon", "plan_version": 1},
                },
                {
                    "athlete_id": "ath_1",
                    "plan_version": 2,
                    "updated_at": 1735732900,
                    "logical_request_id": "req-2",
                    "plan": {"primary_goal": "Marathon", "plan_version": 2},
                },
            ]
        )
        dynamo = _RoutingDynamo({
            dynamodb_models.PLAN_HISTORY_TABLE: history_table,
        })
        with mock.patch.object(dynamodb_models, "dynamodb", dynamo):
            result = dynamodb_models.get_plan_history("ath_1", limit=10)
        self.assertIn("items", result)
        self.assertEqual(len(result["items"]), 2)
        self.assertEqual(result["items"][0]["plan_version"], 1)
        self.assertEqual(result["items"][1]["plan_version"], 2)
        self.assertEqual(result["items"][0]["logical_request_id"], "req-1")
        self.assertEqual(result["items"][1]["updated_at"], 1735732900)


    def test_concurrent_plan_updates_result_in_consistent_state(self):
        """Simulated concurrent updates: one wins, the other retries and applies; final state and history ordered (DoD)."""
        plan_v1 = {
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
        }
        plan_v2 = dict(plan_v1, plan_version=2, current_phase="build", updated_at=1735732900)
        profile_table = _CapturingTable()
        request_table = _CapturingTable()
        history_table = _CapturingTable()
        # First transact succeeds (update A); second raises (update B's first attempt); third succeeds (update B retry).
        collision = ClientError(
            {"Error": {"Code": "TransactionCanceledException"}},
            "TransactWriteItems",
        )
        dynamo = _RoutingDynamo(
            {
                dynamodb_models.COACH_PROFILES_TABLE: profile_table,
                dynamodb_models.PLAN_UPDATE_REQUESTS_TABLE: request_table,
                dynamodb_models.PLAN_HISTORY_TABLE: history_table,
            },
            transact_side_effect=[None, collision, None],
        )
        with mock.patch.object(dynamodb_models, "dynamodb", dynamo), mock.patch.object(
            dynamodb_models,
            "get_current_plan",
            side_effect=[plan_v1, plan_v1, plan_v2],
        ), mock.patch.object(
            dynamodb_models,
            "_get_plan_update_request",
            return_value=None,
        ):
            r1 = dynamodb_models.update_current_plan(
                "ath_1",
                {"current_phase": "build"},
                logical_request_id="req-1",
            )
            r2 = dynamodb_models.update_current_plan(
                "ath_1",
                {"current_focus": "threshold"},
                logical_request_id="req-2",
            )
        self.assertEqual(r1["status"], "applied")
        self.assertEqual(r1["plan_version"], 2)
        self.assertEqual(r2["status"], "applied")
        self.assertEqual(r2["plan_version"], 3)
        self.assertEqual(len(dynamo.all_transacts), 3)
        versions_written = []
        for transact_kwargs in dynamo.all_transacts:
            transact_items = transact_kwargs.get("TransactItems", [])
            history_puts = [
                t["Put"] for t in transact_items
                if t.get("Put", {}).get("TableName") == dynamodb_models.PLAN_HISTORY_TABLE
            ]
            if history_puts:
                item = history_puts[0].get("Item", {})
                raw = item.get("plan_version", {}).get("N") or item.get("plan_version", {}).get("S")
                versions_written.append(int(raw))
        # First and third transacts committed (v2, v3); second failed (would have been v2) so only v2,v3 in history.
        self.assertIn(2, versions_written)
        self.assertEqual(versions_written[-1], 3, "Final plan version should be 3 (consistent state after retry).")


class _PlanHistoryQueryTable:
    """Mock table that returns fixed items for query() to test get_plan_history."""

    def __init__(self, items):
        self._items = sorted(items, key=lambda x: x["plan_version"])

    def query(self, **kwargs):
        return {"Items": list(self._items), "LastEvaluatedKey": None}


if __name__ == "__main__":
    unittest.main()
