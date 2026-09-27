from __future__ import annotations

from dataclasses import dataclass

from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DADATA_PROVIDER_ID,
    DaDataActivationReadiness,
    DaDataControlledActivationGate,
    GatedDaDataCounterpartyLookupProvider,
)
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import AuthorizationError


@dataclass(frozen=True, slots=True)
class CounterpartyProviderActivationRequest:
    provider_id: str
    actor_id: str
    reason: str
    operator_authorized: bool
    activation_version: str
    correlation_id: str

    def __post_init__(self) -> None:
        if self.provider_id != DADATA_PROVIDER_ID:
            raise ValueError("unsupported counterparty provider")
        if not self.actor_id.strip():
            raise ValueError("actor_id is required")
        if not self.reason.strip():
            raise ValueError("reason is required")
        if not self.activation_version.strip():
            raise ValueError("activation_version is required")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id is required")


@dataclass(frozen=True, slots=True)
class CounterpartyProviderActivationResponse:
    provider_id: str
    enabled: bool
    activated_by: str | None
    activation_version: str | None
    rollback_by: str | None
    rollback_reason: str | None


class CounterpartyProviderActivationService:
    """Authenticated application edge for explicit provider binding control."""

    def __init__(
        self,
        *,
        gate: DaDataControlledActivationGate,
        configuration: DaDataConfiguration,
        readiness: DaDataActivationReadiness,
    ) -> None:
        self._gate = gate
        self._configuration = configuration
        self._readiness = readiness

    def activate(
        self,
        request: CounterpartyProviderActivationRequest,
        *,
        permissions: frozenset[Permission],
    ) -> CounterpartyProviderActivationResponse:
        self._authorize(
            request.actor_id,
            permissions,
            Permission.INTELLIGENCE_PROVIDER_ACTIVATE,
        )
        if not request.operator_authorized:
            raise AuthorizationError(
                "counterparty provider activation requires explicit operator authorization"
            )
        self._gate.activate(
            self._configuration,
            readiness=self._readiness,
            activated_by=request.actor_id,
            activation_version=request.activation_version,
            correlation_id=request.correlation_id,
        )
        return self.status()

    def rollback(
        self,
        *,
        provider_id: str,
        actor_id: str,
        reason: str,
        operator_authorized: bool,
        correlation_id: str,
        permissions: frozenset[Permission],
    ) -> CounterpartyProviderActivationResponse:
        if provider_id != DADATA_PROVIDER_ID:
            raise ValueError("unsupported counterparty provider")
        if not actor_id.strip() or not reason.strip() or not correlation_id.strip():
            raise ValueError("actor_id, reason and correlation_id are required")
        self._authorize(
            actor_id,
            permissions,
            Permission.INTELLIGENCE_PROVIDER_ROLLBACK,
        )
        if not operator_authorized:
            raise AuthorizationError(
                "counterparty provider rollback requires explicit operator authorization"
            )
        self._gate.rollback(
            rolled_back_by=actor_id,
            reason=reason,
            correlation_id=correlation_id,
        )
        return self.status()

    def provider(self) -> GatedDaDataCounterpartyLookupProvider:
        return self._gate.provider()

    def status(self) -> CounterpartyProviderActivationResponse:
        state = self._gate.state
        return CounterpartyProviderActivationResponse(
            provider_id=state.provider_id,
            enabled=state.enabled,
            activated_by=state.activated_by,
            activation_version=state.activation_version,
            rollback_by=state.rollback_by,
            rollback_reason=state.rollback_reason,
        )

    @staticmethod
    def _authorize(
        actor_id: str,
        permissions: frozenset[Permission],
        permission: Permission,
    ) -> None:
        RBACAuthorizer(
            (
                AuthorizationSubject(
                    actor_id=actor_id,
                    permissions=permissions,
                ),
            )
        ).require(actor_id, permission)
