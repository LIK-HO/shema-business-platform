from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import uuid4

from shema_platform.application.ports import UnitOfWork
from shema_platform.application.research import (
    ProviderGateway,
    ProviderResult,
    ResearchBudget,
    ResearchProvider,
)
from shema_platform.application.research_routing import (
    ResearchDepth,
    ResearchRoute,
    ResearchRoutingPolicy,
)
from shema_platform.foundation.errors import QuarantineRequired
from shema_platform.foundation.evidence import (
    Evidence,
    EvidenceLifecycle,
    TrustLevel,
    TruthClass,
)


@dataclass(frozen=True, slots=True)
class IntelligenceRun:
    subject_ref: str
    route: ResearchRoute
    results: tuple[ProviderResult, ...]
    evidence: tuple[Evidence, ...]


class IntelligenceService:
    """Runs routed research and materializes provider claims as traceable Evidence."""

    def __init__(
        self,
        routing_policy: ResearchRoutingPolicy,
        provider_gateway: ProviderGateway,
        unit_of_work_factory: Callable[[], UnitOfWork],
    ) -> None:
        self._routing = routing_policy
        self._providers = provider_gateway
        self._unit_of_work_factory = unit_of_work_factory

    def run(
        self,
        *,
        subject_ref: str,
        company_type: str,
        depth: ResearchDepth,
        query: str,
        providers: Sequence[ResearchProvider],
        budget: ResearchBudget,
    ) -> IntelligenceRun:
        if not subject_ref.strip():
            raise ValueError("subject_ref is required")

        route = self._routing.route(company_type, depth)
        results = self._providers.research(
            query,
            topic=company_type.strip().lower(),
            providers=list(providers),
            budget=budget,
            allowed_source_classes=route.allowed_source_classes(),
        )

        covered = frozenset(result.source_class for result in results)
        missing = route.required_source_classes() - covered
        if missing:
            raise QuarantineRequired(
                "research route missing required source classes: "
                + ", ".join(sorted(missing))
            )

        now = datetime.now(UTC)
        evidence: list[Evidence] = []
        for result in results:
            source_ref = (
                result.source_refs[0]
                if result.source_refs
                else f"provider:{result.provider_id}"
            )
            provenance = {
                "provider": result.provider_id,
                "source_class": result.source_class,
                "source_refs": ",".join(result.source_refs),
            }
            for claim in result.claims:
                record = Evidence(
                    evidence_id=str(uuid4()),
                    subject_ref=subject_ref,
                    claim=claim,
                    source_ref=source_ref,
                    observed_at=now,
                    captured_at=now,
                    truth_class=TruthClass.EVIDENCE,
                    trust_level=TrustLevel.T1_OBSERVED,
                    confidence=result.confidence,
                    provenance=provenance,
                    lifecycle=EvidenceLifecycle.ACTIVE,
                )
                evidence.append(record)

        # External provider calls are complete before the transactional boundary opens.
        with self._unit_of_work_factory() as uow:
            for record in evidence:
                uow.evidence.add(record)

        return IntelligenceRun(
            subject_ref=subject_ref,
            route=route,
            results=results,
            evidence=tuple(evidence),
        )
