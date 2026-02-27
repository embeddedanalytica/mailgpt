"""Unit tests for minimal connector gateway v1."""

import unittest

from connector_gateway import ConnectorGateway


class _RecordingClient:
    def __init__(self) -> None:
        self.calls = []

    def fetch_data(
        self,
        *,
        data_types,
        window_days,
        max_items,
        timeout_seconds,
        auth_context=None,
    ):
        self.calls.append(
            {
                "data_types": list(data_types),
                "window_days": window_days,
                "max_items": max_items,
                "timeout_seconds": timeout_seconds,
                "auth_context": auth_context,
            }
        )
        return {"ok": True, "items": []}


class _FailingClient:
    def fetch_data(self, **kwargs):  # type: ignore[no-untyped-def]
        raise RuntimeError("upstream connector timeout")


class TestConnectorGateway(unittest.TestCase):
    def test_policy_denied_short_circuits(self):
        gateway = ConnectorGateway(provider_clients={"strava": _RecordingClient()})
        result = gateway.fetch({"data_types": ["activities"]})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "policy_denied")
        self.assertIsNone(result.request)

    def test_unsupported_provider_returns_error(self):
        gateway = ConnectorGateway(provider_clients={"strava": _RecordingClient()})
        result = gateway.fetch({"provider": "garmin", "data_types": ["sleep"]})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "unsupported_provider")
        self.assertEqual(result.provider, "garmin")

    def test_fetch_calls_provider_with_normalized_request(self):
        client = _RecordingClient()
        gateway = ConnectorGateway(provider_clients={"strava": client})
        result = gateway.fetch(
            {
                "provider": " STRAVA ",
                "data_types": ["activities", "activities", "sleep"],
                "window_days": 999,  # will be clamped by policy
                "max_items": 9000,  # will be clamped by policy
                "timeout_seconds": 500,  # will be clamped by policy
            },
            auth_context={"connection_id": "conn_1"},
        )
        self.assertTrue(result.ok)
        self.assertEqual(result.error, None)
        self.assertEqual(result.provider, "strava")
        self.assertEqual(len(client.calls), 1)
        call = client.calls[0]
        self.assertEqual(call["data_types"], ["activities", "sleep"])
        self.assertEqual(call["window_days"], 90)
        self.assertEqual(call["max_items"], 5000)
        self.assertEqual(call["timeout_seconds"], 120)
        self.assertEqual(call["auth_context"], {"connection_id": "conn_1"})

    def test_provider_failure_returns_error(self):
        gateway = ConnectorGateway(provider_clients={"strava": _FailingClient()})
        result = gateway.fetch({"provider": "strava", "data_types": ["activities"]})
        self.assertFalse(result.ok)
        self.assertEqual(result.error, "provider_fetch_failed")
        self.assertTrue(any("timeout" in r for r in result.reasons))


if __name__ == "__main__":
    unittest.main()
