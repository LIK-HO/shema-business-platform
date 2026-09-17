from dataclasses import dataclass

import pytest

from shema_platform.application.ai import AIGateway, AIRun, AITask
from shema_platform.application.research import (
    ProviderCapability,
    ProviderGateway,
    ProviderResult,
    ResearchBudget,
)


@dataclass
class FakeProvider:
    provider_id: str
    capability: ProviderCapability
    cost: float

    def research(self, query: str, *, max_sources: int) -> ProviderResult:
        return ProviderResult(
            provider_id=self.provider_id,
            claims=(f"claim:{query}",),
            source_refs=(f"source:{self.provider_id}",),
            cost=self.cost,
            latency_seconds=0.01,
            tokens=50,
        )


@dataclass
class FakeAIProvider:
    provider_id: str = "fake-model"

    def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun:
        return AIRun(
            run_id="run-1",
            task_id=task.task_id,
            provider_id=self.provider_id,
            model="fake",
            model_version="1",
            prompt_version=task.prompt_version,
            input_refs=input_refs,
            evidence_refs=("evidence:1",),
            output="derived output",
            tokens=10,
            cost=0.01,
            duration_seconds=0.01,
        )


def test_provider_gateway_respects_explicit_budgets() -> None:
    gateway = ProviderGateway()
    provider = FakeProvider(
        provider_id="p1",
        capability=ProviderCapability(
            "p1",
            frozenset({"company"}),
            cost_per_call=0.50,
            max_requests_per_second=1,
            estimated_tokens_per_call=50,
            estimated_latency_seconds=0.01,
        ),
        cost=0.50,
    )
    results = gateway.research(
        "company query",
        "company",
        [provider],
        ResearchBudget(
            provider_calls=1,
            source_count=3,
            token_budget=1000,
            api_cost_limit=0.50,
            time_budget_seconds=10,
        ),
    )
    assert len(results) == 1


def test_provider_gateway_skips_provider_over_budget() -> None:
    gateway = ProviderGateway()
    provider = FakeProvider(
        provider_id="expensive",
        capability=ProviderCapability(
            "expensive",
            frozenset({"company"}),
            cost_per_call=1.00,
            max_requests_per_second=1,
            estimated_tokens_per_call=5000,
            estimated_latency_seconds=20,
        ),
        cost=1.00,
    )
    results = gateway.research(
        "company query",
        "company",
        [provider],
        ResearchBudget(
            provider_calls=1,
            source_count=3,
            token_budget=100,
            api_cost_limit=1.00,
            time_budget_seconds=10,
        ),
    )
    assert results == ()


def test_ai_gateway_requires_evidence_when_task_requires_it() -> None:
    task = AITask("task-1", "classification", "prompt-v1", evidence_required=True)
    gateway = AIGateway(FakeAIProvider())
    with pytest.raises(ValueError):
        gateway.execute(task, input_refs=("company:1",), evidence_refs=())


def test_ai_gateway_rejects_provider_evidence_not_supplied_by_caller() -> None:
    task = AITask("task-1", "classification", "prompt-v1", evidence_required=True)
    gateway = AIGateway(FakeAIProvider())
    with pytest.raises(ValueError):
        gateway.execute(
            task,
            input_refs=("company:1",),
            evidence_refs=("evidence:other",),
        )
