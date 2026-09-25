import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from shema_platform.adapters.ai import production_activation
from shema_platform.adapters.ai.contracts import (
    AIModelProvenance,
    AIProviderActivation,
    AIProviderDescriptor,
    AIProviderKind,
    AIProviderReadiness,
    AIProviderReadinessState,
    AIProviderRequest,
    AIProviderResourceLimits,
    AIProviderResponse,
)
from shema_platform.application.ai import AIRun
from shema_platform.experience.runtime_composition import compose_yandexgpt_runtime
from shema_platform.foundation.authentication import AuthenticatedActor, AuthenticationPort
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink
from shema_platform.platform.ai_trust import PostgresAIExecutionTrustResolver
from shema_platform.platform.migrations import MigrationPlan, MigrationRunner
from shema_platform.platform.postgres import PostgresUnitOfWork

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


class P32TestAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer p32-token":
            return AuthenticatedActor(
                "p32-operator",
                trust_level=2,
                permissions=frozenset({Permission.AI_RUN}),
            )
        raise RuntimeError("unexpected authentication")


class DeterministicYandexGPTProvider:
    provider_id = "yandexgpt"
    constructions = 0
    invocations = 0

    def __init__(self, configuration, *, prompt_renderer, cost_estimator) -> None:
        type(self).constructions += 1
        self._configuration = configuration
        self._prompt_renderer = prompt_renderer
        self._descriptor = AIProviderDescriptor(
            provider_id=self.provider_id,
            kind=AIProviderKind.CLOUD,
            model_id=configuration.model_uri,
            model_version="latest",
            configuration_version=configuration.configuration_version,
            capabilities=frozenset({"text_generation", "chat_completion"}),
            resource_limits=AIProviderResourceLimits(
                max_duration_seconds=configuration.timeout_seconds,
                max_response_bytes=configuration.max_response_bytes,
                max_input_chars=configuration.max_input_chars,
                max_output_tokens=configuration.max_output_tokens,
                max_calls=1,
                max_cost=configuration.max_cost,
            ),
            provenance=AIModelProvenance(
                source_ref="https://yandex.cloud/en/docs/overview/api",
                license_name="Yandex Cloud service terms",
                license_url="https://yandex.com/legal/cloud_termsofuse/en/",
                license_checked_at=None,
                artifact_digest=None,
                runtime="P32 deterministic transport",
                security_status="test-only",
                free_commercial_use_verified=False,
            ),
        )
        self._activation = AIProviderActivation(
            enabled=True,
            activation_version=configuration.activation_version,
            explicit=True,
            reason="P32 deterministic test transport",
        )

    def descriptor(self) -> AIProviderDescriptor:
        return self._descriptor

    def activation(self) -> AIProviderActivation:
        return self._activation

    def readiness(self) -> AIProviderReadiness:
        return AIProviderReadiness(
            provider_id=self.provider_id,
            state=AIProviderReadinessState.READY,
            checked_at=datetime.now(UTC),
        )

    def invoke(self, request: AIProviderRequest) -> AIProviderResponse:
        type(self).invocations += 1
        assert self._prompt_renderer(request) == "P32 deterministic prompt"

        run = AIRun(
            run_id=str(uuid4()),
            task_id=request.task.task_id,
            provider_id=self.provider_id,
            model=self._descriptor.model_id,
            model_version=self._descriptor.model_version,
            prompt_version=request.task.prompt_version,
            input_refs=request.input_refs,
            evidence_refs=request.evidence_refs,
            output=f"P32 deterministic result:{request.context.correlation_id}",
            tokens=12,
            cost=0.02,
            duration_seconds=0.01,
        )
        return AIProviderResponse(
            run=run,
            configuration_version=self._configuration.configuration_version,
            provenance_ref=f"p32:test:{run.run_id}",
            provider_request_id="p32-provider-request",
            observed_at=datetime.now(UTC),
        )


def apply_migrations() -> None:
    plan = MigrationPlan.from_directory(ROOT / "db/migrations")
    MigrationRunner(
        lambda: psycopg.connect(DATABASE_URL),
        plan,
    ).apply()


def snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p32-runtime:v1",
        environment="production",
        values={
            "ai.yandexgpt.model_uri": "gpt://p32/yandexgpt/latest",
            "ai.yandexgpt.base_url": "https://ai.example.test/v1",
            "ai.yandexgpt.timeout_seconds": 10,
            "ai.yandexgpt.max_response_bytes": 1_048_576,
            "ai.yandexgpt.max_input_chars": 32_768,
            "ai.yandexgpt.max_output_tokens": 100,
            "ai.yandexgpt.max_cost": 1,
            "ai.yandexgpt.configuration_version": "p32-yandexgpt-config:v1",
            "ai.yandexgpt.activation_version": "p32-yandexgpt-activation:v1",
        },
        feature_flags={"ai.yandexgpt.production.enabled": True},
    )


