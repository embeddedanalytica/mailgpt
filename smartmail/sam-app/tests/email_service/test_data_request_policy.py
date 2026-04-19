"""Unit tests for minimal v1 data request policy."""

import unittest

from data_request_policy import (
    DEFAULT_MAX_ITEMS,
    DEFAULT_TIMEOUT_SECONDS,
    DEFAULT_WINDOW_DAYS,
    HARD_CAP_MAX_ITEMS,
    HARD_CAP_TIMEOUT_SECONDS,
    HARD_CAP_WINDOW_DAYS,
    resolve_request,
)


class TestDataRequestPolicy(unittest.TestCase):
    def test_liberal_request_is_allowed(self):
        decision = resolve_request(
            {
                "provider": "strava",
                "data_types": ["activities", "sleep", "power_stream"],
                "window_days": 30,
                "max_items": 1500,
                "timeout_seconds": 45,
            }
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.reasons, [])
        self.assertEqual(decision.normalized_request["provider"], "strava")
        self.assertEqual(
            decision.normalized_request["data_types"],
            ["activities", "sleep", "power_stream"],
        )

    def test_missing_provider_is_denied(self):
        decision = resolve_request({"data_types": ["activities"]})
        self.assertFalse(decision.allowed)
        self.assertIsNone(decision.normalized_request)
        self.assertTrue(any("provider" in r for r in decision.reasons))

    def test_invalid_data_types_is_denied(self):
        decision = resolve_request({"provider": "strava", "data_types": ["activities", ""]})
        self.assertFalse(decision.allowed)
        self.assertIsNone(decision.normalized_request)
        self.assertTrue(any("data_types" in r for r in decision.reasons))

    def test_uses_defaults_for_optional_fields(self):
        decision = resolve_request({"provider": "garmin", "data_types": ["sleep"]})
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.normalized_request["window_days"], DEFAULT_WINDOW_DAYS)
        self.assertEqual(decision.normalized_request["max_items"], DEFAULT_MAX_ITEMS)
        self.assertEqual(
            decision.normalized_request["timeout_seconds"], DEFAULT_TIMEOUT_SECONDS
        )

    def test_hard_caps_are_applied(self):
        decision = resolve_request(
            {
                "provider": "strava",
                "data_types": ["activities"],
                "window_days": HARD_CAP_WINDOW_DAYS + 100,
                "max_items": HARD_CAP_MAX_ITEMS + 1000,
                "timeout_seconds": HARD_CAP_TIMEOUT_SECONDS + 60,
            }
        )
        self.assertTrue(decision.allowed)
        self.assertEqual(decision.normalized_request["window_days"], HARD_CAP_WINDOW_DAYS)
        self.assertEqual(decision.normalized_request["max_items"], HARD_CAP_MAX_ITEMS)
        self.assertEqual(
            decision.normalized_request["timeout_seconds"], HARD_CAP_TIMEOUT_SECONDS
        )

    def test_non_dict_request_is_denied(self):
        decision = resolve_request([])  # type: ignore[arg-type]
        self.assertFalse(decision.allowed)
        self.assertIsNone(decision.normalized_request)
        self.assertTrue(any("dict" in r for r in decision.reasons))


if __name__ == "__main__":
    unittest.main()
