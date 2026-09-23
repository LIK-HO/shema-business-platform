import os
from pathlib import Path

import psycopg
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
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


class FakeProvider(ResearchProvider):
    def __init__(self, provider_id: str, source_class: str, claim: str) -> None:
        self.capability = ProviderCapability(
            provider_id=provider_id,
            source_class=source_class,
            coverage=frozenset({"logistics"}),
            cost_per_call=0.1,
            max_requests_per_second=5,
        )
        self._result = ProviderResult(
            provider_id=provider_id,
            source_class=source_class,
            claims=(claim,),
            source_refs=(f"source:{provider_id}",),
            confidence=0.9,
            cost=0.1,
            latency_seconds=0.1,
        )

    def research(self, query: str, *, max_sources: int) -> ProviderResult:
        return self._result


def apply_migration(connection: psycopg.Connection, path: Path) -> None:
    for statement in path.read_text().split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def test_routed_intelligence_persists_evidence_in_postgres() -> None:
    routing = ResearchRoutingPolicy(
        (
            ResearchRoute(
                "logistics",
                ResearchDepth.R2_CONTEXT,
                (
                    SourceRule("official_registry", SourceRequirement.REQUIRED),
                    SourceRule("company_site", SourceRequirement.OPTIONAL),
                ),
            ),
        )
    )

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migration(connection, ROOT / "db/migrations/0001_foundation.sql")
        connection.commit()

        service = IntelligenceService(
            routing,
            ProviderGateway(),
            lambda: PostgresUnitOfWork(lambda: psycopg.connect(DATABASE_URL)),
        )

        run = service.run(
            subject_ref="identity:integration",
            company_type="logistics",
            depth=ResearchDepth.R2_CONTEXT,
            query="ООО Integration Test",
            providers=[
                FakeProvider("registry", "official_registry", "Registry confirms identity"),
                FakeProvider("site", "company_site", "Site confirms service fit"),
            ],
            budget=ResearchBudget(
                provider_calls=3,
                source_count=10,
                token_budget=100,
                api_cost_limit=1,
                time_budget_seconds=10,
            ),
        )

        assert len(run.evidence) == 2

        row = connection.execute(
            """
            select count(*)
            from evidence
            where subject_ref = %s
            """,
            ("identity:integration",),
        ).fetchone()
        assert row == (2,)

        connection.execute(
            "delete from evidence where subject_ref = %s",
            ("identity:integration",),
        )
        connection.commit()


def test_routed_intelligence_fails_closed_before_persisting_partial_evidence() -> None:
    routing = ResearchRoutingPolicy(
        (
            ResearchRoute(
                "logistics",
                ResearchDepth.R2_CONTEXT,
                (
                    SourceRule("official_registry", SourceRequirement.REQUIRED),
                    SourceRule("company_site", SourceRequirement.OPTIONAL),
                ),
            ),
        )
    )

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migration(connection, ROOT / "db/migrations/0001_foundation.sql")

        service = IntelligenceService(
            routing,
            ProviderGateway(),
            lambda: PostgresUnitOfWork(lambda: psycopg.connect(DATABASE_URL)),
        )

        with pytest.raises(QuarantineRequired):
            service.run(
                subject_ref="identity:integration",
                company_type="logistics",
                depth=ResearchDepth.R2_CONTEXT,
                query="ООО Integration Test",
                providers=[FakeProvider("site", "company_site", "Only site evidence")],
                budget=ResearchBudget(
                    provider_calls=1,
                    source_count=5,
                    token_budget=50,
                    api_cost_limit=1,
                    time_budget_seconds=5,
                ),
            )

        row = connection.execute(
            """
            select count(*)
            from evidence
            where subject_ref = %s
            """,
            ("identity:integration",),
        ).fetchone()
        assert row == (0,)
