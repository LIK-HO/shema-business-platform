from __future__ import annotations

from collections.abc import Callable

from shema_platform.adapters.ai.composition import (
    AIProviderCompositionError,
    ScopedAIProvider,
)
from shema_platform.adapters.ai.contracts import (
    AIProviderFailure,
    AIProviderFailureCode,
)
from shema_platform.adapters.ai.production_activation import (
    YandexGPTProductionGate,
)
from shema_platform.application.ai import AIProvider
from shema_platform.application.ai_runtime import (
    AIExecutionService,
    AIExecutionTrustResolver,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.telemetry import TelemetrySink


class YandexGPTApplicationComposition:
    """Explicit composition of YandexGPT over the frozen AI Gateway."""

    def __init__(
        self,
        *,
        snapshot: ConfigurationSnapshot,
        telemetry: TelemetrySink,
        unit_of_work_factory: Callable[[], UnitOfWork],
        trust_resolver: AIExecutionTrustResolver,
        prompt_renderer: Callable,
        cost_estimator: Callable[[int, int], float],
        policy: PolicyEngine | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._telemetry = telemetry
        self._unit_of_work_factory = unit_of_work_factory
        self._trust_resolver = trust_resolver
        self._prompt_renderer = prompt_renderer
        self._cost_estimator = cost_estimator
        self._policy = policy or PolicyEngine()
        self._gate = YandexGPTProductionGate(telemetry=telemetry)
        self._provider: AIProvider | None = None

    @property
    def gate(self) -> YandexGPTProductionGate:
        return self._gate

    def activate(
        self,
        *,
        activated_by: str,
        api_key: str | None = None,
    ) -> None:
        gated_provider = self._gate.activate(
            self._snapshot,
            activated_by=activated_by,
            prompt_renderer=self._prompt_renderer,
            cost_estimator=self._cost_estimator,
            api_key=api_key,
        )
        self._provider = gated_provider

    def rollback(self, *, rolled_back_by: str, reason: str) -> None:
        self._gate.rollback(
            rolled_back_by=rolled_back_by,
            reason=reason,
        )
        self._provider = None

    def configuration_version(self) -> str:
        version = self._gate.state.configuration_version
        if version is None:
            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.NOT_READY,
                    message="YandexGPT production application is not activated",
                )
            )
        return version

    def provider(self) -> AIProvider:
        provider = self._provider
        if provider is None:
            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.NOT_READY,
                    message="YandexGPT production application is not activated",
                )
            )
        return provider

    def service(self) -> AIExecutionService:
        return AIExecutionService(
            provider_factory=self.provider,
            unit_of_work_factory=self._unit_of_work_factory,
            trust_resolver=self._trust_resolver,
            configuration_version_provider=self.configuration_version,
            policy=self._policy,
        )
