from datetime import UTC, datetime
from decimal import Decimal

from shema_platform.application.procurement import (
    ProcurementCollection,
    ProcurementLaw,
    ProcurementMonitor,
    ProcurementOpportunity,
    ProcurementProviderError,
    ProcurementQuery,
    ProcurementSearchResult,
    ProcurementWatchState,
)


class FakeProvider:
    provider_id = "fixture-procurement"

    def __init__(self, pages):
        self.pages = list(pages)
        self.calls = 0

    def search(self, query):
        self.calls += 1
        return self.pages.pop(0)


def opportunity(
    *,
    external_id="1",
    title="Подъём оборудования",
    stage="planned",
):
    return ProcurementOpportunity(
        provider_id="fixture-procurement",
        source_ref="https://fixture.example/procurement",
        external_id=external_id,
        law=ProcurementLaw.FZ44,
        collection=ProcurementCollection.PURCHASES,
        title=title,
        customer_name='ООО "Заказчик"',
        customer_tax_id="7707083893",
        max_price=Decimal("100000"),
        published_at=datetime(2026, 9, 28, tzinfo=UTC),
        deadline_at=datetime(2026, 10, 10, tzinfo=UTC),
        stage=stage,
        source_url="https://fixture.example/tender/1",
    )


def query():
    return ProcurementQuery(
        law=ProcurementLaw.FZ44,
        collection=ProcurementCollection.PURCHASES,
        limit=10,
    )


def page(*items):
    return ProcurementSearchResult(
        items=tuple(items),
        has_more=False,
        next_page_offset=len(items),
        observed_at=datetime(2026, 9, 28, tzinfo=UTC),
    )


def test_first_poll_returns_new_items_and_stores_cursor():
    provider = FakeProvider([page(opportunity())])
    monitor = ProcurementMonitor(provider, max_attempts=1)

    result = monitor.poll(query(), ProcurementWatchState())

    assert [item.external_id for item in result.new_items] == ["1"]
    assert result.changed_items == ()
    assert result.state.cursor == "1"
    assert result.state.fingerprints["fixture-procurement:1"] == opportunity().fingerprint


def test_repeated_poll_is_idempotent_and_change_is_visible():
    provider = FakeProvider(
        [
            page(opportunity()),
            page(opportunity(title="Подъём оборудования ночью")),
            page(opportunity(external_id="2", title="Такелаж")),
        ]
    )
    monitor = ProcurementMonitor(provider, max_attempts=1)

    state = ProcurementWatchState()
    first = monitor.poll(query(), state)
    second = monitor.poll(query(), first.state)
    third = monitor.poll(query(), second.state)

    assert [item.external_id for item in first.new_items] == ["1"]
    assert second.new_items == ()
    assert [item.external_id for item in second.changed_items] == ["1"]
    assert [item.external_id for item in third.new_items] == ["2"]

def test_rate_limit_is_bounded_then_recovers_without_duplicate_signal():
    class RecoveringProvider:
        provider_id = "fixture-procurement"

        def __init__(self):
            self.calls = 0

        def search(self, query):
            self.calls += 1
            if self.calls == 1:
                raise ProcurementProviderError(
                    "PROVIDER_RATE_LIMIT",
                    "fixture rate limit",
                    retryable=True,
                )
            return page(opportunity())

    provider = RecoveringProvider()
    delays = []
    monitor = ProcurementMonitor(
        provider,
        max_attempts=2,
        sleeper=delays.append,
    )

    result = monitor.poll(query(), ProcurementWatchState())

    assert provider.calls == 2
    assert delays == [0.25]
    assert [item.external_id for item in result.new_items] == ["1"]


def test_material_source_change_is_detected_even_when_title_and_price_are_unchanged():
    provider = FakeProvider(
        [
            page(opportunity()),
            page(
                ProcurementOpportunity(
                    provider_id="fixture-procurement",
                    source_ref="https://fixture.example/procurement",
                    external_id="1",
                    law=ProcurementLaw.FZ44,
                    collection=ProcurementCollection.PURCHASES,
                    title="Подъём оборудования",
                    customer_name='ООО "Заказчик"',
                    customer_tax_id="7707083893",
                    max_price=Decimal("100000"),
                    published_at=datetime(2026, 9, 28, tzinfo=UTC),
                    deadline_at=datetime(2026, 10, 10, tzinfo=UTC),
                    stage="planned",
                    updated_at=datetime(2026, 9, 29, tzinfo=UTC),
                    source_url="https://fixture.example/tender/1-revised",
                )
            ),
        ]
    )
    monitor = ProcurementMonitor(provider, max_attempts=1)

    first = monitor.poll(query(), ProcurementWatchState())
    second = monitor.poll(query(), first.state)

    assert [item.external_id for item in second.changed_items] == ["1"]
