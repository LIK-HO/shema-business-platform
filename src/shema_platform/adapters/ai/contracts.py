from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from math import isfinite
from typing import Protocol

from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIRun,
    AITask,
)


class AIProviderKind(str, Enum):
    CLOUD = "cloud"
    LOCAL_SELF_HOSTED = "local_self_hosted"


class AIProviderReadinessState(str, Enum):
    DISABLED = "disabled"
    READY = "ready"
    NOT_CONFIGURED = "not_configured"
    UNHEALTHY = "unhealthy"


class AIProviderFailureCode(str, Enum):
    CONFIGURATION = "configuration"
    NOT_READY = "not_ready"
    AUTHENTICATION = "authentication"
    AUTHORIZATION = "authorization"
    LICENSE_UNVERIFIED = "license_unverified"
    MODEL_UNAVAILABLE = "model_unavailable"
    RATE_LIMITED = "rate_limited"
    RESOURCE_EXHAUSTED = "resource_exhausted"
    DEADLINE_EXCEEDED = "deadline_exceeded"
    TRANSPORT = "transport"
    INVALID_RESPONSE = "invalid_response"
    POLICY_DENIED = "policy_denied"
    SECURITY_BLOCKED = "security_blocked"


APPROVED_CLOUD_PROVIDER_IDS = frozenset({"yandexgpt", "gigachat"})


