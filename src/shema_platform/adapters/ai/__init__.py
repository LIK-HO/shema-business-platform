"""Provider-neutral AI adapter contracts outside the frozen kernel."""

from shema_platform.adapters.ai.yandexgpt import (
    YandexGPTConfiguration,
    YandexGPTExecutionError,
    YandexGPTProvider,
)
from shema_platform.adapters.ai.contracts import (
    AIModelProvenance,
    AIProviderActivation,
    AIProviderAdapter,
    AIProviderDescriptor,
    AIProviderFailure,
    AIProviderFailureCode,
    AIProviderKind,
    AIProviderReadiness,
    AIProviderReadinessState,
    AIProviderRequest,
    AIProviderResourceLimits,
    AIProviderResponse,
    AIProviderRoutingPolicy,
    validate_provider_activation,
    validate_provider_response,
)

__all__ = [
    "YandexGPTConfiguration",
    "YandexGPTExecutionError",
    "YandexGPTProvider",
    "AIModelProvenance",
    "AIProviderActivation",
    "AIProviderAdapter",
    "AIProviderDescriptor",
    "AIProviderFailure",
    "AIProviderFailureCode",
    "AIProviderKind",
    "AIProviderReadiness",
    "AIProviderReadinessState",
    "AIProviderRequest",
    "AIProviderResourceLimits",
    "AIProviderResponse",
    "AIProviderRoutingPolicy",
    "validate_provider_activation",
    "validate_provider_response",
]
