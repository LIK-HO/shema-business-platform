from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import UTC, datetime

from shema_platform.adapters.ai.composition import (
    AIProviderCompositionError,
    ScopedAIProvider,
    current_ai_execution_scope,
)
from shema_platform.adapters.ai.contracts import (
    AIProviderFailure,
    AIProviderFailureCode,
    AIProviderReadinessState,
)
from shema_platform.adapters.ai.gigachat import (
    PRODUCTION_SCOPES,
    GigaChatConfiguration,
    GigaChatProvider,
)
from shema_platform.application.ai import AIRun, AITask
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.provider_activation import (
    ProviderActivationState,
    ProviderActivationStateStore,
)
from shema_platform.foundation.telemetry import TelemetrySink, build_event

PRODUCTION_FEATURE_FLAG = "ai.gigachat.production.enabled"
AUTHORIZATION_KEY_ENV = "GIGACHAT_AUTHORIZATION_KEY"

_REQUIRED_CONFIG_KEYS = (
    "ai.gigachat.model",
    "ai.gigachat.scope",
    "ai.gigachat.base_url",
    "ai.gigachat.token_url",
    "ai.gigachat.timeout_seconds",
    "ai.gigachat.max_response_bytes",
    "ai.gigachat.max_input_chars",
    "ai.gigachat.max_output_tokens",
    "ai.gigachat.max_cost",
    "ai.gigachat.configuration_version",
    "ai.gigachat.activation_version",
)


class GigaChatProductionActivationError(RuntimeError):
    """Fail-closed GigaChat activation or runtime-gate error."""


@dataclass(frozen=True, slots=True)
class GigaChatProductionActivationState:
    enabled: bool
    provider_id: str
    configuration_version: str | None = None
    activation_version: str | None = None
    activated_by: str | None = None
    activated_at: datetime | None = None
    max_cost: float | None = None
    max_duration_seconds: float | None = None
    rollback_from_configuration_version: str | None = None
    rollback_by: str | None = None
    rollback_at: datetime | None = None
    rollback_reason: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if self.enabled:
            if not self.configuration_version or not self.activation_version:
                raise ValueError(
                    "enabled production state requires configuration versions"
                )
            if not self.activated_by or not self.activated_by.strip():
                raise ValueError(
                    "enabled production state requires activated_by"
                )
            if self.activated_at is None or self.activated_at.tzinfo is None:
                raise ValueError(
                    "enabled production state requires activated_at"
                )
            if self.max_cost is None or self.max_cost <= 0:
                raise ValueError("enabled production state requires max_cost")
            if (
                self.max_duration_seconds is None
                or self.max_duration_seconds <= 0
            ):
                raise ValueError(
                    "enabled production state requires max_duration_seconds"
                )


