from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from shema_platform.application.counterparty_lookup import (
    BoundedCounterpartyLookup,
    CounterpartyLookupProvider,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.application.counterparty_provider_evidence import (
    CounterpartyProviderEvidenceResult,
    CounterpartyProviderEvidenceService,
)


@dataclass(frozen=True, slots=True)
class CounterpartyProviderLookupResult:
    provider_record: CounterpartyProviderRecord
    evidence_result: CounterpartyProviderEvidenceResult


class CounterpartyProviderLookupService:
    """Compose one controlled provider lookup with the existing Evidence intake.

    This service owns orchestration only. It never changes provider activation state,
    canonical Identity semantics or persistence authority outside the Evidence boundary.
    """

    def __init__(
        self,
        provider: CounterpartyLookupProvider,
        evidence_service: CounterpartyProviderEvidenceService,
        *,
        max_attempts: int = 3,
        backoff_seconds: float = 0.25,
        sleeper=None,
    ) -> None:
        if sleeper is None:
            self._lookup = BoundedCounterpartyLookup(
                provider,
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
            )
        else:
            self._lookup = BoundedCounterpartyLookup(
                provider,
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
                sleeper=sleeper,
            )
        self._evidence_service = evidence_service

    def execute(
        self,
        query: CounterpartyLookupQuery,
        *,
        actor_id: str,
        claim_confidence: float,
        expires_at: datetime,
        observed_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> CounterpartyProviderLookupResult:
        record = self._lookup.lookup(query)
        evidence_result = self._evidence_service.ingest(
            record,
            actor_id=actor_id,
            claim_confidence=claim_confidence,
            expires_at=expires_at,
            observed_at=observed_at,
            correlation_id=correlation_id,
        )
        return CounterpartyProviderLookupResult(
            provider_record=record,
            evidence_result=evidence_result,
        )
