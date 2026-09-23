from __future__ import annotations

from dataclasses import dataclass
import time
from math import isfinite
from typing import Protocol


@dataclass(frozen=True, slots=True)
class ResearchBudget:
    provider_calls: int
    source_count: int
    token_budget: int
    api_cost_limit: float
    time_budget_seconds: float

    def __post_init__(self) -> None:
        if min(
            self.provider_calls,
            self.source_count,
            self.token_budget,
            self.time_budget_seconds,
        ) < 0:
            raise ValueError("research budget values cannot be negative")
        if not isfinite(self.api_cost_limit) or self.api_cost_limit < 0:
            raise ValueError("api_cost_limit must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider_id: str
    source_class: str
    coverage: frozenset[str]
    cost_per_call: float
    max_requests_per_second: float
    estimated_tokens_per_call: int = 0
    estimated_latency_seconds: float = 0.0
    healthy: bool = True

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.source_class.strip():
            raise ValueError("source_class is required")
        if (
            not isfinite(self.cost_per_call)
            or not isfinite(self.max_requests_per_second)
            or self.cost_per_call < 0
            or self.max_requests_per_second <= 0
        ):
            raise ValueError("provider capability has invalid cost/rate limits")
        if self.estimated_tokens_per_call < 0 or self.estimated_latency_seconds < 0:
            raise ValueError("provider estimates cannot be negative")


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider_id: str
    source_class: str
    claims: tuple[str, ...]
    source_refs: tuple[str, ...]
    confidence: float
    cost: float
    latency_seconds: float
    tokens: int = 0

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.source_class.strip():
            raise ValueError("source_class is required")
        if not 0.0 <= self.confidence <= 1.0:
            raise ValueError("confidence must be between 0 and 1")
        if (
            not isfinite(self.cost)
            or not isfinite(self.latency_seconds)
            or self.cost < 0
            or self.latency_seconds < 0
            or self.tokens < 0
        ):
            raise ValueError("provider result usage metrics are invalid")
        if any(not ref.strip() for ref in self.source_refs):
            raise ValueError("source references cannot be empty")
        if self.claims and not self.source_refs:
            raise ValueError("claims require at least one source reference")


class ResearchProvider(Protocol):
    capability: ProviderCapability

    def research(
        self,
        query: str,
        *,
        max_sources: int,
        timeout_seconds: float | None = None,
    ) -> ProviderResult: ...


class ProviderGateway:
    """Deterministic provider waterfall with explicit budget enforcement."""

    def select(
        self,
        providers: list[ResearchProvider],
        topic: str,
        *,
        allowed_source_classes: frozenset[str] | None = None,
    ) -> list[ResearchProvider]:
        return sorted(
            (
                provider
                for provider in providers
                if provider.capability.healthy
                and topic in provider.capability.coverage
                and (
                    allowed_source_classes is None
                    or provider.capability.source_class in allowed_source_classes
                )
            ),
            key=lambda provider: provider.capability.cost_per_call,
        )

    def research(
        self,
        query: str,
        topic: str,
        providers: list[ResearchProvider],
        budget: ResearchBudget,
        *,
        allowed_source_classes: frozenset[str] | None = None,
    ) -> tuple[ProviderResult, ...]:
        remaining_calls = budget.provider_calls
        remaining_sources = budget.source_count
        remaining_tokens = budget.token_budget
        remaining_cost = budget.api_cost_limit
        deadline = time.monotonic() + budget.time_budget_seconds
        results: list[ProviderResult] = []

        for provider in self.select(
            providers,
            topic,
            allowed_source_classes=allowed_source_classes,
        ):
            capability = provider.capability
            remaining_time = deadline - time.monotonic()
            if remaining_calls <= 0 or remaining_sources <= 0 or remaining_time <= 0:
                break
            if capability.cost_per_call > remaining_cost:
                continue
            if capability.estimated_tokens_per_call > remaining_tokens:
                continue
            if capability.estimated_latency_seconds > remaining_time:
                continue

            max_sources = min(remaining_sources, 10)
            result = provider.research(
                query,
                max_sources=max_sources,
                timeout_seconds=remaining_time,
            )

            if result.provider_id != capability.provider_id:
                raise ValueError("provider result has mismatched provider_id")
            if result.source_class != capability.source_class:
                raise ValueError("provider result has mismatched source_class")
            if (
                allowed_source_classes is not None
                and result.source_class not in allowed_source_classes
            ):
                raise ValueError("provider result uses a prohibited source class")
            if len(result.source_refs) > max_sources:
                raise ValueError("provider exceeded requested source limit")
            if result.cost > remaining_cost:
                continue
            if result.tokens > remaining_tokens or result.latency_seconds > remaining_time:
                continue

            results.append(result)
            remaining_calls -= 1
            remaining_sources -= len(result.source_refs)
            remaining_tokens -= result.tokens
            remaining_cost -= result.cost

        return tuple(results)
