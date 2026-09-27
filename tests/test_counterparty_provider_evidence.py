from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.application.counterparty_lookup import CounterpartyProviderRecord
from shema_platform.application.counterparty_provider_evidence import (
    CounterpartyProviderEvidenceService,
)
from shema_platform.domain.identity import Identity, IdentityState


@dataclass
class Identities:
    records: list[Identity] = field(default_factory=list)

    def find_by_tax_id(self, tax_id: str):
        return next((item for item in self.records if item.tax_id == tax_id), None)


@dataclass
class EvidenceRepo:
    records: list = field(default_factory=list)

    def add(self, value) -> None:
        self.records.append(value)


@dataclass
class QuarantineRepo:
    records: list[dict] = field(default_factory=list)

    def add(self, **value) -> None:
        self.records.append(value)


@dataclass
class Audits:
    records: list = field(default_factory=list)

    def append(self, value) -> None:
        self.records.append(value)


@dataclass
class UOW:
    identities: Identities
    evidence: EvidenceRepo = field(default_factory=EvidenceRepo)
    quarantine: QuarantineRepo = field(default_factory=QuarantineRepo)
    audits: Audits = field(default_factory=Audits)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def record() -> CounterpartyProviderRecord:
    return CounterpartyProviderRecord(
        provider_id="dadata_organization_api",
        source_ref="https://dadata.ru/api/find-party/",
        canonical_name='ООО "Пример"',
        tax_id="7707083893",
        registration_id="1027700132195",
        legal_status="ACTIVE",
        observed_at_ms=1771891200000,
    )


def test_secondary_provider_does_not_create_canonical_identity() -> None:
    state = UOW(identities=Identities())
    result = CounterpartyProviderEvidenceService(lambda: state).ingest(
        record(),
        actor_id="operator",
        claim_confidence=0.8,
        expires_at=datetime.now(UTC) + timedelta(days=7),
        correlation_id="corr-provider",
    )
    assert result.identity_ref is None
    assert result.quarantined is False
    assert len(state.evidence.records) == 4
    assert len(state.audits.records) == 1


def test_secondary_provider_matches_existing_identity_and_keeps_evidence() -> None:
    existing = Identity(
        identity_id="identity-1",
        canonical_name='ООО "Пример"',
        state=IdentityState.IDENTIFIED,
        tax_id="7707083893",
        registration_id="1027700132195",
    )
    state = UOW(identities=Identities(records=[existing]))
    result = CounterpartyProviderEvidenceService(lambda: state).ingest(
        record(),
        actor_id="operator",
        claim_confidence=0.8,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    assert result.identity_ref == "identity-1"
    assert result.subject_ref == "identity-1"
    assert result.quarantined is False


def test_secondary_provider_conflict_is_quarantined() -> None:
    existing = Identity(
        identity_id="identity-1",
        canonical_name='ООО "Другое"',
        state=IdentityState.IDENTIFIED,
        tax_id="7707083893",
        registration_id="1027700132195",
    )
    state = UOW(identities=Identities(records=[existing]))
    result = CounterpartyProviderEvidenceService(lambda: state).ingest(
        record(),
        actor_id="operator",
        claim_confidence=0.8,
        expires_at=datetime.now(UTC) + timedelta(days=7),
    )
    assert result.quarantined is True
    assert result.contradictions[0][0] == "canonical_name"
    assert len(state.quarantine.records) == 1


def test_confidence_and_expiry_are_explicit() -> None:
    state = UOW(identities=Identities())
    now = datetime.now(UTC)
    with pytest.raises(ValueError):
        CounterpartyProviderEvidenceService(lambda: state).ingest(
            record(),
            actor_id="operator",
            claim_confidence=1.1,
            expires_at=now + timedelta(days=1),
        )
    with pytest.raises(ValueError):
        CounterpartyProviderEvidenceService(lambda: state).ingest(
            record(),
            actor_id="operator",
            claim_confidence=0.8,
            expires_at=now - timedelta(seconds=1),
            observed_at=now,
        )
