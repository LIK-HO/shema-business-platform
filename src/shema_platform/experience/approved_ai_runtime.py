from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from shema_platform.experience.api import APIApplication
from shema_platform.experience.gigachat_runtime_composition import (
    GigaChatRuntimeAssembly,
)
from shema_platform.experience.runtime_composition import (
    YandexGPTRuntimeAssembly,
)

ApprovedAIProvider = Literal["yandexgpt", "gigachat"]


class AIProviderSelectionError(ValueError):
    """Raised when an approved provider cannot be selected safely."""


@dataclass(frozen=True, slots=True)
class ApprovedAIRuntimeAssembly:
    """Immutable operator-selected composition of one approved AI provider."""

    provider_id: ApprovedAIProvider
    _runtime: YandexGPTRuntimeAssembly | GigaChatRuntimeAssembly

    def api_application(self) -> APIApplication:
        return self._runtime.api_application()

    def create_http_app(
        self,
        *,
        authenticator=None,
        enable_docs: bool = True,
        telemetry=None,
    ):
        return self._runtime.create_http_app(
            authenticator=authenticator,
            enable_docs=enable_docs,
            telemetry=telemetry,
        )


def compose_approved_ai_runtime(
    *,
    provider_id: str,
    yandexgpt: YandexGPTRuntimeAssembly | None = None,
    gigachat: GigaChatRuntimeAssembly | None = None,
) -> ApprovedAIRuntimeAssembly:
    """Select exactly one pre-composed approved provider; never falls back."""
    normalized = provider_id.strip().lower()

    if normalized == "yandexgpt":
        if yandexgpt is None:
            raise AIProviderSelectionError(
                "selected AI provider 'yandexgpt' is not composed"
            )
        return ApprovedAIRuntimeAssembly(
            provider_id="yandexgpt",
            _runtime=yandexgpt,
        )

    if normalized == "gigachat":
        if gigachat is None:
            raise AIProviderSelectionError(
                "selected AI provider 'gigachat' is not composed"
            )
        return ApprovedAIRuntimeAssembly(
            provider_id="gigachat",
            _runtime=gigachat,
        )

    raise AIProviderSelectionError(
        "unsupported AI provider selection; allowed providers are "
        "'yandexgpt' and 'gigachat'"
    )
