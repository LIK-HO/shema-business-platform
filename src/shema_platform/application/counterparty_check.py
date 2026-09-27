from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from urllib.parse import urlsplit
from uuid import uuid4

from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.evidence import (
    Evidence,
    EvidenceLifecycle,
    TrustLevel,
    TruthClass,
)
from shema_platform.foundation.ids import Id

OFFICIAL_SOURCE_SUFFIX = ".nalog.ru"
OFFICIAL_SOURCE_HOSTS = {
    "nalog.ru",
    "pb.nalog.ru",
    "service.nalog.ru",
    "www.nalog.ru",
}


class CounterpartyIdentifierType(StrEnum):
    INN = "INN"
    OGRN = "OGRN"
    OGRNIP = "OGRNIP"


class SourceReliability(StrEnum):
    AUTHORITATIVE = "authoritative"
    PRIMARY = "primary"
    TRUSTED_SECONDARY = "trusted_secondary"
    UNVERIFIED = "unverified"


class FreshnessState(StrEnum):
    FRESH = "fresh"
    EXPIRED = "expired"


@dataclass(frozen=True, slots=True)
class CounterpartyObservation:
    identifier_type: CounterpartyIdentifierType
    identifier: str
    canonical_name: str
    tax_id: str | None
    registration_id: str | None
    legal_status: str | None
    source_ref: str
    source_reliability: SourceReliability
    claim_confidence: float
    observed_at: datetime
    expires_at: datetime

    def __post_init__(self) -> None:
        identifier = self.identifier.strip()
        canonical_name = self.canonical_name.strip()
        tax_id = self.tax_id.strip() if self.tax_id else None
        registration_id = (
            self.registration_id.strip() if self.registration_id else None
        )
        legal_status = self.legal_status.strip() if self.legal_status else None

        if not identifier.isdigit():
            raise ValueError("counterparty identifier must contain digits only")
        expected_lengths = {
            CounterpartyIdentifierType.INN: {10, 12},
            CounterpartyIdentifierType.OGRN: {13},
            CounterpartyIdentifierType.OGRNIP: {15},
        }
        if len(identifier) not in expected_lengths[self.identifier_type]:
            raise ValueError(
                f"{self.identifier_type.value} has invalid length"
            )
        if not canonical_name:
            raise ValueError("canonical_name is required")
        if not tax_id and not registration_id:
            raise ValueError("tax_id or registration_id is required")

        parsed = urlsplit(self.source_ref.strip())
        if parsed.scheme != "https" or not parsed.hostname:
            raise ValueError("source_ref must be an HTTPS URL")
        hostname = parsed.hostname.lower()
        if hostname not in OFFICIAL_SOURCE_HOSTS and not hostname.endswith(
            OFFICIAL_SOURCE_SUFFIX
        ):
            raise ValueError("counterparty source must be an official nalog.ru URL")

        if self.source_reliability is not SourceReliability.AUTHORITATIVE:
            raise ValueError(
                "manual counterparty checks require an authoritative source"
            )
        if not 0.0 <= self.claim_confidence <= 1.0:
            raise ValueError("claim_confidence must be between 0 and 1")
        if self.expires_at < self.observed_at:
            raise ValueError("expires_at cannot precede observed_at")

        object.__setattr__(self, "identifier", identifier)
        object.__setattr__(self, "canonical_name", canonical_name)
        object.__setattr__(self, "tax_id", tax_id)
        object.__setattr__(self, "registration_id", registration_id)
        object.__setattr__(self, "legal_status", legal_status)
        object.__setattr__(self, "source_ref", self.source_ref.strip())


@dataclass(frozen=True, slots=True)
class CounterpartyContradiction:
    field: str
    existing_value: str
    observed_value: str


@dataclass(frozen=True, slots=True)
class CounterpartyCheckResult:
    subject_ref: str
    identity: Identity | None
    freshness: FreshnessState
    evidence_ids: tuple[str, ...]
    contradictions: tuple[CounterpartyContradiction, ...]
    quarantined: bool
    operator_brief: str


def _evidence_id() -> str:
    return str(uuid4())

def _freshness(
    expires_at: datetime,
    *,
    at: datetime,
) -> FreshnessState:
    return FreshnessState.FRESH if at <= expires_at else FreshnessState.EXPIRED


