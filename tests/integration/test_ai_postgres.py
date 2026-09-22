import os
from pathlib import Path

import psycopg
import pytest

from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIGateway,
    AIProvider,
    AIRun,
    AITask,
)
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.platform.postgres import PostgresUnitOfWork
from shema_platform.platform.postgres_repositories import (
    PostgresAIRunRepository,
    PostgresAuditRepository,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


class FakeProvider(AIProvider):
    provider_id = "provider:integration"

    def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun:
        return AIRun(
            run_id="run:integration",
            task_id=task.task_id,
            provider_id=self.provider_id,
            model="fake-model",
            model_version="1",
            prompt_version=task.prompt_version,
            input_refs=input_refs,
            evidence_refs=("evidence:integration",),
            output="qualified",
            tokens=10,
            cost=0.01,
            duration_seconds=0.1,
        )


def apply_migrations(connection: psycopg.Connection) -> None:
    for name in (
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
        "0005_ai_run.sql",
    ):
        for statement in (ROOT / "db/migrations" / name).read_text().split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)


def test_ai_gateway_persists_run_and_audit_to_postgres() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        apply_migrations(connection)

        authorizer = RBACAuthorizer(
            (
                AuthorizationSubject(
                    "operator-1",
                    frozenset({Permission.AI_RUN}),
                ),
            )
        )
        runs = PostgresAIRunRepository(connection)
        gateway = AIGateway(
            FakeProvider(),
            authorizer,
            PolicyEngine(),
            lambda: PostgresUnitOfWork(lambda: connection),
        )

        result = gateway.execute(
            AITask("task:integration", "qualification", "prompt:v1"),
            input_refs=("identity:integration",),
            evidence_refs=("evidence:integration",),
            context=AIExecutionContext(
                actor_id="operator-1",
                resource_ref="identity:integration",
                actor_trust_level=2,
                resource_trust_level=2,
                evidence_level=2,
                correlation_id="corr:ai",
                configuration_version="cfg:v1.4",
            ),
            budget=AIBudget(
                max_tokens=100,
                max_cost=1,
                max_duration_seconds=5,
            ),
        )

        loaded = runs.get(result.run_id)
        assert loaded == result

        row = connection.execute(
            """
            select count(*)
            from audit_log
            where action = %s and resource_id = %s
            """,
            ("ai.run", "identity:integration"),
        ).fetchone()
        assert row == (1,)

        connection.execute(
            "delete from ai_run where run_id = %s",
            ("run:integration",),
        )
        connection.execute(
            "delete from audit_log where action = %s and resource_id = %s",
            ("ai.run", "identity:integration"),
        )
        connection.commit()
