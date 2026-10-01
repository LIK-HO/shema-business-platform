from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from shema_platform.adapters.ai.application_composition import (
    YandexGPTApplicationComposition,
)
from shema_platform.application.ai_runtime import AIExecutionTrustResolver
from shema_platform.application.ports import UnitOfWork
from shema_platform.experience.ai_application import AIOnlyAPIApplication
from shema_platform.experience.api import APIApplication, create_app
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.telemetry import TelemetrySink


@dataclass(frozen=True, slots=True)
class YandexGPTRuntimeAssembly:
    """Explicit composition root; construction never activates provider traffic."""

    ai: YandexGPTApplicationComposition

    def api_application(self) -> APIApplication:
        return AIOnlyAPIApplication(self.ai.service())

    def create_http_app(
        self,
        *,
        authenticator=None,
        enable_docs: bool = True,
        telemetry: TelemetrySink | None = None,
    ):
        return create_app(
            application=self.api_application(),
            authenticator=authenticator,
            enable_docs=enable_docs,
            telemetry=telemetry,
        )

    def activate_yandexgpt(
        self,
        *,
        activated_by: str,
        api_key: str | None = None,
    ) -> None:
        self.ai.activate(
            activated_by=activated_by,
            api_key=api_key,
        )

    def rollback_yandexgpt(
        self,
        *,
        rolled_back_by: str,
        reason: str,
    ) -> None:
        self.ai.rollback(
            rolled_back_by=rolled_back_by,
            reason=reason,
        )


def compose_yandexgpt_runtime(
    *,
    snapshot: ConfigurationSnapshot,
    telemetry: TelemetrySink,
    unit_of_work_factory: Callable[[], UnitOfWork],
    trust_resolver: AIExecutionTrustResolver,
    prompt_renderer: Callable,
    cost_estimator: Callable[[int, int], float],
    policy: PolicyEngine | None = None,
) -> YandexGPTRuntimeAssembly:
    """Build the explicit runtime assembly without activating YandexGPT."""
    return YandexGPTRuntimeAssembly(
        ai=YandexGPTApplicationComposition(
            snapshot=snapshot,
            telemetry=telemetry,
            unit_of_work_factory=unit_of_work_factory,
            trust_resolver=trust_resolver,
            prompt_renderer=prompt_renderer,
            cost_estimator=cost_estimator,
            policy=policy,
        )
    )
