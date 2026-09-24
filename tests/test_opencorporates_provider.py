import json
from dataclasses import dataclass

import pytest

from shema_platform.adapters.intelligence.opencorporates import (
    OpenCorporatesConfiguration,
    OpenCorporatesProvider,
)


@dataclass
class FakeRequester:
    status: int
    payload: dict
    calls: list[tuple[str, dict, float]]

    def __call__(
        self,
        url: str,
        params: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        self.calls.append((url, params, timeout_seconds))
        return self.status, json.dumps(self.payload).encode()


def configuration() -> OpenCorporatesConfiguration:
    return OpenCorporatesConfiguration(
        api_token="secret-token",
        api_version="0.4",
        base_url="https://api.opencorporates.com",
        timeout_seconds=1,
        max_requests_per_second=1000,
        coverage=frozenset({"company", "logistics"}),
        confidence=0.8,
    )


def test_environment_configuration_requires_api_token(monkeypatch) -> None:
    monkeypatch.delenv("OPENCORPORATES_API_TOKEN", raising=False)

    with pytest.raises(
        ValueError,
        match="OPENCORPORATES_API_TOKEN is required",
    ):
        OpenCorporatesConfiguration.from_environment()


def test_configuration_rejects_non_https_base_url() -> None:
    with pytest.raises(ValueError, match="must use HTTPS"):
        OpenCorporatesConfiguration(
            api_token="secret",
            base_url="http://api.opencorporates.com",
        )


def test_configuration_rejects_non_positive_response_limit() -> None:
    with pytest.raises(ValueError, match="must be positive"):
        OpenCorporatesConfiguration(
            api_token="secret",
            max_response_bytes=0,
        )


def test_configuration_rejects_response_limit_above_hard_cap() -> None:
    with pytest.raises(ValueError, match="must not exceed 4194304"):
        OpenCorporatesConfiguration(
            api_token="secret",
            max_response_bytes=4_194_305,
        )


def test_provider_parses_provenanced_company_observations() -> None:
    requester = FakeRequester(
        status=200,
        payload={
            "api_version": "0.4",
            "results": {
                "companies": [
                    {
                        "company": {
                            "name": "Example Logistics Ltd",
                            "company_number": "123",
                            "jurisdiction_code": "gb",
                            "current_status": "Active",
                            "opencorporates_url": (
                                "https://opencorporates.com/companies/gb/123"
                            ),
                        }
                    },
                    {
                        "company": {
                            "name": "",
                            "company_number": "456",
                            "jurisdiction_code": "gb",
                            "opencorporates_url": (
                                "https://opencorporates.com/companies/gb/456"
                            ),
                        }
                    },
                ]
            },
        },
        calls=[],
    )
    provider = OpenCorporatesProvider(configuration(), requester=requester)

    result = provider.research("Example Logistics", max_sources=10)

    assert result.provider_id == "opencorporates"
    assert result.source_class == "corporate_registry_aggregator"
    assert result.claims == (
        "OpenCorporates company observation: "
        "name=Example Logistics Ltd; company_number=123; "
        "jurisdiction=gb; current_status=Active",
    )
    assert result.source_refs == (
        "https://opencorporates.com/companies/gb/123",
    )
    assert requester.calls == [
        (
            "https://api.opencorporates.com/v0.4/companies/search",
            {
                "api_token": "secret-token",
                "q": "Example Logistics",
                "per_page": "10",
                "order": "score",
            },
            pytest.approx(1, abs=1e-4),
        )
    ]


def test_provider_caps_requested_sources_at_api_limit() -> None:
    requester = FakeRequester(
        status=200,
        payload={"results": {"companies": []}},
        calls=[],
    )
    provider = OpenCorporatesProvider(configuration(), requester=requester)

    result = provider.research("company", max_sources=500)

    assert result.claims == ()
    assert requester.calls[0][1]["per_page"] == "50"


def test_provider_rejects_oversized_custom_requester_response() -> None:
    class OversizedRequester:
        def __call__(
            self,
            url: str,
            params: dict[str, str],
            timeout_seconds: float,
        ) -> tuple[int, bytes]:
            return 200, b"x" * (1024 * 1024 + 1)

    provider = OpenCorporatesProvider(
        OpenCorporatesConfiguration(
            api_token="secret",
            max_response_bytes=1024 * 1024,
        ),
        requester=OversizedRequester(),
    )

    with pytest.raises(ValueError, match="exceeds configured max_response_bytes"):
        provider.research("company", max_sources=1)


def test_request_json_enforces_transport_response_limit(monkeypatch) -> None:
    import shema_platform.adapters.intelligence.opencorporates as module

    class FakeResponse:
        status = 200

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, traceback):
            return None

        def read(self, size: int) -> bytes:
            return b"x" * size

    monkeypatch.setattr(
        module,
        "urlopen",
        lambda request, timeout: FakeResponse(),
    )

    with pytest.raises(ValueError, match="exceeds configured max_response_bytes"):
        module._request_json(
            "https://api.opencorporates.com/v0.4/companies/search",
            {"q": "company"},
            1,
            8,
        )