def insert_truth(identity_id: str, evidence_id: str) -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            insert into identity(identity_id, canonical_name, state)
            values (%s, %s, 'verified')
            """,
            (identity_id, "P32 integration identity"),
        )
        connection.execute(
            """
            insert into evidence(
                evidence_id, subject_ref, claim, source_ref, truth_class,
                trust_level, confidence, provenance, observed_at,
                captured_at, expires_at, lifecycle
            )
            values (
                %s, %s, %s, %s, 'evidence',
                'T2', 1.0, '{}'::jsonb, now(), now(), null, 'active'
            )
            """,
            (evidence_id, identity_id, "P32 verified evidence", "source:p32"),
        )
        connection.commit()


def cleanup_truth(
    identity_id: str,
    evidence_id: str,
    correlation_id: str,
    run_id: str | None,
) -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "delete from audit_log where correlation_id = %s",
            (correlation_id,),
        )
        if run_id is not None:
            connection.execute(
                "delete from ai_run where run_id = %s",
                (run_id,),
            )
        connection.execute(
            "delete from evidence where evidence_id = %s",
            (evidence_id,),
        )
        connection.execute(
            "delete from identity where identity_id = %s",
            (identity_id,),
        )
        connection.commit()


def build_assembly(telemetry: InMemoryTelemetrySink):
    return compose_yandexgpt_runtime(
        snapshot=snapshot(),
        telemetry=telemetry,
        unit_of_work_factory=lambda: PostgresUnitOfWork(
            lambda: psycopg.connect(DATABASE_URL)
        ),
        trust_resolver=PostgresAIExecutionTrustResolver(
            lambda: psycopg.connect(DATABASE_URL)
        ),
        prompt_renderer=lambda request: "P32 deterministic prompt",
        cost_estimator=lambda input_tokens, output_tokens: 0.02,
    )


def test_assembled_ai_path_persists_run_audit_and_correlation(monkeypatch) -> None:
    apply_migrations()
    identity_id = str(uuid4())
    evidence_id = str(uuid4())
    correlation_id = f"p32:{uuid4()}"
    run_id = None

    DeterministicYandexGPTProvider.constructions = 0
    DeterministicYandexGPTProvider.invocations = 0
    monkeypatch.setattr(
        production_activation,
        "YandexGPTProvider",
        DeterministicYandexGPTProvider,
    )

    insert_truth(identity_id, evidence_id)
    try:
        telemetry = InMemoryTelemetrySink()
        assembly = build_assembly(telemetry)

        assert assembly.ai.gate.state.enabled is False
        assert DeterministicYandexGPTProvider.constructions == 0

        assembly.activate_yandexgpt(
            activated_by="p32-operator",
            api_key="test-secret-not-sent",
        )

        assert assembly.ai.gate.state.enabled is True
        assert DeterministicYandexGPTProvider.constructions == 1

        client = TestClient(
            assembly.create_http_app(
                authenticator=P32TestAuthenticator(),
                telemetry=telemetry,
            )
        )
        response = client.post(
            "/v1/ai/run",
            headers={
                "Authorization": "Bearer p32-token",
                "X-Correlation-Id": correlation_id,
            },
            json={
                "taskType": "qualification",
                "promptVersion": "prompt:p32",
                "resourceRef": identity_id,
                "inputRefs": [identity_id],
                "evidenceRefs": [evidence_id],
                "maxTokens": 100,
                "maxCost": 0.50,
                "maxDurationSeconds": 5,
            },
        )

        assert response.status_code == 200
        body = response.json()
        run_id = body["runId"]
        assert body["providerId"] == "yandexgpt"
        assert body["output"] == f"P32 deterministic result:{correlation_id}"
        assert body["correlationId"] == correlation_id
        assert DeterministicYandexGPTProvider.invocations == 1
        assert response.headers["X-Correlation-Id"] == correlation_id

        with psycopg.connect(DATABASE_URL) as connection:
            ai_row = connection.execute(
                """
                select provider_id, model, prompt_version, output, tokens, cost
                from ai_run
                where run_id = %s
                """,
                (run_id,),
            ).fetchone()
            assert ai_row == (
                "yandexgpt",
                "gpt://p32/yandexgpt/latest",
                "prompt:p32",
                f"P32 deterministic result:{correlation_id}",
                12,
                0.02,
            )

            audit_rows = connection.execute(
                """
                select action, outcome, correlation_id, configuration_version
                from audit_log
                where correlation_id = %s
                  and action = 'ai.run'
                """,
                (correlation_id,),
            ).fetchall()
            assert audit_rows == [
                (
                    "ai.run",
                    "success",
                    correlation_id,
                    "p32-yandexgpt-config:v1",
                )
            ]
    finally:
        cleanup_truth(identity_id, evidence_id, correlation_id, run_id)


def test_assembled_ai_path_fails_closed_for_expired_evidence(monkeypatch) -> None:
    apply_migrations()
    identity_id = str(uuid4())
    evidence_id = str(uuid4())
    correlation_id = f"p32-expired:{uuid4()}"

    DeterministicYandexGPTProvider.constructions = 0
    DeterministicYandexGPTProvider.invocations = 0
    monkeypatch.setattr(
        production_activation,
        "YandexGPTProvider",
        DeterministicYandexGPTProvider,
    )

    insert_truth(identity_id, evidence_id)
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            "update evidence set expires_at = now() - interval '1 second' "
            "where evidence_id = %s",
            (evidence_id,),
        )
        connection.commit()

    try:
        assembly = build_assembly(InMemoryTelemetrySink())
        assembly.activate_yandexgpt(
            activated_by="p32-operator",
            api_key="test-secret-not-sent",
        )

        client = TestClient(
            assembly.create_http_app(authenticator=TestAuthenticator())
        )
        response = client.post(
            "/v1/ai/run",
            headers={
                "Authorization": "Bearer p32-token",
                "X-Correlation-Id": correlation_id,
            },
            json={
                "taskType": "qualification",
                "promptVersion": "prompt:p32",
                "resourceRef": identity_id,
                "inputRefs": [identity_id],
                "evidenceRefs": [evidence_id],
                "maxTokens": 100,
                "maxCost": 0.50,
                "maxDurationSeconds": 5,
            },
        )

        assert response.status_code == 423
        assert response.json()["code"] == "review_required"
        assert DeterministicYandexGPTProvider.invocations == 0
    finally:
        cleanup_truth(identity_id, evidence_id, correlation_id, None)
