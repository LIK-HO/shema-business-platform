from __future__ import annotations

import json

import pytest

from shema_platform.adapters.intelligence.dadata import (
    DaDataConfiguration,
    DaDataCounterpartyLookupProvider,
)
from shema_platform.application.counterparty_lookup import (
    BoundedCounterpartyLookup,
    CounterpartyLookupIdentifierType,
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
)


def sample_response() -> bytes:
    return json.dumps(
        {
            "suggestions": [
                {
                    "value": 'ООО "Пример"',
                    "unrestricted_value": 'ООО "Пример"',
                    "data": {
                        "name": {"full_with_opf": 'ООО "Пример"'},
                        "inn": "7707083893",
                        "ogrn": "1027700132195",
                        "type": "LEGAL",
                        "state": {"status": "ACTIVE", "actuality_date": 1771891200000},
                    },
                }
            ]
        }
    ).encode("utf-8")


def inn_query() -> CounterpartyLookupQuery:
    return CounterpartyLookupQuery(
        identifier_type=CounterpartyLookupIdentifierType.INN,
        identifier="7707083893",
    )


def enabled_config(**overrides) -> DaDataConfiguration:
    values = {
        "api_key": "test-token",
        "enabled": True,
        "timeout_seconds": 5.0,
        "max_response_bytes": 1024 * 1024,
        "min_connection_interval_seconds": 0.001,
    }
    values.update(overrides)
    return DaDataConfiguration(**values)


def test_provider_is_disabled_by_default() -> None:
    provider = DaDataCounterpartyLookupProvider(DaDataConfiguration(api_key="", enabled=False))
    with pytest.raises(CounterpartyLookupProviderError, match="disabled"):
        provider.lookup(inn_query())


def test_missing_key_is_explicit_when_enabled() -> None:
    with pytest.raises(ValueError, match="DADATA_API_KEY"):
        DaDataConfiguration(api_key="", enabled=True)


def test_success_response_is_normalized() -> None:
    calls = []

    def requester(endpoint, api_key, payload, timeout, max_bytes):
        calls.append((endpoint, api_key, payload, timeout, max_bytes))
        return 200, sample_response()

    provider = DaDataCounterpartyLookupProvider(enabled_config(), requester=requester)
    record = provider.lookup(inn_query())

    assert record.provider_id == "dadata_organization_api"
    assert record.source_ref == "https://dadata.ru/api/find-party/"
    assert record.tax_id == "7707083893"
    assert record.registration_id == "1027700132195"
    assert record.canonical_name == 'ООО "Пример"'
    assert record.legal_status == "ACTIVE"
    assert calls[0][2] == {"query": "7707083893", "count": 1}


@pytest.mark.parametrize(
    ("status", "code", "retryable"),
    [
        (400, "INVALID_REQUEST", False),
        (401, "MISSING_OR_INVALID_API_KEY", False),
        (403, "ACCOUNT_OR_QUOTA_FORBIDDEN", False),
        (405, "METHOD_NOT_ALLOWED", False),
        (413, "REQUEST_TOO_LARGE", False),
        (429, "PROVIDER_RATE_LIMIT", True),
        (500, "PROVIDER_INTERNAL_ERROR", True),
    ],
)
def test_http_failures_are_classified_explicitly(status, code, retryable) -> None:
    provider = DaDataCounterpartyLookupProvider(
        enabled_config(),
        requester=lambda *args: (status, b"{}"),
    )
    with pytest.raises(CounterpartyLookupProviderError) as excinfo:
        provider.lookup(inn_query())
    assert excinfo.value.code == code
    assert excinfo.value.retryable is retryable


def test_empty_result_is_explicit_not_found() -> None:
    provider = DaDataCounterpartyLookupProvider(
        enabled_config(),
        requester=lambda *args: (200, b'{"suggestions":[]}')
    )
    with pytest.raises(CounterpartyLookupProviderError) as excinfo:
        provider.lookup(inn_query())
    assert excinfo.value.code == "NOT_FOUND"
    assert excinfo.value.retryable is False


def test_invalid_json_is_rejected() -> None:
    provider = DaDataCounterpartyLookupProvider(
        enabled_config(),
        requester=lambda *args: (200, b"not-json"),
    )
    with pytest.raises(CounterpartyLookupProviderError) as excinfo:
        provider.lookup(inn_query())
    assert excinfo.value.code == "MALFORMED_PROVIDER_PAYLOAD"


def test_ogrnip_forces_individual_type_filter() -> None:
    calls = []

    def requester(endpoint, api_key, payload, timeout, max_bytes):
        calls.append(payload)
        return 200, sample_response()

    provider = DaDataCounterpartyLookupProvider(enabled_config(), requester=requester)
    query = CounterpartyLookupQuery(
        identifier_type=CounterpartyLookupIdentifierType.OGRNIP,
        identifier="123456789012345",
    )
    provider.lookup(query)
    assert calls[0]["type"] == "INDIVIDUAL"


def test_bounded_retry_retries_only_transient_failures() -> None:
    attempts = {"count": 0}
    delays = []

    def requester(*args):
        attempts["count"] += 1
        if attempts["count"] < 3:
            return 500, b"{}"
        return 200, sample_response()

    provider = DaDataCounterpartyLookupProvider(enabled_config(), requester=requester)
    retrying = BoundedCounterpartyLookup(
        provider,
        max_attempts=3,
        backoff_seconds=0.01,
        sleeper=delays.append,
    )
    result = retrying.lookup(inn_query())
    assert result.tax_id == "7707083893"
    assert attempts["count"] == 3
    assert delays == [0.01, 0.02]


def test_bounded_retry_does_not_retry_403() -> None:
    attempts = {"count": 0}

    def requester(*args):
        attempts["count"] += 1
        return 403, b"{}"

    provider = DaDataCounterpartyLookupProvider(enabled_config(), requester=requester)
    retrying = BoundedCounterpartyLookup(
        provider,
        max_attempts=3,
        backoff_seconds=0.01,
        sleeper=lambda _: None,
    )
    with pytest.raises(CounterpartyLookupProviderError):
        retrying.lookup(inn_query())
    assert attempts["count"] == 1


def test_response_size_is_bounded() -> None:
    oversized = b"x" * (1024 * 1024 + 1)
    provider = DaDataCounterpartyLookupProvider(
        enabled_config(max_response_bytes=1024),
        requester=lambda *args: (200, oversized),
    )
    with pytest.raises(CounterpartyLookupProviderError) as excinfo:
        provider.lookup(inn_query())
    assert excinfo.value.code == "RESPONSE_TOO_LARGE"