def test_provider_fails_on_http_error() -> None:
    requester = FakeRequester(
        status=401,
        payload={"error": "unauthorized"},
        calls=[],
    )
    provider = OpenCorporatesProvider(configuration(), requester=requester)

    with pytest.raises(ConnectionError, match="HTTP 401"):
        provider.research("company", max_sources=5)


def test_provider_fails_on_invalid_json() -> None:
    class InvalidJSONRequester:
        def __call__(
            self,
            url: str,
            params: dict[str, str],
            timeout_seconds: float,
        ) -> tuple[int, bytes]:
            return 200, b"not-json"

    provider = OpenCorporatesProvider(
        configuration(),
        requester=InvalidJSONRequester(),
    )

    with pytest.raises(ValueError, match="invalid JSON"):
        provider.research("company", max_sources=5)


def test_configuration_rejects_unbounded_timeout() -> None:
    with pytest.raises(ValueError, match="must not exceed 30"):
        OpenCorporatesConfiguration(
            api_token="secret",
            timeout_seconds=30.1,
        )


def test_provider_passes_bounded_timeout_to_external_request() -> None:
    requester = FakeRequester(
        status=200,
        payload={"results": {"companies": []}},
        calls=[],
    )
    provider = OpenCorporatesProvider(
        OpenCorporatesConfiguration(
            api_token="secret",
            timeout_seconds=30,
            max_requests_per_second=1000,
        ),
        requester=requester,
    )

    provider.research("company", max_sources=1)

    assert requester.calls[0][2] == pytest.approx(30, abs=1e-4)


def test_provider_uses_research_deadline_override() -> None:
    requester = FakeRequester(
        status=200,
        payload={"results": {"companies": []}},
        calls=[],
    )
    provider = OpenCorporatesProvider(
        OpenCorporatesConfiguration(
            api_token="secret",
            timeout_seconds=5,
            max_requests_per_second=1000,
        ),
        requester=requester,
    )

    provider.research("company", max_sources=1, timeout_seconds=2)

    assert requester.calls[0][2] == pytest.approx(2, abs=1e-4)


def test_provider_rejects_non_positive_research_deadline() -> None:
    provider = OpenCorporatesProvider(
        configuration(),
        requester=FakeRequester(
            status=200,
            payload={"results": {"companies": []}},
            calls=[],
        ),
    )

    with pytest.raises(ValueError, match="override must be positive"):
        provider.research("company", max_sources=1, timeout_seconds=0)


def test_provider_reduces_timeout_by_rate_limit_wait(monkeypatch) -> None:
    import shema_platform.adapters.intelligence.opencorporates as module

    now = [100.0]
    monkeypatch.setattr(module.time, "monotonic", lambda: now[0])
    monkeypatch.setattr(
        module.time,
        "sleep",
        lambda seconds: now.__setitem__(0, now[0] + seconds),
    )

    requester = FakeRequester(
        status=200,
        payload={"results": {"companies": []}},
        calls=[],
    )
    provider = OpenCorporatesProvider(
        OpenCorporatesConfiguration(
            api_token="secret",
            timeout_seconds=1,
            max_requests_per_second=2,
        ),
        requester=requester,
    )
    provider._last_request_at = 99.8

    provider.research("company", max_sources=1, timeout_seconds=0.5)

    assert requester.calls[0][2] == pytest.approx(0.2, abs=1e-9)


def test_provider_rejects_deadline_consumed_by_rate_limit_wait(monkeypatch) -> None:
    import shema_platform.adapters.intelligence.opencorporates as module

    monkeypatch.setattr(module.time, "monotonic", lambda: 100.0)

    requester = FakeRequester(
        status=200,
        payload={"results": {"companies": []}},
        calls=[],
    )
    provider = OpenCorporatesProvider(
        OpenCorporatesConfiguration(
            api_token="secret",
            timeout_seconds=1,
            max_requests_per_second=1,
        ),
        requester=requester,
    )
    provider._last_request_at = 99.5

    with pytest.raises(TimeoutError, match="rate-limit wait"):
        provider.research("company", max_sources=1, timeout_seconds=0.1)

    assert requester.calls == []
