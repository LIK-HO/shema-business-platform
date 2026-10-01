from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from shema_platform.application.counterparty_check import (
    CounterpartyCheckService,
    CounterpartyIdentifierType,
    CounterpartyObservation,
    FreshnessState,
    SourceReliability,
)
from shema_platform.domain.identity import Identity, IdentityState


@dataclass
class MemoryIdentities:
    records: list[Identity] = field(default_factory=list)

    def get(self, identity_id: str):
        return next(
            (item for item in self.records if item.identity_id == identity_id),
            None,
        )

    def find_by_tax_id(self, tax_id: str):
        return next(
            (item for item in self.records if item.tax_id == tax_id),
            None,
        )

    def add(self, identity: Identity) -> None:
        self.records.append(identity)


@dataclass
class MemoryEvidence:
    records: list = field(default_factory=list)

    def add(self, evidence) -> None:
        self.records.append(evidence)


@dataclass
class MemoryQuarantine:
    records: list[dict] = field(default_factory=list)

    def add(self, **record) -> None:
        self.records.append(record)


@dataclass
class MemoryAudits:
    records: list = field(default_factory=list)

    def append(self, record) -> None:
        self.records.append(record)


class StubRepository:
    def __getattr__(self, name):
        def unsupported(*args, **kwargs):
            raise AssertionError(f"unexpected repository call: {name}")
        return unsupported


@dataclass
class MemoryUnitOfWork:
    identities: MemoryIdentities
    evidence: MemoryEvidence = field(default_factory=MemoryEvidence)
    quarantine: MemoryQuarantine = field(default_factory=MemoryQuarantine)
    audits: MemoryAudits = field(default_factory=MemoryAudits)
    idempotency: object = field(default_factory=StubRepository)
    outbox: object = field(default_factory=StubRepository)
    jobs: object = field(default_factory=StubRepository)
    commercial_actions: object = field(default_factory=StubRepository)
    orders: object = field(default_factory=StubRepository)
    economics: object = field(default_factory=StubRepository)
    ai_runs: object = field(default_factory=StubRepository)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def observation(**overrides):
    values = {
        "identifier_type": CounterpartyIdentifierType.INN,
        "identifier": "7707083893",
        "canonical_name": 'ООО "Пример"',
        "tax_id": "7707083893",
        "registration_id": "1027700132195",
        "legal_status": "Действующая организация",
        "source_ref": "https://pb.nalog.ru/",
        "source_reliability": SourceReliability.AUTHORITATIVE,
        "claim_confidence": 0.95,
        "observed_at": datetime(2026, 9, 26, 10, tzinfo=UTC),
        "expires_at": datetime(2026, 10, 3, 10, tzinfo=UTC),
    }
    values.update(overrides)
    return CounterpartyObservation(**values)


def make_service(state: MemoryUnitOfWork):
    return CounterpartyCheckService(lambda: state)


def test_manual_counterparty_check_resolves_identity_and_persists_evidence():
    state = MemoryUnitOfWork(identities=MemoryIdentities())
    result = make_service(state).check(
        observation(),
        actor_id="operator",
        correlation_id="corr-1",
        now=datetime(2026, 9, 27, tzinfo=UTC),
    )

    assert result.identity is not None
    assert result.identity.state is IdentityState.IDENTIFIED
    assert result.freshness is FreshnessState.FRESH
    assert result.contradictions == ()
    assert result.quarantined is False
    assert len(result.evidence_ids) == 4
    assert len(state.identities.records) == 1
    assert len(state.evidence.records) == 4
    assert len(state.audits.records) == 1
    assert "Конфликтов" in result.operator_brief


def test_repeated_manual_checks_create_distinct_evidence_observations():
    state = MemoryUnitOfWork(identities=MemoryIdentities())
    service = make_service(state)

    first = service.check(
        observation(),
        actor_id="operator",
        now=datetime(2026, 9, 27, tzinfo=UTC),
    )
    second = service.check(
        observation(),
        actor_id="operator",
        now=datetime(2026, 9, 27, 0, 1, tzinfo=UTC),
    )

    assert set(first.evidence_ids).isdisjoint(second.evidence_ids)
    assert len(state.evidence.records) == 8


def test_manual_counterparty_check_quarantines_identity_conflict():
    existing = Identity(
        identity_id="identity-existing",
        canonical_name='ООО "Старое имя"',
        state=IdentityState.IDENTIFIED,
        tax_id="7707083893",
        registration_id="1027700132195",
    )
    state = MemoryUnitOfWork(
        identities=MemoryIdentities(records=[existing]),
    )

    result = make_service(state).check(
        observation(canonical_name='ООО "Новое имя"'),
        actor_id="operator",
        now=datetime(2026, 9, 27, tzinfo=UTC),
    )

    assert result.identity == existing
    assert result.quarantined is True
    assert [item.field for item in result.contradictions] == ["canonical_name"]
    assert len(state.quarantine.records) == 1
    assert state.audits.records[0].outcome == "quarantined"


@pytest.mark.parametrize(
    ("identifier_type", "identifier"),
    [
        (CounterpartyIdentifierType.INN, "123"),
        (CounterpartyIdentifierType.OGRN, "770708389312"),
        (CounterpartyIdentifierType.OGRNIP, "1234567890123"),
        (CounterpartyIdentifierType.INN, "77070838A3"),
    ],
)
def test_counterparty_identifier_is_structurally_validated(identifier_type, identifier):
    with pytest.raises(ValueError):
        observation(
            identifier_type=identifier_type,
            identifier=identifier,
        )


def test_counterparty_observation_requires_authoritative_source():
    with pytest.raises(ValueError, match="authoritative source"):
        observation(source_reliability=SourceReliability.PRIMARY)


def test_counterparty_observation_requires_official_source_and_expiry():
    with pytest.raises(ValueError, match="official nalog.ru"):
        observation(source_ref="https://example.com/check")

    with pytest.raises(ValueError, match="expires_at"):
        observation(
            expires_at=datetime(2026, 9, 26, 9, tzinfo=UTC),
        )


def test_expired_observation_is_explicitly_marked_expired():
    state = MemoryUnitOfWork(identities=MemoryIdentities())
    result = make_service(state).check(
        observation(
            expires_at=datetime(2026, 9, 26, 11, tzinfo=UTC),
        ),
        actor_id="operator",
        now=datetime(2026, 9, 27, tzinfo=UTC),
    )

    assert result.freshness is FreshnessState.EXPIRED