@dataclass(frozen=True, slots=True)
class AIProviderResourceLimits:
    max_duration_seconds: float
    max_response_bytes: int
    max_input_chars: int
    max_output_tokens: int
    max_calls: int
    max_cost: float

    def __post_init__(self) -> None:
        if not isfinite(self.max_duration_seconds) or self.max_duration_seconds <= 0:
            raise ValueError("max_duration_seconds must be finite and positive")
        if self.max_response_bytes <= 0:
            raise ValueError("max_response_bytes must be positive")
        if self.max_input_chars <= 0:
            raise ValueError("max_input_chars must be positive")
        if self.max_output_tokens < 0:
            raise ValueError("max_output_tokens cannot be negative")
        if self.max_calls < 0:
            raise ValueError("max_calls cannot be negative")
        if not isfinite(self.max_cost) or self.max_cost < 0:
            raise ValueError("max_cost must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class AIModelProvenance:
    source_ref: str
    license_name: str
    license_url: str
    license_checked_at: datetime | None
    artifact_digest: str | None
    runtime: str
    security_status: str
    free_commercial_use_verified: bool

    def __post_init__(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        if not self.license_name.strip():
            raise ValueError("license_name is required")
        if not self.license_url.startswith(("https://", "http://")):
            raise ValueError("license_url must be an absolute URL")
        if not self.runtime.strip():
            raise ValueError("runtime is required")
        if not self.security_status.strip():
            raise ValueError("security_status is required")
        if self.free_commercial_use_verified and (
            self.license_checked_at is None
            or not self.artifact_digest
        ):
            raise ValueError(
                "free-commercial-use verification requires license_checked_at "
                "and artifact_digest"
            )


@dataclass(frozen=True, slots=True)
class AIProviderDescriptor:
    provider_id: str
    kind: AIProviderKind
    model_id: str
    model_version: str
    configuration_version: str
    capabilities: frozenset[str]
    resource_limits: AIProviderResourceLimits
    provenance: AIModelProvenance

    def __post_init__(self) -> None:
        for name, value in (
            ("provider_id", self.provider_id),
            ("model_id", self.model_id),
            ("model_version", self.model_version),
            ("configuration_version", self.configuration_version),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")
        if not self.capabilities:
            raise ValueError("capabilities cannot be empty")


@dataclass(frozen=True, slots=True)
class AIProviderActivation:
    enabled: bool
    activation_version: str
    explicit: bool
    reason: str

    def __post_init__(self) -> None:
        if not self.activation_version.strip():
            raise ValueError("activation_version is required")
        if not self.reason.strip():
            raise ValueError("reason is required")
        if self.enabled and not self.explicit:
            raise ValueError("provider activation must be explicit")


@dataclass(frozen=True, slots=True)
class AIProviderRoutingPolicy:
    implicit_cloud_to_local_fallback: bool = False
    implicit_local_to_cloud_fallback: bool = False

    def __post_init__(self) -> None:
        if self.implicit_cloud_to_local_fallback:
            raise ValueError("cloud-to-local implicit fallback is forbidden")
        if self.implicit_local_to_cloud_fallback:
            raise ValueError("local-to-cloud implicit fallback is forbidden")


@dataclass(frozen=True, slots=True)
class AIProviderReadiness:
    provider_id: str
    state: AIProviderReadinessState
    checked_at: datetime | None
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if self.state is AIProviderReadinessState.READY and self.error_code:
            raise ValueError("ready provider cannot carry an error_code")
        if self.state not in {
            AIProviderReadinessState.READY,
            AIProviderReadinessState.DISABLED,
        } and self.checked_at is None:
            raise ValueError("non-disabled readiness requires checked_at")
        if (
            self.state not in {
                AIProviderReadinessState.READY,
                AIProviderReadinessState.DISABLED,
            }
            and not self.error_code
        ):
            raise ValueError("non-ready state requires an error_code")


@dataclass(frozen=True, slots=True)
class AIProviderRequest:
    operation_id: str
    task: AITask
    input_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    context: AIExecutionContext
    budget: AIBudget
    deadline_seconds: float

    def __post_init__(self) -> None:
        if not self.operation_id.strip():
            raise ValueError("operation_id is required")
        if not isfinite(self.deadline_seconds) or self.deadline_seconds <= 0:
            raise ValueError("deadline_seconds must be finite and positive")
        if len(self.input_refs) != len(set(self.input_refs)):
            raise ValueError("input_refs must be unique")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")


@dataclass(frozen=True, slots=True)
class AIProviderResponse:
    run: AIRun
    configuration_version: str
    provenance_ref: str
    provider_request_id: str | None
    observed_at: datetime

    def __post_init__(self) -> None:
        if not self.configuration_version.strip():
            raise ValueError("configuration_version is required")
        if not self.provenance_ref.strip():
            raise ValueError("provenance_ref is required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class AIProviderFailure:
    code: AIProviderFailureCode
    message: str
    retry_allowed: bool = False
    retry_safety_evidence_ref: str | None = None

    def __post_init__(self) -> None:
        if not self.message.strip():
            raise ValueError("message is required")
        if self.retry_allowed and not (
            self.retry_safety_evidence_ref
            and self.retry_safety_evidence_ref.strip()
        ):
            raise ValueError(
                "retry_allowed requires explicit retry-safety evidence"
            )


class AIProviderAdapter(Protocol):
    """Provider adapter boundary; implementations never own canonical business state."""

    provider_id: str

    def descriptor(self) -> AIProviderDescriptor: ...

    def activation(self) -> AIProviderActivation: ...

    def readiness(self) -> AIProviderReadiness: ...

    def invoke(self, request: AIProviderRequest) -> AIProviderResponse: ...


def validate_provider_activation(
    descriptor: AIProviderDescriptor,
    activation: AIProviderActivation,
) -> None:
    if descriptor.kind is AIProviderKind.CLOUD:
        if descriptor.provider_id not in APPROVED_CLOUD_PROVIDER_IDS:
            raise ValueError(
                "cloud AI provider is outside the approved allowlist"
            )
        if descriptor.provenance.free_commercial_use_verified:
            raise ValueError(
                "cloud provider provenance cannot be treated as local-model "
                "free-commercial-use certification"
            )

    if descriptor.kind is AIProviderKind.LOCAL_SELF_HOSTED:
        if not descriptor.provenance.free_commercial_use_verified:
            raise ValueError(
                "local/self-hosted model requires verified free commercial use"
            )
        if descriptor.provenance.license_checked_at is None:
            raise ValueError(
                "local/self-hosted model requires license verification date"
            )
        if not descriptor.provenance.artifact_digest:
            raise ValueError(
                "local/self-hosted model requires artifact digest"
            )

    if activation.enabled and not activation.explicit:
        raise ValueError("provider activation must be explicit")


def validate_provider_response(
    descriptor: AIProviderDescriptor,
    request: AIProviderRequest,
    response: AIProviderResponse,
) -> None:
    run = response.run
    if run.provider_id != descriptor.provider_id:
        raise ValueError("provider response has mismatched provider_id")
    if run.task_id != request.task.task_id:
        raise ValueError("provider response has mismatched task_id")
    if run.prompt_version != request.task.prompt_version:
        raise ValueError("provider response has mismatched prompt_version")
    if run.model != descriptor.model_id:
        raise ValueError("provider response has mismatched model_id")
    if run.model_version != descriptor.model_version:
        raise ValueError("provider response has mismatched model_version")
    if tuple(run.input_refs) != tuple(request.input_refs):
        raise ValueError("provider response has mismatched input_refs")
    if not set(run.evidence_refs).issubset(request.evidence_refs):
        raise ValueError("provider response contains unsupported evidence_refs")
    if response.configuration_version != descriptor.configuration_version:
        raise ValueError("provider response has mismatched configuration_version")
    if run.tokens > request.budget.max_tokens:
        raise ValueError("provider response exceeded token budget")
    if run.cost > request.budget.max_cost:
        raise ValueError("provider response exceeded cost budget")
    if run.duration_seconds > min(
        request.budget.max_duration_seconds,
        descriptor.resource_limits.max_duration_seconds,
        request.deadline_seconds,
    ):
        raise ValueError("provider response exceeded duration budget")
    output_bytes = len(run.output.encode("utf-8"))
    if output_bytes > descriptor.resource_limits.max_response_bytes:
        raise ValueError("provider response exceeded response-size limit")
