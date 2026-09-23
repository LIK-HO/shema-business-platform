from dataclasses import dataclass

import pytest

from shema_platform.application.research import (
    ProviderCapability,
    ProviderGateway,
    ProviderResult,
    ResearchBudget,
)
from shema_platform.application.provider_resource_guard import (
    ProviderCallDecision,
    ProviderRateLimiter,
    ProviderResourceGuard,
)


def capability(
    provider_id: str = "provider",
    *,
    cost: float = 1.0,
    rate: float = 2.0,
    tokens: int = 10,
    latency: float = 1.0,
) -> ProviderCapability:
    return ProviderCapability(
        provider_id=provider_id,
        source_class="official_registry",
        coverage=frozenset({"logistics"}),
        cost_per_call=cost,
        max_requests_per_second=rate,
        estimated_tokens_per_call=tokens,
        estimated_latency_seconds=latency,
    )


def budget(
    *,
    calls: int = 1,
    sources: int = 10,
    tokens: int = 10,
    cost: float = 1.0,
    time: float = 1.0,
) -> ResearchBudget:
    return ResearchBudget(
        provider_calls=calls,
        source_count=sources,
        token_budget=tokens,
        api_cost_limit=cost,
        time_budget_seconds=time,
    )


def test_guard_allows_call_inside_estimated_budget() -> None:
    guard = ProviderResourceGuard(
        ProviderRateLimiter(clock=lambda: 0.0)
    )

    decision = guard.authorize(
        capability(),
        budget(),
        remaining_calls=1,
        remaining_sources=10,
        remaining_tokens=10,
        remaining_cost=1.0,
        remaining_time=1.0,
        requested_sources=10,
    )

    assert decision == ProviderCallDecision(
        allowed=True,
        stop_operation=False,
        reason=None,
    )


@pytest.mark.parametrize(
    ("remaining_cost", "remaining_tokens", "remaining_time", "reason"),
    [
        (0.5, 10, 1.0, "provider_cost_limit"),
        (1.0, 5, 1.0, "provider_token_limit"),
        (1.0, 10, 0.5, "provider_time_limit"),
    ],
)
def test_guard_rejects_before_io_for_estimated_resource_overrun(
    remaining_cost: float,
    remaining_tokens: int,
    remaining_time: float,
    reason: str,
) -> None:
    guard = ProviderResourceGuard(
        ProviderRateLimiter(clock=lambda: 0.0)
    )

    decision = guard.authorize(
        capability(),
        budget(),
        remaining_calls=1,
        remaining_sources=10,
        remaining_tokens=remaining_tokens,
        remaining_cost=remaining_cost,
        remaining_time=remaining_time,
        requested_sources=10,
    )

    assert decision.allowed is False
    assert decision.stop_operation is False
    assert decision.reason == reason


def test_guard_stops_when_provider_call_budget_is_exhausted() -> None:
    guard = ProviderResourceGuard(
        ProviderRateLimiter(clock=lambda: 0.0)
    )

    decision = guard.authorize(
        capability(),
        budget(calls=0),
        remaining_calls=0,
        remaining_sources=10,
        remaining_tokens=10,
        remaining_cost=1.0,
        remaining_time=1.0,
        requested_sources=10,
    )

    assert decision == ProviderCallDecision(
        allowed=False,
        stop_operation=True,
        reason="provider_call_budget_exhausted",
    )


def test_rate_limiter_rejects_second_call_before_interval() -> None:
    now = [0.0]
    limiter = ProviderRateLimiter(clock=lambda: now[0])

    assert limiter.allow("provider", 2.0) is True
    now[0] = 0.25
    assert limiter.allow("provider", 2.0) is False
    now[0] = 0.5
    assert limiter.allow("provider", 2.0) is True


@dataclass
class CountingProvider:
    capability: ProviderCapability
    calls: int = 0

    def research(self, query: str, *, max_sources: int) -> ProviderResult:
        self.calls += 1
        return ProviderResult(
            provider_id=self.capability.provider_id,
            source_class=self.capability.source_class,
            claims=(),
            source_refs=(),
            confidence=0.5,
            cost=self.capability.cost_per_call,
            latency_seconds=self.capability.estimated_latency_seconds,
            tokens=self.capability.estimated_tokens_per_call,
        )


def test_gateway_does_not_call_provider_when_preflight_budget_denies() -> None:
    provider = CountingProvider(
        capability(
            cost=2.0,
            rate=1000.0,
            tokens=1,
            latency=1,
        )
    )
    gateway = ProviderGateway(
        resource_guard=ProviderResourceGuard(
            ProviderRateLimiter(clock=lambda: 0.0)
        )
    )

    results = gateway.research(
        "query",
        "logistics",
        [provider],
        budget(cost=1.0, tokens=10, time=1.0),
    )

    assert results == ()
    assert provider.calls == 0


def test_gateway_rate_guard_blocks_second_external_call() -> None:
    provider = CountingProvider(
        capability(
            provider_id="provider",
            cost=0.1,
            rate=2.0,
            tokens=1,
            latency=0.1,
        )
    )
    now = [0.0]
    gateway = ProviderGateway(
        resource_guard=ProviderResourceGuard(
            ProviderRateLimiter(clock=lambda: now[0])
        )
    )
    research_budget = budget(
        calls=1,
        sources=1,
        tokens=1,
        cost=0.1,
        time=0.1,
    )

    first = gateway.research(
        "query",
        "logistics",
        [provider],
        research_budget,
    )
    second = gateway.research(
        "query",
        "logistics",
        [provider],
        research_budget,
    )

    assert len(first) == 1
    assert second == ()
    assert provider.calls == 1
