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
            1,
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

    assert requester.calls[0][2] == 30


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

    assert requester.calls[0][2] == 2


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


