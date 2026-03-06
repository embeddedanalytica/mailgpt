"""Shared test helpers for email_service unit tests."""

from __future__ import annotations

import sys
import types


def install_boto_stubs() -> None:
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
        dynamodb_conditions_module.Key = Key
        dynamodb_types_module.TypeSerializer = TypeSerializer
        dynamodb_module.conditions = dynamodb_conditions_module
        dynamodb_module.types = dynamodb_types_module

        sys.modules["boto3"] = boto3_module
        sys.modules["boto3.dynamodb"] = dynamodb_module
        sys.modules["boto3.dynamodb.conditions"] = dynamodb_conditions_module
        sys.modules["boto3.dynamodb.types"] = dynamodb_types_module


def valid_engine_output_payload(**overrides):
    payload = {
        "classification_label": "event_8_16w / hybrid_seasonal / intermediate / 4_6h / recurring_niggles / high",
        "track": "main_build",
        "phase": "build",
        "risk_flag": "yellow",
        "weekly_skeleton": [
            "easy_aerobic_main",
            "easy_aerobic_main",
            "reduced_intensity_or_easy",
            "strength_or_cross_train",
        ],
        "today_action": "do planned but conservative",
        "plan_update_status": "updated",
        "adjustments": ["reduce intensity", "no make-up intensity"],
        "next_email_payload": {
            "subject_hint": "This week: stay consistent, reduce intensity",
            "summary": "Short summary.",
            "sessions": ["Session 1", "Session 2"],
            "plan_focus_line": "Nail one key aerobic anchor and protect recovery.",
            "technique_cue": "Relax shoulders and keep cadence smooth.",
            "recovery_target": "Sleep 7.5+ hours on three nights.",
            "if_then_rules": ["If pain rises above 4, stop intensity immediately."],
            "disclaimer_short": "Not medical advice; consult a clinician if symptoms escalate.",
            "safety_note": "Monitor symptoms and keep intensity controlled.",
        },
    }
    payload.update(overrides)
    return payload
