import sys
import types
import unittest
from decimal import Decimal
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


def _memory_note(
    note_id: int,
    *,
    fact_type: str,
    fact_key: str,
    summary: str,
    importance: str = "medium",
    status: str = "active",
    created_at: int = 1772000000,
    updated_at: int = 1773014400,
    last_confirmed_at: int = 1773014400,
) -> dict:
    return {
        "memory_note_id": note_id,
        "fact_type": fact_type,
        "fact_key": fact_key,
        "summary": summary,
        "importance": importance,
        "status": status,
        "created_at": created_at,
        "updated_at": updated_at,
        "last_confirmed_at": last_confirmed_at,
    }


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


class _ProfileMemoryTable:
    def __init__(self, item=None):
        self.item = dict(item or {})
        self.last_update_kwargs = None

    def get_item(self, **kwargs):
        athlete_id = kwargs.get("Key", {}).get("athlete_id")
        if athlete_id and self.item.get("athlete_id") == athlete_id:
            return {"Item": dict(self.item)}
        return {}

    def update_item(self, **kwargs):
        self.last_update_kwargs = kwargs
        values = kwargs.get("ExpressionAttributeValues", {})
        if ":created_at" in values and "created_at" not in self.item:
            self.item["created_at"] = values[":created_at"]
        if ":updated_at" in values:
            self.item["updated_at"] = values[":updated_at"]
        if ":memory_notes" in values:
            self.item["memory_notes"] = values[":memory_notes"]
        if ":continuity_summary" in values:
            self.item["continuity_summary"] = values[":continuity_summary"]
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
    def test_serialize_dynamodb_payload_converts_nested_floats(self):
        payload = {
            "score": 2.5,
            "nested": {"confidence": 0.75, "items": [1, 3.5, True, None]},
            "tuple_values": (4.5, "ok"),
            "count": 2,
        }

        serialized = dynamodb_models.serialize_dynamodb_payload(payload)

        self.assertEqual(serialized["score"], Decimal("2.5"))
        self.assertEqual(serialized["nested"]["confidence"], Decimal("0.75"))
        self.assertEqual(serialized["nested"]["items"][1], Decimal("3.5"))
        self.assertIs(serialized["nested"]["items"][2], True)
        self.assertEqual(serialized["tuple_values"], [Decimal("4.5"), "ok"])
        self.assertEqual(serialized["count"], 2)

    def test_serialize_dynamodb_payload_rejects_non_finite_float(self):
        with self.assertRaises(ValueError):
            dynamodb_models.serialize_dynamodb_payload({"bad": float("inf")})

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

    def test_normalize_profile_record_accepts_decimal_hours_per_week(self):
        normalized = dynamodb_models.normalize_profile_record(
            {"time_availability": {"hours_per_week": Decimal("4.5")}}
        )
        self.assertEqual(normalized["time_availability"]["hours_per_week"], 4.5)

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

    def test_normalize_profile_updates_converts_hours_per_week_to_decimal(self):
        normalized = dynamodb_models.normalize_profile_updates(
            {"time_availability": {"hours_per_week": 4.5}}
        )
        self.assertEqual(normalized["time_availability"]["hours_per_week"], Decimal("4.5"))

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

    def test_merge_coach_profile_fields_writes_decimal_hours_per_week(self):
        profile_table = _ProfileSeedTable()
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            ok = dynamodb_models.merge_coach_profile_fields(
                "ath_123",
                {"time_availability": {"sessions_per_week": 4, "hours_per_week": 4.5}},
            )

        self.assertTrue(ok)
        values = profile_table.last_update_kwargs["ExpressionAttributeValues"]
        self.assertEqual(
            values[":v_time_availability"],
            {"sessions_per_week": 4, "hours_per_week": Decimal("4.5")},
        )

    def test_get_memory_notes_returns_empty_when_missing(self):
        profile_table = _ProfileMemoryTable({"athlete_id": "ath_123"})
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            notes = dynamodb_models.get_memory_notes("ath_123")

        self.assertEqual(notes, [])

    def test_get_memory_notes_hard_cutover_drops_am1_shape(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_123",
                "memory_notes": [
                    {
                        "memory_note_id": 1,
                        "category": "schedule",
                        "summary": "old shape",
                        "importance": "medium",
                        "last_confirmed_at": 1772928000,
                    }
                ],
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            notes = dynamodb_models.get_memory_notes("ath_123")

        self.assertEqual(notes, [])

    def test_replace_memory_notes_persists_multiple_notes(self):
        profile_table = _ProfileMemoryTable({"athlete_id": "ath_123"})
        notes = [
            _memory_note(
                1,
                fact_type="schedule",
                fact_key="weekday_before_7am_cutoff",
                summary="Prefers early runs on weekdays",
                importance="high",
                updated_at=1772928000,
                last_confirmed_at=1772928000,
            ),
            _memory_note(
                2,
                fact_type="other",
                fact_key="treadmill_access",
                summary="Uses a treadmill when weather is bad",
                updated_at=1773014400,
                last_confirmed_at=1773014400,
            ),
        ]
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            ok = dynamodb_models.replace_memory_notes("ath_123", notes)
            stored = dynamodb_models.get_memory_notes("ath_123")

        self.assertTrue(ok)
        self.assertEqual(stored, notes)
        names = profile_table.last_update_kwargs["ExpressionAttributeNames"]
        self.assertEqual(names["#memory_notes"], "memory_notes")

    def test_get_active_memory_notes_filters_inactive(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_123",
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="schedule",
                        fact_key="masters_session_slot",
                        summary="Masters swim every Tuesday night",
                    ),
                    _memory_note(
                        2,
                        fact_type="schedule",
                        fact_key="masters_session_slot",
                        summary="Old Tuesday masters wording",
                        status="inactive",
                    ),
                ],
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            notes = dynamodb_models.get_active_memory_notes("ath_123")

        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["memory_note_id"], 1)

    def test_upsert_memory_note_assigns_next_available_id(self):
        profile_table = _ProfileMemoryTable({"athlete_id": "ath_123"})
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            first = dynamodb_models.upsert_memory_note(
                "ath_123",
                {
                    "fact_type": "schedule",
                    "fact_key": "weekday cutoff",
                    "summary": "Can usually train before work",
                    "importance": "high",
                },
            )
            second = dynamodb_models.upsert_memory_note(
                "ath_123",
                {
                    "fact_type": "other",
                    "fact_key": "thursday travel pattern",
                    "summary": "Travel is heavy every second Thursday",
                    "importance": "medium",
                },
            )

        self.assertEqual(first["memory_note_id"], 1)
        self.assertEqual(second["memory_note_id"], 2)
        self.assertEqual(
            [note["memory_note_id"] for note in profile_table.item["memory_notes"]],
            [1, 2],
        )

    def test_upsert_memory_note_updates_existing_note_without_changing_id(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_123",
                "memory_notes": [
                    _memory_note(
                        2,
                        fact_type="constraint",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Can train only before 7am",
                        updated_at=1772928000,
                        last_confirmed_at=1772928000,
                    )
                ],
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            updated = dynamodb_models.upsert_memory_note(
                "ath_123",
                {
                    "memory_note_id": 2,
                    "fact_type": "constraint",
                    "fact_key": "weekday cutoff",
                    "summary": "Can train only before 6:30am on weekdays",
                    "importance": "medium",
                },
            )
            stored = dynamodb_models.get_memory_notes("ath_123")

        self.assertEqual(updated["memory_note_id"], 2)
        self.assertEqual(len(stored), 1)
        self.assertEqual(stored[0]["memory_note_id"], 2)
        self.assertEqual(stored[0]["summary"], "Can train only before 6:30am on weekdays")
        self.assertEqual(stored[0]["fact_key"], "weekday_cutoff")

    def test_upsert_memory_note_rejects_unknown_existing_id(self):
        profile_table = _ProfileMemoryTable({"athlete_id": "ath_123"})
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            result = dynamodb_models.upsert_memory_note(
                "ath_123",
                {
                    "memory_note_id": 9,
                    "fact_type": "schedule",
                    "fact_key": "weekday cutoff",
                    "summary": "Should fail",
                    "importance": "medium",
                },
            )

        self.assertIsNone(result)

    def test_get_memory_context_for_response_generation_applies_selection_rule(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_123",
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="achilles_tightness_watch",
                        summary="Monitor Achilles tightness",
                        importance="high",
                        updated_at=1772668800,
                        last_confirmed_at=1772668800,
                    ),
                    _memory_note(
                        2,
                        fact_type="schedule",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Prefers early weekdays",
                        updated_at=1773100800,
                        last_confirmed_at=1773100800,
                    ),
                    _memory_note(
                        3,
                        fact_type="other",
                        fact_key="treadmill_access",
                        summary="Uses treadmill in bad weather",
                        importance="low",
                        updated_at=1773014400,
                        last_confirmed_at=1773014400,
                    ),
                    _memory_note(
                        4,
                        fact_type="constraint",
                        fact_key="thursday_availability",
                        summary="Busy on Thursdays",
                        updated_at=1772928000,
                        last_confirmed_at=1772928000,
                    ),
                ],
                "continuity_summary": {
                    "summary": "Rebuilding after travel week.",
                    "last_recommendation": "Keep the week light.",
                    "open_loops": ["Check energy next week"],
                    "updated_at": 1773100800,
                },
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            context = dynamodb_models.get_memory_context_for_response_generation("ath_123")

        selected_ids = [note["memory_note_id"] for note in context["memory_notes"]]
        self.assertEqual(selected_ids, [1, 2, 3, 4])
        self.assertEqual(context["continuity_summary"]["summary"], "Rebuilding after travel week.")

    def test_get_memory_context_for_response_generation_includes_all_high_and_only_three_extra_recent(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_realistic",
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="calf_tightness_watch",
                        summary="History of calf tightness when intensity jumps too quickly",
                        importance="high",
                        updated_at=1772409600,
                        last_confirmed_at=1772409600,
                    ),
                    _memory_note(
                        2,
                        fact_type="constraint",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Usually can train only before 7am on weekdays",
                        importance="high",
                        updated_at=1773187200,
                        last_confirmed_at=1773187200,
                    ),
                    _memory_note(
                        3,
                        fact_type="schedule",
                        fact_key="travel_disruption_pattern",
                        summary="Travel week every third week of the month",
                        updated_at=1772668800,
                        last_confirmed_at=1772668800,
                    ),
                    _memory_note(
                        4,
                        fact_type="other",
                        fact_key="home_training_access",
                        summary="Has treadmill and adjustable dumbbells at home",
                        updated_at=1773100800,
                        last_confirmed_at=1773100800,
                    ),
                    _memory_note(
                        5,
                        fact_type="preference",
                        fact_key="reply_format",
                        summary="Prefers concise bullets over long explanations",
                        importance="low",
                        updated_at=1773014400,
                        last_confirmed_at=1773014400,
                    ),
                ],
                "continuity_summary": {
                    "summary": "Athlete is rebuilding consistency after two disrupted travel weeks.",
                    "last_recommendation": "Hold intensity steady and protect the calf while restoring routine.",
                    "open_loops": [
                        "Confirm whether travel block is over",
                        "Check calf response after first faster session",
                    ],
                    "updated_at": 1773187200,
                },
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            context = dynamodb_models.get_memory_context_for_response_generation("ath_realistic")

        selected_ids = [note["memory_note_id"] for note in context["memory_notes"]]
        self.assertEqual(selected_ids, [1, 2, 4, 5, 3])
        self.assertEqual(
            context["continuity_summary"]["open_loops"],
            [
                "Confirm whether travel block is over",
                "Check calf response after first faster session",
            ],
        )

    def test_get_memory_context_for_response_generation_drops_only_invalid_artifacts(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_invalid",
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="schedule",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Valid note",
                        updated_at=1772928000,
                        last_confirmed_at=1772928000,
                    ),
                    {
                        "memory_note_id": 2,
                        "category": "Bad-Category",
                        "summary": "Stylistically odd category should still be kept",
                        "importance": "medium",
                        "last_confirmed_at": 1773014400,
                    },
                ],
                "continuity_summary": {
                    "summary": " ",
                    "last_recommendation": "Invalid continuity payload should be dropped",
                    "open_loops": ["check"],
                    "updated_at": 1773014400,
                },
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            context = dynamodb_models.get_memory_context_for_response_generation("ath_invalid")

        self.assertEqual(context["memory_notes"], [])
        self.assertIsNone(context["continuity_summary"])

    def test_replace_memory_artifacts_atomically_persists_notes_and_continuity_summary(self):
        profile_table = _ProfileMemoryTable({"athlete_id": "ath_123"})
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            ok = dynamodb_models.replace_memory_artifacts(
                "ath_123",
                memory_notes=[
                    _memory_note(
                        1,
                        fact_type="constraint",
                        fact_key="weekday_before_7am_cutoff",
                        summary="Weekday sessions need to finish before 7am",
                        importance="high",
                        created_at=1773273600,
                        updated_at=1773273600,
                        last_confirmed_at=1773273600,
                    )
                ],
                continuity_summary={
                    "summary": "Athlete is back from travel and rebuilding consistency.",
                    "last_recommendation": "Keep one moderate session this week.",
                    "open_loops": ["Check calf response after Thursday workout"],
                    "updated_at": 1773273600,
                },
            )

        self.assertTrue(ok)
        self.assertEqual(profile_table.item["memory_notes"][0]["memory_note_id"], 1)
        self.assertEqual(
            profile_table.item["continuity_summary"]["summary"],
            "Athlete is back from travel and rebuilding consistency.",
        )

    def test_replace_continuity_summary_updates_only_continuity(self):
        profile_table = _ProfileMemoryTable(
            {
                "athlete_id": "ath_123",
                "memory_notes": [
                    _memory_note(
                        1,
                        fact_type="goal",
                        fact_key="marathon_goal",
                        summary="Training for a fall marathon",
                    )
                ],
            }
        )
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            ok = dynamodb_models.replace_continuity_summary(
                "ath_123",
                {
                    "summary": "Athlete is back from travel.",
                    "last_recommendation": "Keep the week light.",
                    "open_loops": ["Check energy next week"],
                    "updated_at": 1773273600,
                },
            )

        self.assertTrue(ok)
        self.assertEqual(profile_table.item["memory_notes"][0]["fact_key"], "marathon_goal")
        self.assertEqual(profile_table.item["continuity_summary"]["summary"], "Athlete is back from travel.")

    def test_replace_memory_artifacts_rejects_duplicate_ids_and_too_many_notes(self):
        profile_table = _ProfileMemoryTable({"athlete_id": "ath_123"})
        duplicate_ids_ok = None
        too_many_active_ok = None
        with mock.patch.object(
            dynamodb_models,
            "dynamodb",
            _RoutingDynamo({dynamodb_models.COACH_PROFILES_TABLE: profile_table}),
        ):
            duplicate_ids_ok = dynamodb_models.replace_memory_artifacts(
                "ath_123",
                memory_notes=[
                    _memory_note(
                        1,
                        fact_type="schedule",
                        fact_key="first_slot",
                        summary="first",
                        importance="high",
                        created_at=1773273600,
                        updated_at=1773273600,
                        last_confirmed_at=1773273600,
                    ),
                    _memory_note(
                        1,
                        fact_type="other",
                        fact_key="duplicate_id",
                        summary="duplicate id",
                        created_at=1773273600,
                        updated_at=1773273600,
                        last_confirmed_at=1773273600,
                    ),
                ],
                continuity_summary={
                    "summary": "ok",
                    "last_recommendation": "ok",
                    "open_loops": ["ok"],
                    "updated_at": 1773273600,
                },
            )
            too_many_active_ok = dynamodb_models.replace_memory_artifacts(
                "ath_123",
                memory_notes=[
                    _memory_note(
                        idx,
                        fact_type="schedule",
                        fact_key=f"schedule:note_{idx}",
                        summary=f"note {idx}",
                        created_at=1773273600,
                        updated_at=1773273600,
                        last_confirmed_at=1773273600,
                    )
                    for idx in range(1, 9)
                ],
                continuity_summary={
                    "summary": "ok",
                    "last_recommendation": "ok",
                    "open_loops": ["ok"],
                    "updated_at": 1773273600,
                },
            )

        self.assertFalse(duplicate_ids_ok)
        self.assertFalse(too_many_active_ok)


if __name__ == "__main__":
    unittest.main()
