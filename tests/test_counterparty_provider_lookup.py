from __future__ import annotations

from datetime import UTC, datetime, timedelta

from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupIdentifierType,
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.application.counterparty_provider_evidence import (
    CounterpartyProviderEvidenceService,
)
from shema_platform.application.counterparty_provider_lookup import (
    CounterpartyProviderLookupService,
)
from shema_platform.domain.identity import Identity, IdentityState


class Identities:
    def __init__(self, records=None):
        self.records = list(records or [])

    def find_by_tax_id(self, tax_id: str):
        return next((item for item in self.records if item.tax_id == tax_id), None)


class Evidence:
    def __init__(self):
        self.records = []

    def add(self, value):
        self.records.append(value)


class Quarantine:
    def __init__(self):
        self.records = []

    def add(self, **value):
        self.records.append(value)


class Audits:
    def __init__(self):
        self.records = []

    def append(self, value):
        self.records.append(value)


class UOW:
    def __init__(self, identities):
        self.identities = identities
        self.evidence = Evidence()
        self.quarantine = Quarantine()
        self.audits = Audits()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class StubProvider:
    def __init__(self, *, failures: int = 0) -> None:
        self.failures = failures
        self.calls = 0

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        self.calls += 1
        if self.calls <= self.failures:
            raise CounterpartyLookupProviderError(
                "PROVIDER_INTERNAL_ERROR",
                "transient",
                retryable=True,
            )
        return CounterpartyProviderRecord(
            provider_id="dadata_organization_api",
            source_ref="https://dadata.ru/api/find-party/",
            canonical_name='ООО "Пример"',
            tax_id="7707083893",
            registration_id="1027700132195",
            legal_status="ACTIVE",
        )


def query() -> CounterpartyLookupQuery:
    return CounterpartyLookupQuery(
        identifier_type=CounterpartyLookupIdentifierType.INN,
        identifier="7707083893",
    )


def test_lookup_service_composes_retry_and_evidence_intake() -> None:
    state = UOW(identities=Identities())
    provider = StubProvider(failures=2)
    delays: list[float] = []
    service = CounterpartyProviderLookupService(
        provider,
        CounterpartyProviderEvidenceService(lambda: state),
        max_attempts=3,
        backoff_seconds=0.01,
        sleeper=delays.append,
    )

    result = service.execute(
        query(),
        actor_id="operator",
        claim_confidence=0.8,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        correlation_id="corr-lookup",
    )

    assert provider.calls == 3
    assert delays == [0.01, 0.02]
    assert result.provider_record.provider_id == "dadata_organization_api"
    assert len(result.evidence_result.evidence_ids) == 4
    assert result.evidence_result.identity_ref is None


def test_lookup_service_uses_existing_identity_without_promoting_secondary_truth() -> None:
    existing = Identity(
        identity_id="identity-1",
        canonical_name='ООО "Пример"',
        state=IdentityState.IDENTIFIED,
        tax_id="7707083893",
        registration_id="1027700132195",
    )
    state = UOW(identities=Identities(records=[existing]))
    service = CounterpartyProviderLookupService(
        StubProvider(),
        CounterpartyProviderEvidenceService(lambda: state),
        sleeper=lambda _: None,
    )

    result = service.execute(
        query(),
        actor_id="operator",
        claim_confidence=0.8,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )

    assert result.evidence_result.identity_ref == "identity-1"
    assert state.identities.records == [existing]
