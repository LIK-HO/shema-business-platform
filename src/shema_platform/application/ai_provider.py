from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import TYPE_CHECKING, Protocol

if TYPE_CHECKING:
    from shema_platform.application.ai import AIBudget, AIExecutionContext, AIRun, AITask


class AIProviderKind(StrEnum):
    CLOUD = "cloud"
    LOCAL = "local"


class AIProviderReadiness(StrEnum):
    READY = "ready"
    NOT_READY = "not_ready"
    DISABLED = "disabled"


class AIProviderFailureCode(StrEnum):
    CONFIGURATION_INVALID = "configuration_invalid"
    NOT_READY = "not_ready"
    UNAVAILABLE = "unavailable"
    AUTHENTICATION_FAILED = "authentication_failed"
    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    RESOURCE_LIMIT = "resource_limit"
    MALFORMED_RESPONSE = "malformed_response"
    PROVIDER_ERROR = "provider_error"


@dataclass(frozen=True, slots=True)
class AIProviderFailure(RuntimeError):
    """Provider failure without a built-in retry or fallback policy."""

    code: AIProviderFailureCode
    detail: str

    def __post_init__(self) -> None:
        if not self.detail.strip():
            raise ValueError("AI provider failure detail is required")

    def __str__(self) -> str:
        return f"{self.code.value}: {self.detail}"


@dataclass(frozen=True, slots=True)
class AIProviderLimits:
    """Operational bounds owned by the adapter boundary, not business semantics."""

    max_request_bytes: int
    max_response_bytes: int
    max_duration_seconds: float
    max_concurrency: int

    def __post_init__(self) -> None:
        if self.max_request_bytes <= 0 or self.max_response_bytes <= 0:
            raise ValueError("AI provider byte limits must be positive")
        if (
            not isfinite(self.max_duration_seconds)
            or self.max_duration_seconds <= 0
        ):
            raise ValueError("AI provider duration limit must be positive")
        if self.max_concurrency <= 0:
            raise ValueError("AI provider concurrency limit must be positive")


@dataclass(frozen=True, slots=True)
class AIProviderProvenance:
    """Non-secret provenance metadata for the selected provider/model configuration."""

    source: str
    license_name: str | None = None
    license_url: str | None = None
    license_checked_at: str | None = None
    artifact_digest: str | None = None
    runtime: str | None = None
    security_status: str = "unknown"
    free_commercial_use_verified: bool | None = None

    def __post_init__(self) -> None:
        if not self.source.strip():
            raise ValueError("AI provider provenance source is required")
        if not self.security_status.strip():
            raise ValueError("AI provider security status is required")


@dataclass(frozen=True, slots=True)
class AIProviderDescriptor:
    """Immutable runtime snapshot used for one provider execution decision."""

    provider_id: str
    provider_kind: AIProviderKind
    model: str
    model_version: str
    configuration_version: str
    capabilities: frozenset[str]
    limits: AIProviderLimits
    provenance: AIProviderProvenance

    def __post_init__(self) -> None:
        if not all(
            value.strip()
            for value in (
                self.provider_id,
                self.model,
                self.model_version,
                self.configuration_version,
            )
        ):
            raise ValueError("AI provider identity and configuration version are required")
        if not self.capabilities:
            raise ValueError("AI provider capabilities cannot be empty")

        provenance = self.provenance
        if self.provider_kind is AIProviderKind.LOCAL:
            required = (
                provenance.license_name,
                provenance.license_url,
                provenance.license_checked_at,
                provenance.artifact_digest,
                provenance.runtime,
            )
            if not all(value and value.strip() for value in required):
                raise ValueError(
                    "local AI models require license, verification, digest and runtime metadata"
                )
            if provenance.free_commercial_use_verified is not True:
                raise ValueError(
                    "local AI models require verified free commercial use permission"
                )


@dataclass(frozen=True, slots=True)
class AIProviderReadinessState:
    status: AIProviderReadiness
    reason_code: str | None = None

    def __post_init__(self) -> None:
        if self.status is AIProviderReadiness.READY and self.reason_code is not None:
            raise ValueError("ready provider cannot carry a failure reason")
        if self.status is not AIProviderReadiness.READY and (
            self.reason_code is None or not self.reason_code.strip()
        ):
            raise ValueError("non-ready provider requires a reason code")


@dataclass(frozen=True, slots=True)
class AIProviderRequest:
    """Single bounded execution envelope passed from the gateway to an adapter."""

    task: AITask
    input_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    context: AIExecutionContext
    budget: AIBudget
    provider_snapshot: AIProviderDescriptor


class AIProviderAdapter(Protocol):
    """Provider-neutral adapter boundary for cloud and local/self-hosted AI."""

    def describe(self) -> AIProviderDescriptor: ...

    def readiness(self) -> AIProviderReadinessState: ...

    def execute(self, request: AIProviderRequest) -> AIRun: ...


AIProvider = AIProviderAdapter
