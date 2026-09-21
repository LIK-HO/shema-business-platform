from dataclasses import dataclass, field

import pytest

from shema_platform.application.intelligence import IntelligenceService
from shema_platform.application.research import (
    ProviderCapability,
    ProviderGateway,
    ProviderResult,
    ResearchBudget,
    ResearchProvider,
)
from shema_platform.application.research_routing import (
    ResearchDepth,
    ResearchRoute,
    ResearchRoutingPolicy,
    SourceRequirement,
    SourceRule,
)
from shema_platform.foundation.errors import QuarantineRequired


@dataclass
class MemoryEvidenceRepository:
    records: list = field(default_factory=list)

    def add(self, evidence) -> None:
        self.records.append(evidence)


@dataclass
class FakeProvider(ResearchProvider):
    capability: ProviderCapability
    result: ProviderResult

    def research(self, query: str, *, max_sources: int) -> ProviderResult:
        return self.result


def provider(
    provider_id: str,
    source_class: str,
    claim: str,
) -> FakeProvider:
    return FakeProvider(
        capability=ProviderCapability(
            provider_id=provider_id,
            source_class=source_class,
            coverage=frozenset({"logistics"}),
            cost_per_call=0.1,
            max_requests_per_second=5,
        ),
        result=ProviderResult(
            provider_id=provider_id,
            source_class=source_class,
            claims=(claim,),
            source_refs=(f"source:{provider_id}",),
            confidence=0.9,
            cost=0.1,
            latency_seconds=0.1,
        ),
    )


def budget() -> ResearchBudget:
    return ResearchBudget(
        provider_calls=3,
        source_count=10,
        token_budget=100,
        api_cost_limit=1,
        time_budget_seconds=10,
    )


def make_service(repository: MemoryEvidenceRepository) -> IntelligenceService:
    routing = ResearchRoutingPolicy(
        (
            ResearchRoute(
                company_type="logistics",
                depth=ResearchDepth.R2_CONTEXT,
                rules=(
                    SourceRule("official_registry", SourceRequirement.REQUIRED),
                    SourceRule("company_site", SourceRequirement.OPTIONAL),
                ),
            ),
        )
    )
    return IntelligenceService(routing, ProviderGateway(), repository)


def test_intelligence_materializes_routed_claims_as_evidence() -> None:
    repository = MemoryEvidenceRepository()
    service = make_service(repository)

    run = service.run(
        subject_ref="identity:1",
        company_type="logistics",
        depth=ResearchDepth.R2_CONTEXT,
        query="ООО Альфа",
        providers=[
            provider("registry", "official_registry", "INN is active"),
            provider("site", "company_site", "Company operates logistics"),
        ],
        budget=budget(),
    )

    assert len(run.evidence) == 2
    assert len(repository.records) == 2
    assert {record.source_ref for record in run.evidence} == {
        "source:registry",
        "source:site",
    }
    assert all(record.confidence == 0.9 for record in run.evidence)


def test_intelligence_fails_closed_when_required_source_is_missing() -> None:
    repository = MemoryEvidenceRepository()
    service = make_service(repository)

    with pytest.raises(QuarantineRequired, match="missing required source"):
        service.run(
            subject_ref="identity:1",
            company_type="logistics",
            depth=ResearchDepth.R2_CONTEXT,
            query="ООО Альфа",
            providers=[provider("site", "company_site", "Only site evidence")],
            budget=budget(),
        )


def test_intelligence_rejects_prohibited_provider_class_via_route() -> None:
    routing = ResearchRoutingPolicy(
        (
            ResearchRoute(
                "logistics",
                ResearchDepth.R1_IDENTITY,
                (
                    SourceRule("official_registry", SourceRequirement.REQUIRED),
                    SourceRule("social_profile", SourceRequirement.PROHIBITED),
                ),
            ),
        )
    )
    repository = MemoryEvidenceRepository()
    service = IntelligenceService(routing, ProviderGateway(), repository)

    with pytest.raises(QuarantineRequired, match="missing required source"):
        service.run(
            subject_ref="identity:1",
            company_type="logistics",
            depth=ResearchDepth.R1_IDENTITY,
            query="ООО Альфа",
            providers=[provider("social", "social_profile", "Social signal")],
            budget=budget(),
        )
