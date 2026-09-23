from dataclasses import dataclass, field

import pytest

from shema_platform.application.research import (
    ProviderCapability,
    ProviderGateway,
    ProviderResult,
    ResearchBudget,
    ResearchProvider,
)


@dataclass
class FakeProvider(ResearchProvider):
    capability: ProviderCapability
    result: ProviderResult
    timeouts: list[float | None] = field(default_factory=list)

    def research(
        self,
        query: str,
        *,
        max_sources: int,
        timeout_seconds: float | None = None,
    ) -> ProviderResult:
        self.timeouts.append(timeout_seconds)
        return self.result


def provider(
    provider_id: str,
    *,
    cost: float,
    source_class: str = "official_registry",
    topic: str = "logistics",
    sources: tuple[str, ...] = ("source:1",),
) -> FakeProvider:
    capability = ProviderCapability(
        provider_id=provider_id,
        source_class=source_class,
        coverage=frozenset({topic}),
        cost_per_call=cost,
        max_requests_per_second=5,
        estimated_tokens_per_call=10,
        estimated_latency_seconds=1,
    )
    result = ProviderResult(
        provider_id=provider_id,
        source_class=source_class,
        claims=("claim",),
        source_refs=sources,
        confidence=0.9,
        cost=cost,
        latency_seconds=1,
        tokens=10,
    )
    return FakeProvider(capability=capability, result=result)


def test_research_gateway_selects_healthy_covered_providers_by_cost() -> None:
    gateway = ProviderGateway()
    providers = [provider("expensive", cost=2.0), provider("cheap", cost=0.5)]

    selected = gateway.select(
        providers,
        "logistics",
        allowed_source_classes=frozenset({"official_registry"}),
    )

    assert [item.capability.provider_id for item in selected] == ["cheap", "expensive"]


def test_research_gateway_excludes_prohibited_source_class() -> None:
    gateway = ProviderGateway()
    selected = gateway.select(
        [provider("social", cost=0.1, source_class="social_profile")],
        "logistics",
        allowed_source_classes=frozenset({"official_registry"}),
    )

    assert selected == []


def test_research_gateway_enforces_budget() -> None:
    gateway = ProviderGateway()
    results = gateway.research(
        "Москва логистика",
        "logistics",
        [provider("cheap", cost=0.5), provider("expensive", cost=2.0)],
        ResearchBudget(
            provider_calls=1,
            source_count=3,
            token_budget=20,
            api_cost_limit=1.0,
            time_budget_seconds=2.0,
        ),
        allowed_source_classes=frozenset({"official_registry"}),
    )

    assert len(results) == 1
    assert results[0].provider_id == "cheap"


def test_research_gateway_propagates_remaining_time_budget() -> None:
    gateway = ProviderGateway()
    candidate = provider("deadline-aware", cost=0.5)

    results = gateway.research(
        "Москва логистика",
        "logistics",
        [candidate],
        ResearchBudget(
            provider_calls=1,
            source_count=2,
            token_budget=20,
            api_cost_limit=1.0,
            time_budget_seconds=2.5,
        ),
    )

    assert len(results) == 1
    assert candidate.timeouts == [2.5]


def test_research_gateway_uses_wall_clock_remaining_time(monkeypatch) -> None:
    import shema_platform.application.research as research_module

    now = [100.0]
    monkeypatch.setattr(research_module.time, "monotonic", lambda: now[0])

    gateway = ProviderGateway()
    first = provider("first", cost=0.5)
    second = provider("second", cost=0.5)

    class AdvancingProvider:
        def __init__(self, wrapped: FakeProvider, advance: float) -> None:
            self.capability = wrapped.capability
            self._wrapped = wrapped
            self._advance = advance
            self.timeouts = wrapped.timeouts

        def research(
            self,
            query: str,
            *,
            max_sources: int,
            timeout_seconds: float | None = None,
        ) -> ProviderResult:
            result = self._wrapped.research(
                query,
                max_sources=max_sources,
                timeout_seconds=timeout_seconds,
            )
            now[0] += self._advance
            return result

    first_wrapped = AdvancingProvider(first, 1.5)
    second_wrapped = AdvancingProvider(second, 0.0)

    results = gateway.research(
        "Москва логистика",
        "logistics",
        [first_wrapped, second_wrapped],
        ResearchBudget(
            provider_calls=2,
            source_count=4,
            token_budget=40,
            api_cost_limit=2.0,
            time_budget_seconds=2.5,
        ),
    )

    assert len(results) == 2
    assert first.timeouts == [2.5]
    assert second.timeouts == [1.0]


def test_provider_results_require_source_references_for_claims() -> None:
    with pytest.raises(ValueError, match="source reference"):
        ProviderResult(
            provider_id="provider",
            source_class="official_registry",
            claims=("unsupported claim",),
            source_refs=(),
            confidence=0.5,
            cost=0,
            latency_seconds=0,
        )


def test_provider_result_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError, match="confidence"):
        ProviderResult(
            provider_id="provider",
            source_class="official_registry",
            claims=(),
            source_refs=("source:1",),
            confidence=1.5,
            cost=0,
            latency_seconds=0,
        )
