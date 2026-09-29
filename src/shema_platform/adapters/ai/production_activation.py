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
from shema_platform.adapters.ai.yandexgpt import (
    YandexGPTConfiguration,
    YandexGPTProvider,
)
from shema_platform.application.ai import AIRun, AITask
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.provider_activation import (
    ProviderActivationState,
    ProviderActivationStateStore,
)
from shema_platform.foundation.telemetry import (
    TelemetrySink,
    build_event,
)

PRODUCTION_FEATURE_FLAG = "ai.yandexgpt.production.enabled"
API_KEY_ENV = "YANDEXGPT_API_KEY"

_REQUIRED_CONFIG_KEYS = (
    "ai.yandexgpt.model_uri",
    "ai.yandexgpt.base_url",
    "ai.yandexgpt.timeout_seconds",
    "ai.yandexgpt.max_response_bytes",
    "ai.yandexgpt.max_input_chars",
    "ai.yandexgpt.max_output_tokens",
    "ai.yandexgpt.max_cost",
    "ai.yandexgpt.configuration_version",
    "ai.yandexgpt.activation_version",
)


class AIProductionActivationError(RuntimeError):
    """Fail-closed production activation or runtime-gate error."""


@dataclass(frozen=True, slots=True)
class AIProductionActivationState:
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
                raise ValueError("enabled production state requires configuration versions")
            if not self.activated_by or not self.activated_by.strip():
                raise ValueError("enabled production state requires activated_by")
            if self.activated_at is None or self.activated_at.tzinfo is None:
                raise ValueError("enabled production state requires activated_at")
            if self.max_cost is None or self.max_cost <= 0:
                raise ValueError("enabled production state requires max_cost")
            if (
                self.max_duration_seconds is None
                or self.max_duration_seconds <= 0
            ):
                raise ValueError(
                    "enabled production state requires max_duration_seconds"
                )


