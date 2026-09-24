"""Provider-neutral AI adapter contracts outside the frozen kernel."""

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
from shema_platform.adapters.ai.composition import (
    AIExecutionScope,
    AIProviderCompositionError,
    ScopedAIProvider,
    bind_ai_execution_scope,
    current_ai_execution_scope,
    execute_scoped_ai,
)
from shema_platform.adapters.ai.yandexgpt import (
    YandexGPTConfiguration,
    YandexGPTExecutionError,
    YandexGPTProvider,
)

__all__ = [
    "AIExecutionScope",
    "AIProviderCompositionError",
    "ScopedAIProvider",
    "bind_ai_execution_scope",
    "current_ai_execution_scope",
    "execute_scoped_ai",
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
