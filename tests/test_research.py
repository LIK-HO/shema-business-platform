from dataclasses import dataclass

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

    def research(self, query: str, *, max_sources: int) -> ProviderResult:
        return self.result


def provider(
    provider_id: str,
    *,
    cost: float,
    topic: str = "logistics",
    sources: tuple[str, ...] = ("source:1",),
) -> FakeProvider:
    return FakeProvider(
        capability=ProviderCapability(
            provider_id=provider_id,
            coverage=frozenset({topic}),
            cost_per_call=cost,
            max_requests_per_second=5,
            estimated_tokens_per_call=10,
            estimated_latency_seconds=1,
        ),
        result=ProviderResult(
            provider_id=provider_id,
            claims=("claim",),
            source_refs=sources,
            cost=cost,
            latency_seconds=1,
            tokens=10,
        ),
    )


def test_research_gateway_selects_healthy_covered_providers_by_cost() -> None:
    gateway = ProviderGateway()
    providers = [provider("expensive", cost=2.0), provider("cheap", cost=0.5)]

    selected = gateway.select(providers, "logistics")

    assert [item.capability.provider_id for item in selected] == ["cheap", "expensive"]


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
    )

    assert len(results) == 1
    assert results[0].provider_id == "cheap"


def test_provider_results_require_source_references_for_claims() -> None:
    with pytest.raises(ValueError, match="source reference"):
        ProviderResult(
            provider_id="provider",
            claims=("unsupported claim",),
            source_refs=(),
            cost=0,
            latency_seconds=0,
        )
