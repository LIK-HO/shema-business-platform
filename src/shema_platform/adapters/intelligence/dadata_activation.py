from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, fields
from datetime import UTC, datetime

from shema_platform.adapters.intelligence.dadata import (
    DaDataConfiguration,
    DaDataCounterpartyLookupProvider,
)
from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupProvider,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.foundation.provider_activation import (
    ProviderActivationState,
    ProviderActivationStateStore,
)
from shema_platform.foundation.telemetry import TelemetrySink, build_event

DADATA_PROVIDER_ID = "dadata_organization_api"


class DaDataActivationError(RuntimeError):
    """Fail-closed controlled DaData activation error."""


@dataclass(frozen=True, slots=True)
class DaDataActivationReadiness:
    source_registry_entry: bool
    authoritative_provider_contract_evidence: bool
    provider_neutral_counterparty_lookup_port: bool
    deterministic_positive_fixture: bool
    deterministic_negative_fixture_matrix: bool
    bounded_retry_policy: bool
    application_timeout_policy: bool
    credential_boundary: bool
    redacted_observability: bool
    kill_switch: bool
    rollback_without_schema_change: bool
    full_release_ci: bool

    @property
    def ready(self) -> bool:
        return all(getattr(self, item.name) for item in fields(self))

    def require_ready(self) -> None:
        if not self.ready:
            failed = [
                item.name for item in fields(self) if not getattr(self, item.name)
            ]
            raise DaDataActivationError(
                "DaData activation readiness is incomplete: " + ", ".join(failed)
            )


@dataclass(frozen=True, slots=True)
class DaDataActivationState:
    enabled: bool
    provider_id: str = DADATA_PROVIDER_ID
    activated_by: str | None = None
    activated_at: datetime | None = None
    configuration_endpoint: str | None = None
    activation_version: str | None = None
    rollback_by: str | None = None
    rollback_at: datetime | None = None
    rollback_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if self.enabled:
            if not self.activated_by or not self.activated_by.strip():
                raise ValueError("enabled state requires activated_by")
            if self.activated_at is None or self.activated_at.tzinfo is None:
                raise ValueError("enabled state requires activated_at")
            if not self.configuration_endpoint or not self.configuration_endpoint.strip():
                raise ValueError("enabled state requires configuration_endpoint")
            if not self.activation_version or not self.activation_version.strip():
                raise ValueError("enabled state requires activation_version")


class GatedDaDataCounterpartyLookupProvider:
    provider_id = DADATA_PROVIDER_ID

    def __init__(
        self,
        provider: CounterpartyLookupProvider,
        *,
        gate: DaDataControlledActivationGate,
        activation_version: str,
        activated_at: datetime | None,
    ) -> None:
        self._provider = provider
        self._gate = gate
        self._activation_version = activation_version
        self._activated_at = activated_at

    def binding_matches(
        self,
        *,
        activation_version: str,
        activated_at: datetime | None,
    ) -> bool:
        return (
            self._activation_version == activation_version
            and self._activated_at == activated_at
        )

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        if not self._gate.allows_request(
            activation_version=self._activation_version,
            activated_at=self._activated_at,
        ):
            raise DaDataActivationError(
                "DaData provider binding is stale or disabled"
            )
        return self._provider.lookup(query)


