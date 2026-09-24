import json
import os
from dataclasses import replace
from pathlib import Path

import psycopg
import pytest

from shema_platform.adapters.ai.openai import OpenAIConfiguration, OpenAIProvider
from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIGateway,
    AITask,
)
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.platform.postgres import PostgresUnitOfWork
from shema_platform.platform.postgres_repositories import PostgresAIRunRepository

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


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


def test_openai_provider_runs_through_gateway_and_persists_to_postgres() -> None:
    calls: list[tuple[str, str, dict[str, str], bytes | None]] = []

    def requester(method, url, headers, body, timeout):
        calls.append((method, url, dict(headers), body))
        return (
            200,
            json.dumps(
                {
                    "id": "resp:p26:1",
                    "object": "response",
                    "status": "completed",
                    "model": "gpt-6-luna",
                    "output": [
                        {
                            "id": "msg:p26:1",
                            "type": "message",
                            "status": "completed",
                            "content": [
                                {
                                    "type": "output_text",
                                    "text": "qualified",
                                }
                            ],
                        }
                    ],
                    "usage": {
                        "input_tokens": 12,
                        "output_tokens": 8,
                        "total_tokens": 20,
                    },
                }
            ).encode(),
        )

    provider = OpenAIProvider(
        OpenAIConfiguration(
            api_key="runtime-secret",
            max_output_tokens=64,
            max_cost_usd_per_call=0.10,
        ),
        prompt_resolver=lambda task, refs: "Classify the supplied evidence.",
        evidence_resolver=lambda refs: ("evidence:p26",),
        requester=requester,
    )
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                "operator-1",
                frozenset({Permission.AI_RUN}),
            ),
        )
    )
    gateway = AIGateway(
        provider,
        authorizer,
        PolicyEngine(),
        lambda: PostgresUnitOfWork(
            lambda: psycopg.connect(DATABASE_URL),
        ),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migrations(connection)
        connection.commit()

        result = gateway.execute(
            AITask(
                "task:p26",
                "qualification",
                "prompt:v1",
                evidence_required=True,
            ),
            input_refs=("identity:p26",),
            evidence_refs=("evidence:p26",),
            context=AIExecutionContext(
                actor_id="operator-1",
                resource_ref="identity:p26",
                actor_trust_level=2,
                resource_trust_level=2,
                evidence_level=2,
                correlation_id="corr:p26",
                configuration_version="cfg:p26",
            ),
            budget=AIBudget(
                max_tokens=20,
                max_cost=0.10,
                max_duration_seconds=5,
            ),
        )

        loaded = PostgresAIRunRepository(connection).get(result.run_id)
        assert loaded is not None
        assert loaded == replace(
            result,
            duration_seconds=loaded.duration_seconds,
        )
        assert result.provider_id == "openai"
        assert result.output == "qualified"
        assert calls[0][0] == "POST"
        assert calls[0][1].endswith("/v1/responses")
        assert calls[0][2]["Authorization"] == "Bearer runtime-secret"

        audit = connection.execute(
            """
            select action, resource_id, outcome, correlation_id
            from audit_log
            where action = %s and resource_id = %s
            """,
            ("ai.run", "identity:p26"),
        ).fetchone()
        assert audit == ("ai.run", "identity:p26", "success", "corr:p26")

        connection.execute(
            "delete from ai_run where run_id = %s",
            (result.run_id,),
        )
        connection.execute(
            """
            delete from audit_log
            where action = %s and resource_id = %s
            """,
            ("ai.run", "identity:p26"),
        )
        connection.commit()
