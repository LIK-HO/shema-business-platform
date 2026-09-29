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
from shema_platform.adapters.ai.gigachat import (
    GigaChatConfiguration,
    GigaChatProvider,
)
from shema_platform.adapters.ai.gigachat_activation import (
    GigaChatProductionActivationError,
    GigaChatProductionGate,
)
from shema_platform.application.ai import AIProvider
from shema_platform.application.ai_runtime import (
    AIExecutionService,
    AIExecutionTrustResolver,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.provider_activation import ProviderActivationStateStore
from shema_platform.foundation.telemetry import TelemetrySink


class GigaChatApplicationComposition:
    """Explicit composition bridge for GigaChat over the frozen AI Gateway."""

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
            raise ValueError("GigaChat requires a shared provider activation state store")
        self._activation_state_store = activation_state_store
        self._gate = GigaChatProductionGate(
            telemetry=telemetry,
            provider_factory=self._build_provider,
            activation_state_store=activation_state_store,
            configuration_version=str(
                snapshot.values["ai.gigachat.configuration_version"]
            ),
        )
        self._provider: AIProvider | None = None

    def _build_provider(
        self,
        authorization_key: str | None = None,
        *,
        requester=None,
        token_requester=None,
        prompt_renderer=None,
        cost_estimator=None,
    ) -> AIProvider:
        secret = (
            authorization_key
            or os.getenv("GIGACHAT_AUTHORIZATION_KEY", "")
        ).strip()
        if not secret:
            raise ValueError("GIGACHAT_AUTHORIZATION_KEY is required")
        values = self._snapshot.values
        configuration = GigaChatConfiguration(
            authorization_key=secret,
            model=str(values["ai.gigachat.model"]),
            scope=str(values["ai.gigachat.scope"]),
            base_url=str(values["ai.gigachat.base_url"]).rstrip("/"),
            token_url=str(values["ai.gigachat.token_url"]).rstrip("/"),
            timeout_seconds=float(values["ai.gigachat.timeout_seconds"]),
            max_response_bytes=int(values["ai.gigachat.max_response_bytes"]),
            max_input_chars=int(values["ai.gigachat.max_input_chars"]),
            max_output_tokens=int(values["ai.gigachat.max_output_tokens"]),
            max_cost=float(values["ai.gigachat.max_cost"]),
            configuration_version=str(values["ai.gigachat.configuration_version"]),
            activation_version=str(values["ai.gigachat.activation_version"]),
        )
        return GigaChatProvider(
            configuration,
            prompt_renderer=prompt_renderer or self._prompt_renderer,
            cost_estimator=cost_estimator or self._cost_estimator,
            requester=requester,
            token_requester=token_requester,
        )

    @property
    def gate(self) -> GigaChatProductionGate:
        return self._gate

    def activate(
        self,
        *,
        activated_by: str,
        authorization_key: str | None = None,
        requester=None,
        token_requester=None,
    ) -> None:
        self._provider = self._gate.activate(
            self._snapshot,
            activated_by=activated_by,
            prompt_renderer=self._prompt_renderer,
            cost_estimator=self._cost_estimator,
            authorization_key=authorization_key,
            requester=requester,
            token_requester=token_requester,
        )

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
                    message=(
                        "GigaChat production application is not activated"
                    ),
                )
            )
        return version

    def provider(self) -> AIProvider:
        try:
            return self._gate.provider()
        except GigaChatProductionActivationError as exc:
            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.NOT_READY,
                    message=f"GigaChat production provider is not activated: {exc}",
                )
            ) from exc

    def service(self) -> AIExecutionService:
        return AIExecutionService(
            provider_factory=self.provider,
            unit_of_work_factory=self._unit_of_work_factory,
            trust_resolver=self._trust_resolver,
            configuration_version_provider=self.configuration_version,
            policy=self._policy,
            scoped_executor=execute_scoped_ai,
        )
