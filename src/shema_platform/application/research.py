from __future__ import annotations

from dataclasses import dataclass
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
        if self.api_cost_limit < 0:
            raise ValueError("api_cost_limit cannot be negative")


@dataclass(frozen=True, slots=True)
class ProviderCapability:
    provider_id: str
    coverage: frozenset[str]
    cost_per_call: float
    max_requests_per_second: float
    healthy: bool = True


@dataclass(frozen=True, slots=True)
class ProviderResult:
    provider_id: str
    claims: tuple[str, ...]
    source_refs: tuple[str, ...]
    cost: float
    latency_seconds: float


class ResearchProvider(Protocol):
    capability: ProviderCapability

    def research(self, query: str, *, max_sources: int) -> ProviderResult: ...


class ProviderGateway:
    """Deterministic provider waterfall with explicit cost/source/call budgets."""

    def select(self, providers: list[ResearchProvider], topic: str) -> list[ResearchProvider]:
        return sorted(
            (
                provider
                for provider in providers
                if provider.capability.healthy and topic in provider.capability.coverage
            ),
            key=lambda provider: provider.capability.cost_per_call,
        )

    def research(
        self,
        query: str,
        topic: str,
        providers: list[ResearchProvider],
        budget: ResearchBudget,
    ) -> tuple[ProviderResult, ...]:
        remaining_calls = budget.provider_calls
        remaining_sources = budget.source_count
        remaining_cost = budget.api_cost_limit
        results: list[ProviderResult] = []

        for provider in self.select(providers, topic):
            if remaining_calls <= 0 or remaining_sources <= 0:
                break
            if provider.capability.cost_per_call > remaining_cost:
                continue

            max_sources = min(remaining_sources, 10)
            result = provider.research(query, max_sources=max_sources)
            if result.cost > remaining_cost:
                continue

            results.append(result)
            remaining_calls -= 1
            remaining_sources -= len(result.source_refs)
            remaining_cost -= result.cost

        return tuple(results)
