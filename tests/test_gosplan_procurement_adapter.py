from __future__ import annotations

import json

from shema_platform.adapters.procurement.gosplan import (
    GosplanConfiguration,
    GosplanProcurementProvider,
)
from shema_platform.application.procurement import (
    ProcurementCollection,
    ProcurementLaw,
    ProcurementProviderError,
    ProcurementQuery,
)


def body(items):
    return json.dumps(items).encode("utf-8")


def query():
    return ProcurementQuery(
        law=ProcurementLaw.FZ44,
        collection=ProcurementCollection.PURCHASES,
        limit=10,
        skip=20,
        reg_number="0372200283826000023",
        sort="max_price_desc",
    )


def provider(requester):
    return GosplanProcurementProvider(
        GosplanConfiguration(
            endpoint="https://v2test.gosplan.info",
            enabled=True,
        ),
        requester=requester,
    )


def test_builds_documented_path_paging_and_reg_number_filter():
    seen = {}

    def requester(url, api_key, timeout, max_response):
        seen.update({"url": url, "api_key": api_key})
        return 200, body(
            [
                {
                    "regNumber": "0372200283826000023",
                    "name": "Подъём оборудования",
                    "customerName": 'ООО "Заказчик"',
                    "customerInn": "7707083893",
                    "max_price": 100000,
                    "status": "planned",
                }
            ]
        )

    result = provider(requester).search(query())

    assert "/fz44/purchases?" in seen["url"]
    assert "limit=10" in seen["url"]
    assert "skip=20" in seen["url"]
    assert "regNumber=0372200283826000023" in seen["url"]
    assert "sort=max_price_desc" in seen["url"]
    assert result.items[0].external_id == "0372200283826000023"
    assert result.items[0].customer_tax_id == "7707083893"


def test_disabled_provider_fails_closed():
    provider = GosplanProcurementProvider(
        GosplanConfiguration(endpoint="https://v2test.gosplan.info", enabled=False),
        requester=lambda *_: (200, b"[]"),
    )

    try:
        provider.search(query())
    except ProcurementProviderError as exc:
        assert exc.code == "PROVIDER_DISABLED"
    else:
        raise AssertionError("disabled provider must fail closed")


def test_rate_limit_is_retryable():
    def requester(*_):
        return 429, b"{}"

    try:
        provider(requester).search(query())
    except ProcurementProviderError as exc:
        assert exc.code == "PROVIDER_RATE_LIMIT"
        assert exc.retryable is True
    else:
        raise AssertionError("429 must be retryable")


def test_500_is_retryable_and_malformed_json_fails_closed():
    def requester(*_):
        return 500, b"{}"

    try:
        provider(requester).search(query())
    except ProcurementProviderError as exc:
        assert exc.code == "PROVIDER_INTERNAL_ERROR"
        assert exc.retryable is True
    else:
        raise AssertionError("5xx must be retryable")

    def malformed(*_):
        return 200, b"{not-json"

    try:
        provider(malformed).search(query())
    except ProcurementProviderError as exc:
        assert exc.code == "MALFORMED_PROVIDER_PAYLOAD"
    else:
        raise AssertionError("malformed payload must fail closed")