class GigaChatProductionGate:
    """Explicit production gate backed by canonical shared activation state."""

    def __init__(
        self,
        *,
        telemetry: TelemetrySink,
        provider_factory=None,
        activation_state_store: ProviderActivationStateStore,
        configuration_version: str = "gigachat-config:v1",
        provider_id: str = "gigachat",
    ) -> None:
        self._telemetry = telemetry
        self._provider_factory = provider_factory
        self._activation_state_store = activation_state_store
        self._configuration_version = configuration_version
        self._provider_id = provider_id
        self._state = GigaChatProductionActivationState(
            enabled=False,
            provider_id=provider_id,        )
        self._provider: GatedGigaChatProvider | None = None

    @property
    def state(self) -> GigaChatProductionActivationState:
        canonical = self._activation_state_store.get(self._provider_id)
        if canonical is None:
            return self._state
        return GigaChatProductionActivationState(
            enabled=canonical.enabled,
            provider_id=canonical.provider_id,
            configuration_version=canonical.configuration_version,
            activation_version=canonical.activation_version,
            activated_by=canonical.activated_by,
            activated_at=canonical.activated_at,
            max_cost=canonical.max_cost,
            max_duration_seconds=canonical.max_duration_seconds,
            rollback_from_configuration_version=(
                canonical.rollback_from_configuration_version
            ),
            rollback_by=canonical.rollback_by,
            rollback_at=canonical.rollback_at,
            rollback_reason=canonical.rollback_reason,
        )

    def activate(
        self,
        snapshot: ConfigurationSnapshot,
        *,
        activated_by: str,
        prompt_renderer,
        cost_estimator,
        authorization_key: str | None = None,
        requester=None,
        token_requester=None,
    ) -> GatedGigaChatProvider:
        canonical = self._activation_state_store.get(self._provider_id)
        if (canonical is not None and canonical.enabled) or self._state.enabled:
            raise GigaChatProductionActivationError(
                "GigaChat production activation is already active"
            )
        if snapshot.environment.strip().lower() != "production":
            raise GigaChatProductionActivationError(
                "GigaChat production activation requires production environment"
            )
        if not snapshot.feature_flags.get(PRODUCTION_FEATURE_FLAG, False):
            raise GigaChatProductionActivationError(
                "GigaChat production activation is disabled by configuration"
            )
        if not activated_by.strip():
            raise GigaChatProductionActivationError(
                "GigaChat production activation requires an explicit operator"
            )
        if self._telemetry is None:
            raise GigaChatProductionActivationError(
                "GigaChat production activation requires telemetry"
            )

        values = self._required_values(snapshot)
        scope = str(values["ai.gigachat.scope"])
        if scope not in PRODUCTION_SCOPES:
            raise GigaChatProductionActivationError(
                "GigaChat production activation requires a B2B or CORP scope"
            )

        secret = (
            authorization_key
            or os.getenv(AUTHORIZATION_KEY_ENV, "")
        ).strip()
        if not secret:
            raise GigaChatProductionActivationError(
                f"GigaChat production activation requires {AUTHORIZATION_KEY_ENV}"
            )

        configuration = GigaChatConfiguration(
            authorization_key=secret,
            model=str(values["ai.gigachat.model"]),
            scope=scope,
            base_url=str(values["ai.gigachat.base_url"]).rstrip("/"),
            token_url=str(values["ai.gigachat.token_url"]).rstrip("/"),
            timeout_seconds=float(values["ai.gigachat.timeout_seconds"]),
            max_response_bytes=int(
                values["ai.gigachat.max_response_bytes"]
            ),
            max_input_chars=int(values["ai.gigachat.max_input_chars"]),
            max_output_tokens=int(values["ai.gigachat.max_output_tokens"]),
            max_cost=float(values["ai.gigachat.max_cost"]),
            configuration_version=str(
                values["ai.gigachat.configuration_version"]
            ),
            activation_version=str(
                values["ai.gigachat.activation_version"]
            ),
        )

        if self._provider_factory is None:
            provider = GigaChatProvider(
                configuration,
                prompt_renderer=prompt_renderer,
                cost_estimator=cost_estimator,
                requester=requester,
                token_requester=token_requester,
            )
        else:
            provider = self._provider_factory(
                secret,
                requester=requester,
                token_requester=token_requester,
                prompt_renderer=prompt_renderer,
                cost_estimator=cost_estimator,
            )
        readiness = provider.readiness()
        if readiness.state is not AIProviderReadinessState.READY:
            raise GigaChatProductionActivationError(
                "GigaChat production activation failed readiness"
            )

        activation_time = datetime.now(UTC)
        previous_config = self._state.configuration_version
        new_state = GigaChatProductionActivationState(
            enabled=True,
            provider_id=self._provider_id,
            configuration_version=configuration.configuration_version,
            activation_version=configuration.activation_version,
            activated_by=activated_by,
            activated_at=activation_time,
            max_cost=configuration.max_cost,
            max_duration_seconds=configuration.timeout_seconds,
            rollback_from_configuration_version=previous_config,
        )
        self._activation_state_store.activate(
            ProviderActivationState(
                provider_id=new_state.provider_id,
                enabled=True,
                configuration_version=new_state.configuration_version,
                activation_version=new_state.activation_version,
                activated_by=new_state.activated_by,
                activated_at=new_state.activated_at,
                max_cost=new_state.max_cost,
                max_duration_seconds=new_state.max_duration_seconds,
            )
        )
        self._state = new_state
        self._provider = GatedGigaChatProvider(
            ScopedAIProvider(provider, telemetry=self._telemetry),
            gate=self,
            activation_version=new_state.activation_version,
            activated_at=new_state.activated_at,
        )
        self._emit(
            name="ai.production.activated",
            operation="activate",
            provider="gigachat",
            operator=activated_by,
            configuration_version=configuration.configuration_version,
        )
        return self._provider

    def rollback(self, *, rolled_back_by: str, reason: str) -> None:
        if not rolled_back_by.strip():
            raise GigaChatProductionActivationError(
                "GigaChat rollback requires an explicit operator"
            )
        if not reason.strip():
            raise GigaChatProductionActivationError(
                "GigaChat rollback requires a reason"
            )
        canonical = self._activation_state_store.get(self._provider_id)
        previous = self.state
        if canonical is None or not canonical.enabled:
            return

        rollback_time = datetime.now(UTC)
        self._activation_state_store.rollback(
            provider_id=self._provider_id,
            rolled_back_by=rolled_back_by,
            rolled_back_at=rollback_time,
            reason=reason,
            expected_activation_version=str(canonical.activation_version),
            expected_activated_at=canonical.activated_at,
        )
        self._state = GigaChatProductionActivationState(
            enabled=False,
            provider_id=self._provider_id,
            rollback_from_configuration_version=previous.configuration_version,
            rollback_by=rolled_back_by,
            rollback_at=rollback_time,
            rollback_reason=reason[:256],
        )
        self._provider = None
        self._emit(
            name="ai.production.rolled_back",
            operation="rollback",
            provider="gigachat",
            operator=rolled_back_by,
            configuration_version=previous.configuration_version,
            error_code="production_activation_rolled_back",
        )

    def _required_values(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> dict[str, object]:
        missing = [
            key
            for key in _REQUIRED_CONFIG_KEYS
            if key not in snapshot.values
        ]
        if missing:
            raise GigaChatProductionActivationError(
                "GigaChat production snapshot is missing required values: "
                + ", ".join(missing)
            )
        return {key: snapshot.values[key] for key in _REQUIRED_CONFIG_KEYS}

    def provider(self) -> GatedGigaChatProvider:
        canonical = self._activation_state_store.get(self._provider_id)
        if canonical is None or not canonical.enabled:
            raise GigaChatProductionActivationError(
                "GigaChat production activation is not enabled in canonical state"
            )
        if canonical.configuration_version != self._configuration_version:
            raise GigaChatProductionActivationError(
                "GigaChat canonical activation configuration does not match runtime"
            )
        if self._provider is None:
            if self._provider_factory is None:
                raise GigaChatProductionActivationError(
                    "GigaChat provider composition is unavailable on this replica"
                )
            provider = self._provider_factory(None)
            readiness = provider.readiness()
            if readiness.state is not AIProviderReadinessState.READY:
                raise GigaChatProductionActivationError(
                    "GigaChat provider is not ready for canonical activation"
                )
            self._provider = GatedGigaChatProvider(
                ScopedAIProvider(provider, telemetry=self._telemetry),
                gate=self,
            )
        self._state = GigaChatProductionActivationState(
            enabled=True,
            provider_id=self._provider_id,
            configuration_version=canonical.configuration_version,
            activation_version=canonical.activation_version,
            activated_by=canonical.activated_by,
            activated_at=canonical.activated_at,
            max_cost=canonical.max_cost,
            max_duration_seconds=canonical.max_duration_seconds,
            rollback_by=canonical.rollback_by,
            rollback_at=canonical.rollback_at,
            rollback_reason=canonical.rollback_reason,
        )
        return self._provider

    def allows_request(self, *, configuration_version: str) -> bool:
        state = self._state
        return bool(
            state.enabled
            and state.configuration_version == configuration_version
        )

    def budget_allows(
        self,
        *,
        max_cost: float,
        max_duration_seconds: float,
    ) -> bool:
        state = self._state
        return bool(
            state.enabled
            and state.max_cost is not None
            and state.max_duration_seconds is not None
            and max_cost <= state.max_cost
            and max_duration_seconds <= state.max_duration_seconds
        )

    def _emit(
        self,
        *,
        name: str,
        operation: str,
        provider: str,
        operator: str | None = None,
        configuration_version: str | None = None,
        error_code: str | None = None,
    ) -> None:
        try:
            correlation_id = (
                self._state.activation_version
                or "ai-production-activation"
            )
            self._telemetry.emit(
                build_event(
                    name=name,
                    correlation_id=correlation_id,
                    attributes={
                        "component": "ai.production",
                        "operation": operation,
                        "provider": provider,
                        "operator": operator,
                        "configuration_version": configuration_version,
                        "error_code": error_code,
                    },
                )
            )
        except Exception:
            return


class GatedGigaChatProvider:
    """Frozen-gateway-compatible provider controlled by the GigaChat gate."""

    provider_id = "gigachat"

    def __init__(
        self,
        provider: ScopedAIProvider,
        *,
        gate: GigaChatProductionGate,
    ) -> None:
        self._provider = provider
        self._gate = gate

    def run(
        self,
        task: AITask,
        *,
        input_refs: tuple[str, ...],
    ) -> AIRun:
        scope = current_ai_execution_scope()
        configuration_version = scope.context.configuration_version
        if not configuration_version or not self._gate.allows_request(
            configuration_version=configuration_version,
        ):
            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.NOT_READY,
                    message=(
                        "GigaChat production activation is not active "
                        "for this configuration"
                    ),
                )
            )

        if not self._gate.budget_allows(
            max_cost=scope.budget.max_cost,
            max_duration_seconds=scope.deadline_seconds,
        ):
            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.RESOURCE_EXHAUSTED,
                    message="AI request exceeds production activation ceilings",
                )
            )

        return self._provider.run(
            task,
            input_refs=input_refs,
        )
