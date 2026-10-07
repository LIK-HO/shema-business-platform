from __future__ import annotations

import os
from collections.abc import Callable

from shema_platform.adapters.ai.composition import (
    AIProviderCompositionError,
    execute_scoped_ai,
)
from shema_platform.adapters.ai.contracts import (
    AIProviderFailure,
    AIProviderFailureCode,
)
from shema_platform.adapters.ai.production_activation import (
    AIProductionActivationError,
    YandexGPTProductionGate,
)
from shema_platform.adapters.ai.yandexgpt import (
    YandexGPTConfiguration,
    YandexGPTProvider,
)
from shema_platform.application.ai import AIProvider
from shema_platform.application.ai_runtime import (
    AIExecutionService,
    AIExecutionTrustResolver,
    IdempotentAIExecutionService,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.provider_activation import ProviderActivationStateStore
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
        activation_state_store: ProviderActivationStateStore | None = None,
    ) -> None:
        self._snapshot = snapshot
        self._telemetry = telemetry
        self._unit_of_work_factory = unit_of_work_factory
        self._trust_resolver = trust_resolver
        self._prompt_renderer = prompt_renderer
        self._cost_estimator = cost_estimator
        self._policy = policy or PolicyEngine()
        if activation_state_store is None:
            raise ValueError("YandexGPT requires a shared provider activation state store")
        self._activation_state_store = activation_state_store
        self._gate = YandexGPTProductionGate(
            telemetry=telemetry,
            provider_factory=self._build_provider,
            activation_state_store=activation_state_store,
            configuration_version=str(
                snapshot.values["ai.yandexgpt.configuration_version"]
            ),
        )
        self._provider: AIProvider | None = None

    def _build_provider(
        self,
        api_key: str | None = None,
        *,
        prompt_renderer=None,
        cost_estimator=None,
        requester=None,
        token_requester=None,
    ) -> AIProvider:
        secret = (api_key or os.getenv("YANDEXGPT_API_KEY", "")).strip()
        if not secret:
            raise ValueError("YANDEXGPT_API_KEY is required")
        values = self._snapshot.values
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
        return YandexGPTProvider(
            configuration,
            prompt_renderer=prompt_renderer or self._prompt_renderer,
            cost_estimator=cost_estimator or self._cost_estimator,
            requester=requester,
        )

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
        try:
            return self._gate.provider()
        except AIProductionActivationError as exc:
            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.NOT_READY,
                    message=str(exc),
                )
            ) from exc

    def service(self) -> IdempotentAIExecutionService:
        return IdempotentAIExecutionService(
            service=AIExecutionService(
                provider_factory=self.provider,
                unit_of_work_factory=self._unit_of_work_factory,
                trust_resolver=self._trust_resolver,
                configuration_version_provider=self.configuration_version,
                policy=self._policy,
                scoped_executor=execute_scoped_ai,
            ),
            unit_of_work_factory=self._unit_of_work_factory,
        )
