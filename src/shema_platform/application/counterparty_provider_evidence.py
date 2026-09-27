from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from shema_platform.application.counterparty_lookup import CounterpartyProviderRecord
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.evidence import (
    Evidence,
    EvidenceLifecycle,
    TrustLevel,
    TruthClass,
)


@dataclass(frozen=True, slots=True)
class CounterpartyProviderEvidenceResult:
    subject_ref: str
    identity_ref: str | None
    evidence_ids: tuple[str, ...]
    contradictions: tuple[tuple[str, str, str], ...]
    quarantined: bool


class CounterpartyProviderEvidenceService:
    """Conservative provider-observation intake into the existing Evidence boundary.

    Secondary provider observations may resolve an existing identity, but they do
    not create or promote canonical Identity state by themselves.
    """

    def __init__(self, unit_of_work_factory):
        self._unit_of_work_factory = unit_of_work_factory

    def ingest(
        self,
        record: CounterpartyProviderRecord,
        *,
        actor_id: str,
        claim_confidence: float,
        expires_at: datetime,
        observed_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> CounterpartyProviderEvidenceResult:
        actor_id = actor_id.strip()
        if not actor_id:
            raise ValueError("actor_id is required")
        if not 0.0 <= claim_confidence <= 1.0:
            raise ValueError("claim_confidence must be between 0 and 1")

        now = datetime.now(UTC)
        observed = observed_at or now
        if expires_at < observed:
            raise ValueError("expires_at cannot precede observed_at")

        with self._unit_of_work_factory() as uow:
            identity = (
                uow.identities.find_by_tax_id(record.tax_id)
                if record.tax_id
                else None
            )
            identity_ref = identity.identity_id if identity else None
            subject_ref = identity_ref or (
                f"counterparty:provider:{record.provider_id}:"
                f"{record.tax_id or record.registration_id}"
            )

            contradictions: list[tuple[str, str, str]] = []
            if identity is not None:
                if (
                    identity.canonical_name.strip()
                    and identity.canonical_name.strip() != record.canonical_name.strip()
                ):
                    contradictions.append(
                        ("canonical_name", identity.canonical_name, record.canonical_name)
                    )
                if (
                    identity.registration_id
                    and record.registration_id
                    and identity.registration_id != record.registration_id
                ):
                    contradictions.append(
                        ("registration_id", identity.registration_id, record.registration_id)
                    )

            claims = [
                ("canonical_name", record.canonical_name),
                ("tax_id", record.tax_id),
                ("registration_id", record.registration_id),
                ("legal_status", record.legal_status),
            ]
            evidence_ids: list[str] = []
            for field, value in claims:
                if not value:
                    continue
                evidence = Evidence(
                    evidence_id=str(uuid4()),
                    subject_ref=subject_ref,
                    claim=f"{field}={value}",
                    source_ref=record.source_ref,
                    observed_at=observed,
                    captured_at=now,
                    truth_class=TruthClass.EVIDENCE,
                    trust_level=TrustLevel.T1_OBSERVED,
                    confidence=claim_confidence,
                    provenance={
                        "provider_id": record.provider_id,
                        "source_reliability": "trusted_secondary",
                        "identifier": record.tax_id or record.registration_id or "",
                        "provider_actuality_ms": (
                            str(record.observed_at_ms)
                            if record.observed_at_ms is not None
                            else ""
                        ),
                    },
                    expires_at=expires_at,
                    lifecycle=EvidenceLifecycle.ACTIVE,
                )
                uow.evidence.add(evidence)
                evidence_ids.append(evidence.evidence_id)

            quarantined = bool(contradictions)
            if quarantined:
                uow.quarantine.add(
                    object_type="counterparty_provider_evidence",
                    object_ref=subject_ref,
                    reason_code="provider_observation_conflict",
                    payload={
                        "provider_id": record.provider_id,
                        "contradictions": [
                            {
                                "field": field,
                                "existing": existing,
                                "observed": observed_value,
                            }
                            for field, existing, observed_value in contradictions
                        ],
                    },
                )

            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid4()),
                    actor_id=actor_id,
                    action="counterparty.provider_evidence",
                    resource_type="counterparty_provider_evidence",
                    resource_id=subject_ref,
                    outcome="quarantined" if quarantined else "success",
                    occurred_at=now,
                    metadata={
                        "provider_id": record.provider_id,
                        "source_ref": record.source_ref,
                        "evidence_count": len(evidence_ids),
                        "contradiction_count": len(contradictions),
                    },
                    correlation_id=correlation_id,
                )
            )

        return CounterpartyProviderEvidenceResult(
            subject_ref=subject_ref,
            identity_ref=identity_ref,
            evidence_ids=tuple(evidence_ids),
            contradictions=tuple(contradictions),
            quarantined=quarantined,
        )