class YandexGPTProductionGate:
    """Explicit production gate backed by canonical shared activation state."""

    def __init__(
        self,
        *,
        telemetry: TelemetrySink,
        provider_factory=None,
        activation_state_store: ProviderActivationStateStore,
        configuration_version: str,
        provider_id: str = "yandexgpt",
    ) -> None:
        self._telemetry = telemetry
        self._provider_factory = provider_factory
        self._activation_state_store = activation_state_store
        self._configuration_version = configuration_version
        self._provider_id = provider_id
        self._state = AIProductionActivationState(
            enabled=False,
            provider_id=provider_id,
        )
        self._provider: GatedYandexGPTProvider | None = None

    @property
    def state(self) -> AIProductionActivationState:
        canonical = self._activation_state_store.get(self._provider_id)
        if canonical is None:
            return self._state
        return AIProductionActivationState(
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
        api_key: str | None = None,
    ) -> GatedYandexGPTProvider:
        canonical = self._activation_state_store.get(self._provider_id)
        if (canonical is not None and canonical.enabled) or self._state.enabled:
            raise AIProductionActivationError(
                "YandexGPT production activation is already active"
            )
        if snapshot.environment.strip().lower() != "production":
            raise AIProductionActivationError(
                "YandexGPT production activation requires production environment"
            )
        if not snapshot.feature_flags.get(PRODUCTION_FEATURE_FLAG, False):
            raise AIProductionActivationError(
                "YandexGPT production activation is disabled by configuration"
            )
        if not activated_by.strip():
            raise AIProductionActivationError(
                "YandexGPT production activation requires an explicit operator"
            )
        if self._telemetry is None:
            raise AIProductionActivationError(
                "YandexGPT production activation requires telemetry"
            )

        values = self._required_values(snapshot)
        secret = (api_key or os.getenv(API_KEY_ENV, "")).strip()
        if not secret:
            raise AIProductionActivationError(
                f"YandexGPT production activation requires {API_KEY_ENV}"
            )

        configuration = YandexGPTConfiguration(
            api_key=secret,
            model_uri=str(values["ai.yandexgpt.model_uri"]),
            base_url=str(values["ai.yandexgpt.base_url"]).rstrip("/"),
            timeout_seconds=float(values["ai.yandexgpt.timeout_seconds"]),
            max_response_bytes=int(values["ai.yandexgpt.max_response_bytes"]),
            max_input_chars=int(values["ai.yandexgpt.max_input_chars"]),
            max_output_tokens=int(values["ai.yandexgpt.max_output_tokens"]),
            max_cost=float(values["ai.yandexgpt.max_cost"]),
            configuration_version=str(values["ai.yandexgpt.configuration_version"]),
            activation_version=str(values["ai.yandexgpt.activation_version"]),
        )

        if self._provider_factory is None:
            provider = YandexGPTProvider(
                configuration,
                prompt_renderer=prompt_renderer,
                cost_estimator=cost_estimator,
            )
        else:
            provider = self._provider_factory(
                secret,
                prompt_renderer=prompt_renderer,
                cost_estimator=cost_estimator,
            )
        readiness = provider.readiness()
        if readiness.state is not AIProviderReadinessState.READY:
            raise AIProductionActivationError(
                "YandexGPT production activation failed readiness"
            )

        activation_time = datetime.now(UTC)
        previous_config = self._state.configuration_version
        new_state = AIProductionActivationState(
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
        self._provider = GatedYandexGPTProvider(
            ScopedAIProvider(provider, telemetry=self._telemetry),
            gate=self,
            activation_version=new_state.activation_version,
            activated_at=new_state.activated_at,
        )
        self._emit(
            name="ai.production.activated",
            operation="activate",
            provider="yandexgpt",
            operator=activated_by,
            configuration_version=configuration.configuration_version,
        )
        return self._provider

    def rollback(self, *, rolled_back_by: str, reason: str) -> None:
        if not rolled_back_by.strip():
            raise AIProductionActivationError(
                "YandexGPT rollback requires an explicit operator"
            )
        if not reason.strip():
            raise AIProductionActivationError(
                "YandexGPT rollback requires a reason"
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
        self._state = AIProductionActivationState(
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
            provider="yandexgpt",
            operator=rolled_back_by,
            configuration_version=previous.configuration_version,
            error_code="production_activation_rolled_back",
        )

    def _required_values(
        self,
        snapshot: ConfigurationSnapshot,
    ) -> dict[str, object]:
        missing = [
            key for key in _REQUIRED_CONFIG_KEYS if key not in snapshot.values
        ]
        if missing:
            raise AIProductionActivationError(
                "YandexGPT production snapshot is missing required values: "
                + ", ".join(missing)
            )
        return {key: snapshot.values[key] for key in _REQUIRED_CONFIG_KEYS}

    def provider(self) -> GatedYandexGPTProvider:
        canonical = self._activation_state_store.get(self._provider_id)
        if canonical is None or not canonical.enabled:
            raise AIProductionActivationError(
                "YandexGPT production activation is not enabled in canonical state"
            )
        if canonical.configuration_version != self._configuration_version:
            raise AIProductionActivationError(
                "YandexGPT canonical activation configuration does not match runtime"
            )
        if (
            self._provider is not None
            and not self._provider.binding_matches(
                activation_version=str(canonical.activation_version),
                activated_at=canonical.activated_at,
            )
        ):
            self._provider = None
        if self._provider is None:
            if self._provider_factory is None:
                raise AIProductionActivationError(
                    "YandexGPT provider composition is unavailable on this replica"
                )
            provider = self._provider_factory(None)
            readiness = provider.readiness()
            if readiness.state is not AIProviderReadinessState.READY:
                raise AIProductionActivationError(
                    "YandexGPT provider is not ready for canonical activation"
                )
            self._provider = GatedYandexGPTProvider(
                ScopedAIProvider(provider, telemetry=self._telemetry),
                gate=self,
                activation_version=str(canonical.activation_version),
                activated_at=canonical.activated_at,
            )
        self._state = AIProductionActivationState(
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

    def allows_request(
        self,
        *,
        configuration_version: str,
        activation_version: str,
        activated_at: datetime | None,
    ) -> bool:
        state = self._activation_state_store.get(self._provider_id)
        return bool(
            state
            and state.enabled
            and state.configuration_version == configuration_version
            and state.activation_version == activation_version
            and state.activated_at == activated_at
        )

    def budget_allows(
        self,
        *,
        max_cost: float,
        max_duration_seconds: float,
    ) -> bool:
        state = self._activation_state_store.get(self._provider_id)
        return bool(
            state
            and state.enabled
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


class GatedYandexGPTProvider:
    """Frozen-gateway-compatible provider whose traffic is controlled by the gate."""

    provider_id = "yandexgpt"

    def __init__(
        self,
        provider: ScopedAIProvider,
        *,
        gate: YandexGPTProductionGate,
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
            failure = AIProviderFailure(
                code=AIProviderFailureCode.NOT_READY,
                message="YandexGPT production activation is not active for this configuration",
            )
            raise AIProviderCompositionError(failure)

        if not self._gate.budget_allows(
            max_cost=scope.budget.max_cost,
            max_duration_seconds=scope.deadline_seconds,
        ):
            failure = AIProviderFailure(
                code=AIProviderFailureCode.RESOURCE_EXHAUSTED,
                message="AI request exceeds production activation ceilings",
            )
            raise AIProviderCompositionError(failure)

        return self._provider.run(
            task,
            input_refs=input_refs,
        )
