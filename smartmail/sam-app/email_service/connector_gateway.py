"""
Minimal connector gateway (v1).

YAGNI-first implementation:
- Apply data request policy.
- Dispatch to provider client adapter.
- No direct network code in this module.
- Provider adapters are injectable and can be mocked in tests.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional, Protocol

from data_request_policy import PolicyDecision, resolve_request


class ProviderClient(Protocol):
    def fetch_data(
        self,
        *,
        data_types: List[str],
        window_days: int,
        max_items: int,
        timeout_seconds: int,
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Fetch connector data for the specified shape and constraints."""


@dataclass(frozen=True)
class GatewayResult:
    ok: bool
    provider: Optional[str]
    request: Optional[Dict[str, Any]]
    data: Optional[Dict[str, Any]]
    error: Optional[str]
    reasons: List[str]


class _StubProviderClient:
    """
    Simple placeholder adapter used until real provider clients are implemented.
    Returns empty payloads for requested data types.
    """

    def __init__(self, provider_name: str) -> None:
        self.provider_name = provider_name

    def fetch_data(
        self,
        *,
        data_types: List[str],
        window_days: int,
        max_items: int,
        timeout_seconds: int,
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        return {
            "provider": self.provider_name,
            "window_days": window_days,
            "max_items": max_items,
            "timeout_seconds": timeout_seconds,
            "data": {data_type: [] for data_type in data_types},
            "meta": {"stub": True, "auth_present": bool(auth_context)},
        }


def build_default_provider_clients() -> Dict[str, ProviderClient]:
    return {"strava": _StubProviderClient("strava"), "garmin": _StubProviderClient("garmin")}


class ConnectorGateway:
    def __init__(
        self,
        *,
        policy_resolver: Callable[[Dict[str, Any]], PolicyDecision] = resolve_request,
        provider_clients: Optional[Dict[str, ProviderClient]] = None,
    ) -> None:
        self._policy_resolver = policy_resolver
        self._provider_clients = provider_clients or build_default_provider_clients()

    def fetch(
        self,
        request: Dict[str, Any],
        *,
        auth_context: Optional[Dict[str, Any]] = None,
    ) -> GatewayResult:
        decision = self._policy_resolver(request)
        if not decision.allowed or not decision.normalized_request:
            return GatewayResult(
                ok=False,
                provider=None,
                request=None,
                data=None,
                error="policy_denied",
                reasons=list(decision.reasons),
            )

        normalized_request = decision.normalized_request
        provider = normalized_request["provider"]
        provider_client = self._provider_clients.get(provider)
        if provider_client is None:
            return GatewayResult(
                ok=False,
                provider=provider,
                request=normalized_request,
                data=None,
                error="unsupported_provider",
                reasons=[f"no client registered for provider={provider}"],
            )

        try:
            payload = provider_client.fetch_data(
                data_types=list(normalized_request["data_types"]),
                window_days=int(normalized_request["window_days"]),
                max_items=int(normalized_request["max_items"]),
                timeout_seconds=int(normalized_request["timeout_seconds"]),
                auth_context=auth_context,
            )
            return GatewayResult(
                ok=True,
                provider=provider,
                request=normalized_request,
                data=payload,
                error=None,
                reasons=[],
            )
        except Exception as exc:
            return GatewayResult(
                ok=False,
                provider=provider,
                request=normalized_request,
                data=None,
                error="provider_fetch_failed",
                reasons=[str(exc)],
            )