class CounterpartyCheckService:
    """Manual authoritative-source intake over the existing identity/evidence contracts.

    The operator performs the lookup against an official FNS source. This service
    validates the observation, resolves the canonical identity by INN when possible,
    records traceable evidence, quarantines contradictions, and returns a compact
    operator brief. It does not call external providers.
    """

    def __init__(self, unit_of_work_factory):
        self._unit_of_work_factory = unit_of_work_factory

    def check(
        self,
        observation: CounterpartyObservation,
        *,
        actor_id: str,
        correlation_id: str | None = None,
        now: datetime | None = None,
    ) -> CounterpartyCheckResult:
        actor_id = actor_id.strip()
        if not actor_id:
            raise ValueError("actor_id is required")

        current_time = now or datetime.now(UTC)
        subject_key = (
            f"counterparty:{observation.identifier_type.value.lower()}:"
            f"{observation.identifier}"
        )

        with self._unit_of_work_factory() as uow:
            identity = None
            contradictions: list[CounterpartyContradiction] = []

            if observation.tax_id:
                identity = uow.identities.find_by_tax_id(observation.tax_id)
                if identity is None:
                    identity = Identity(
                        identity_id=str(Id.new()),
                        canonical_name=observation.canonical_name,
                        state=IdentityState.IDENTIFIED,
                        tax_id=observation.tax_id,
                        registration_id=observation.registration_id,
                    )
                    uow.identities.add(identity)
                else:
                    if (
                        identity.canonical_name.strip()
                        and identity.canonical_name.strip()
                        != observation.canonical_name
                    ):
                        contradictions.append(
                            CounterpartyContradiction(
                                field="canonical_name",
                                existing_value=identity.canonical_name,
                                observed_value=observation.canonical_name,
                            )
                        )
                    if (
                        identity.registration_id
                        and observation.registration_id
                        and identity.registration_id != observation.registration_id
                    ):
                        contradictions.append(
                            CounterpartyContradiction(
                                field="registration_id",
                                existing_value=identity.registration_id,
                                observed_value=observation.registration_id,
                            )
                        )

            subject_ref = identity.identity_id if identity else subject_key

            claims = [
                ("canonical_name", observation.canonical_name),
                ("tax_id", observation.tax_id),
                ("registration_id", observation.registration_id),
                ("legal_status", observation.legal_status),
            ]
            evidence_ids: list[str] = []
            for field, value in claims:
                if not value:
                    continue
                claim = f"{field}={value}"
                evidence = Evidence(
                    evidence_id=_evidence_id(
                    ),
                    subject_ref=subject_ref,
                    claim=claim,
                    source_ref=observation.source_ref,
                    observed_at=observation.observed_at,
                    captured_at=current_time,
                    truth_class=TruthClass.EVIDENCE,
                    trust_level=TrustLevel.T1_OBSERVED,
                    confidence=observation.claim_confidence,
                    provenance={
                        "source_reliability": observation.source_reliability.value,
                        "identifier_type": observation.identifier_type.value,
                        "identifier": observation.identifier,
                    },
                    expires_at=observation.expires_at,
                    lifecycle=EvidenceLifecycle.ACTIVE,
                )
                uow.evidence.add(evidence)
                evidence_ids.append(evidence.evidence_id)

            quarantined = bool(contradictions)
            if quarantined:
                uow.quarantine.add(
                    object_type="counterparty_check",
                    object_ref=subject_ref,
                    reason_code="counterparty_observation_conflict",
                    payload={
                        "identifier_type": observation.identifier_type.value,
                        "identifier": observation.identifier,
                        "contradictions": [
                            {
                                "field": item.field,
                                "existing": item.existing_value,
                                "observed": item.observed_value,
                            }
                            for item in contradictions
                        ],
                    },
                )

            occurred_at = current_time
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid4()),
                    actor_id=actor_id,
                    action="counterparty.check",
                    resource_type="counterparty_check",
                    resource_id=subject_ref,
                    outcome="quarantined" if quarantined else "success",
                    occurred_at=occurred_at,
                    metadata={
                        "identifier_type": observation.identifier_type.value,
                        "identifier": observation.identifier,
                        "source_ref": observation.source_ref,
                        "source_reliability": observation.source_reliability.value,
                        "evidence_count": len(evidence_ids),
                        "contradiction_count": len(contradictions),
                    },
                    correlation_id=correlation_id,
                )
            )

        freshness = _freshness(observation.expires_at, at=current_time)
        identity_line = (
            f"{observation.canonical_name}; "
            f"ИНН {observation.tax_id or 'не указан'}; "
            f"регистрационный номер "
            f"{observation.registration_id or 'не указан'}."
        )
        conflict_line = (
            f" Конфликты: {', '.join(item.field for item in contradictions)}."
            if contradictions
            else " Конфликтов с текущей canonical identity не выявлено."
        )
        next_step = (
            " Требуется ручная сверка конфликта до квалификации."
            if quarantined
            else " Следующий безопасный шаг: независимая проверка материала по другому источнику."
        )
        brief = (
            f"{identity_line} Источник: {observation.source_ref}. "
            f"Надёжность источника: {observation.source_reliability.value}; "
            f"уверенность утверждений: {observation.claim_confidence:.2f}. "
            f"Свежесть: {freshness.value}."
            f"{conflict_line}{next_step}"
        )

        return CounterpartyCheckResult(
            subject_ref=subject_ref,
            identity=identity,
            freshness=freshness,
            evidence_ids=tuple(evidence_ids),
            contradictions=tuple(contradictions),
            quarantined=quarantined,
            operator_brief=brief,
        )