class DaDataControlledActivationGate:
    """Process-local provider binding gate; construction never activates traffic."""

    def __init__(
        self,
        *,
        telemetry: TelemetrySink,
        activation_state_store: ProviderActivationStateStore,
        provider_factory: Callable[[DaDataConfiguration], CounterpartyLookupProvider]
        | None = None,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        if telemetry is None:
            raise ValueError("telemetry is required")
        self._telemetry = telemetry
        self._activation_state_store = activation_state_store
        self._provider_factory = provider_factory or (
            lambda configuration: DaDataCounterpartyLookupProvider(configuration)
        )
        self._now = now or (lambda: datetime.now(UTC))
        self._state = DaDataActivationState(enabled=False)
        self._provider: GatedDaDataCounterpartyLookupProvider | None = None

    @property
    def state(self) -> DaDataActivationState:
        canonical = self._activation_state_store.get(DADATA_PROVIDER_ID)
        if canonical is None:
            return self._state
        return DaDataActivationState(
            enabled=canonical.enabled,
            provider_id=canonical.provider_id,
            activated_by=canonical.activated_by,
            activated_at=canonical.activated_at,
            configuration_endpoint=canonical.configuration_version,
            activation_version=canonical.activation_version,
            rollback_by=canonical.rollback_by,
            rollback_at=canonical.rollback_at,
            rollback_reason=canonical.rollback_reason,
        )

    def provider(
        self,
        *,
        configuration: DaDataConfiguration | None = None,
    ) -> GatedDaDataCounterpartyLookupProvider:
        canonical = self._activation_state_store.get(DADATA_PROVIDER_ID)
        if canonical is None or not canonical.enabled:
            raise DaDataActivationError(
                "DaData provider execution is not active"
            )
        provider = self._provider
        if (
            provider is not None
            and not provider.binding_matches(
                activation_version=str(canonical.activation_version),
                activated_at=canonical.activated_at,
            )
        ):
            provider = None
            self._provider = None
        if provider is None:
            if configuration is None:
                raise DaDataActivationError(
                    "DaData provider composition is stale on this replica; "
                    "explicit configuration is required to rebind"
                )
            provider = self._provider_factory(configuration)
            self._provider = GatedDaDataCounterpartyLookupProvider(
                provider,
                gate=self,
                activation_version=str(canonical.activation_version),
                activated_at=canonical.activated_at,
            )
        return self._provider

    def allows_request(
        self,
        *,
        activation_version: str,
        activated_at: datetime | None,
    ) -> bool:
        state = self._activation_state_store.get(DADATA_PROVIDER_ID)
        return bool(
            state
            and state.enabled
            and state.activation_version == activation_version
            and state.activated_at == activated_at
        )

    def activate(
        self,
        configuration: DaDataConfiguration,
        *,
        readiness: DaDataActivationReadiness,
        activated_by: str,
        activation_version: str,
        correlation_id: str,
    ) -> GatedDaDataCounterpartyLookupProvider:
        canonical = self._activation_state_store.get(DADATA_PROVIDER_ID)
        if (canonical is not None and canonical.enabled) or self.state.enabled:
            raise DaDataActivationError("DaData activation is already active")
        if not activated_by.strip():
            raise DaDataActivationError("DaData activation requires an explicit operator")
        if not activation_version.strip():
            raise DaDataActivationError("DaData activation requires activation_version")
        if not correlation_id.strip():
            raise DaDataActivationError("DaData activation requires correlation_id")

        readiness.require_ready()
        if not configuration.enabled:
            raise DaDataActivationError(
                "DaData provider execution remains disabled by configuration"
            )

        provider = self._provider_factory(configuration)
        activation_time = self._now()
        self._activation_state_store.activate(
            ProviderActivationState(
                provider_id=DADATA_PROVIDER_ID,
                enabled=True,
                configuration_version=configuration.endpoint,
                activation_version=activation_version.strip(),
                activated_by=activated_by.strip(),
                activated_at=activation_time,
            )
        )
        self._state = DaDataActivationState(
            enabled=True,
            activated_by=activated_by.strip(),
            activated_at=activation_time,
            configuration_endpoint=configuration.endpoint,
            activation_version=activation_version.strip(),
        )
        self._provider = GatedDaDataCounterpartyLookupProvider(
            provider,
            gate=self,
            activation_version=activation_version.strip(),
            activated_at=activation_time,
        )
        self._emit(
            "intelligence.provider.activated",
            correlation_id=correlation_id,
            operator=activated_by,
            operation="activate",
        )
        return self._provider

    def rollback(
        self,
        *,
        rolled_back_by: str,
        reason: str,
        correlation_id: str,
    ) -> None:
        if not rolled_back_by.strip():
            raise DaDataActivationError("DaData rollback requires an explicit operator")
        if not reason.strip():
            raise DaDataActivationError("DaData rollback requires a reason")
        if not correlation_id.strip():
            raise DaDataActivationError("DaData rollback requires correlation_id")
        canonical = self._activation_state_store.get(DADATA_PROVIDER_ID)
        if canonical is None or not canonical.enabled:
            return

        activation_version = self._state.activation_version
        activation_endpoint = self._state.configuration_endpoint
        rollback_time = self._now()
        self._activation_state_store.rollback(
            provider_id=DADATA_PROVIDER_ID,
            rolled_back_by=rolled_back_by.strip(),
            rolled_back_at=rollback_time,
            reason=reason,
            expected_activation_version=str(canonical.activation_version),
            expected_activated_at=canonical.activated_at,
        )
        self._state = DaDataActivationState(
            enabled=False,
            configuration_endpoint=activation_endpoint,
            activation_version=activation_version,
            rollback_by=rolled_back_by.strip(),
            rollback_at=rollback_time,
            rollback_reason=reason.strip()[:256],
        )
        self._provider = None
        self._emit(
            "intelligence.provider.rolled_back",
            correlation_id=correlation_id,
            operator=rolled_back_by,
            operation="rollback",
        )

    def _emit(
        self,
        name: str,
        *,
        correlation_id: str,
        operator: str,
        operation: str,
    ) -> None:
        try:
            self._telemetry.emit(
                build_event(
                    name=name,
                    correlation_id=correlation_id,
                    attributes={
                        "component": "intelligence.provider",
                        "operation": operation,
                        "provider": DADATA_PROVIDER_ID,
                        "operator": operator,
                    },
                )
            )
        except Exception:
            return
