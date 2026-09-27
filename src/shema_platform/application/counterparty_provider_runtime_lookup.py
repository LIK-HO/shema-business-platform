from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime

from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupProvider,
    CounterpartyLookupQuery,
)
from shema_platform.application.counterparty_provider_evidence import (
    CounterpartyProviderEvidenceService,
)
from shema_platform.application.counterparty_provider_lookup import (
    CounterpartyProviderLookupResult,
    CounterpartyProviderLookupService,
)
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import AuthorizationError


@dataclass(frozen=True, slots=True)
class CounterpartyProviderRuntimeLookupService:
    """Runtime command boundary for provider lookup -> retry -> Evidence."""

    provider_id: str
    provider_resolver: Callable[[], CounterpartyLookupProvider]
    evidence_service: CounterpartyProviderEvidenceService
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    sleeper: Callable[[float], None] | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if self.max_attempts < 1 or self.max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")

    def execute(
        self,
        query: CounterpartyLookupQuery,
        *,
        actor_id: str,
        permissions: frozenset[Permission],
        claim_confidence: float,
        expires_at: datetime,
        observed_at: datetime | None = None,
        correlation_id: str | None = None,
    ) -> CounterpartyProviderLookupResult:
        self._authorize(actor_id, permissions)

        provider = self.provider_resolver()
        result_service = CounterpartyProviderLookupService(
            provider,
            self.evidence_service,
            max_attempts=self.max_attempts,
            backoff_seconds=self.backoff_seconds,
            sleeper=self.sleeper,
        )
        result = result_service.execute(
            query,
            actor_id=actor_id,
            claim_confidence=claim_confidence,
            expires_at=expires_at,
            observed_at=observed_at,
            correlation_id=correlation_id,
        )
        if result.provider_record.provider_id != self.provider_id:
            raise RuntimeError("runtime provider identity mismatch")
        return result

    def _authorize(
        self,
        actor_id: str,
        permissions: frozenset[Permission],
    ) -> None:
        try:
            RBACAuthorizer(
                (
                    AuthorizationSubject(
                        actor_id=actor_id,
                        permissions=permissions,
                    ),
                )
            ).require(actor_id, Permission.INTELLIGENCE_PROVIDER_LOOKUP)
        except AuthorizationError:
            raise
