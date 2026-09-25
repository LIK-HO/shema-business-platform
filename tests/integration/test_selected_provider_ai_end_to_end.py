import os
from datetime import UTC, datetime
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest
from fastapi.testclient import TestClient

from shema_platform.adapters.ai import gigachat_activation, production_activation
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
from shema_platform.experience.approved_ai_runtime import compose_approved_ai_runtime
from shema_platform.experience.gigachat_runtime_composition import (
    compose_gigachat_runtime,
)
from shema_platform.experience.runtime_composition import (
    compose_yandexgpt_runtime,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
)
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


class P37TestAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer p37-token":
            return AuthenticatedActor(
                "p37-operator",
                trust_level=2,
                permissions=frozenset({Permission.AI_RUN}),
            )
        raise RuntimeError("unexpected authentication")


class DeterministicAIProvider:
    constructions = 0
    invocations = 0
    provider_id = ""
    output_prefix = ""
    runtime = "P37 deterministic transport"

    def __init__(self, configuration, *, prompt_renderer, cost_estimator, **_) -> None:
        type(self).constructions += 1
        self._configuration = configuration
        self._prompt_renderer = prompt_renderer
        self._cost_estimator = cost_estimator
        self._model = (
            getattr(configuration, "model_uri", None)
            or getattr(configuration, "model", None)
        )
        self._descriptor = AIProviderDescriptor(
            provider_id=self.provider_id,
            kind=AIProviderKind.CLOUD,
            model_id=self._model,
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
                source_ref="https://example.test/p37",
                license_name="P37 deterministic test transport",
                license_url="https://example.test/p37/license",
                license_checked_at=None,
                artifact_digest=None,
                runtime=self.runtime,
                security_status="test-only",
                free_commercial_use_verified=False,
            ),
        )
        self._activation = AIProviderActivation(
            enabled=True,
            activation_version=configuration.activation_version,
            explicit=True,
            reason="P37 deterministic test transport",
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
        assert self._prompt_renderer(request) == "P37 deterministic prompt"
        run = AIRun(
            run_id=str(uuid4()),
            task_id=request.task.task_id,
            provider_id=self.provider_id,
            model=self._descriptor.model_id,
            model_version="latest",
            prompt_version=request.task.prompt_version,
            input_refs=request.input_refs,
            evidence_refs=request.evidence_refs,
            output=f"{self.output_prefix}{request.context.correlation_id}",
            tokens=12,
            cost=self._cost_estimator(8, 4),
            duration_seconds=0.01,
        )
        return AIProviderResponse(
            run=run,
            configuration_version=self._configuration.configuration_version,
            provenance_ref=f"p37:test:{run.run_id}",
            provider_request_id=f"p37-{self.provider_id}-request",
            observed_at=datetime.now(UTC),
        )


class DeterministicYandexGPTProvider(DeterministicAIProvider):
    provider_id = "yandexgpt"
    output_prefix = "P37 yandex result:"


class DeterministicGigaChatProvider(DeterministicAIProvider):
    provider_id = "gigachat"
    output_prefix = "P37 gigachat result:"


def apply_migrations() -> None:
    plan = MigrationPlan.from_directory(ROOT / "db/migrations")
    MigrationRunner(
        lambda: psycopg.connect(DATABASE_URL),
        plan,
    ).apply()


def yandex_snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p37-yandex-runtime:v1",
        environment="production",
        values={
            "ai.yandexgpt.model_uri": "gpt://p37/yandexgpt/latest",
            "ai.yandexgpt.base_url": "https://ai.example.test/v1",
            "ai.yandexgpt.timeout_seconds": 10,
            "ai.yandexgpt.max_response_bytes": 1_048_576,
            "ai.yandexgpt.max_input_chars": 32_768,
            "ai.yandexgpt.max_output_tokens": 100,
            "ai.yandexgpt.max_cost": 1,
            "ai.yandexgpt.configuration_version": "p37-yandex-config:v1",
            "ai.yandexgpt.activation_version": "p37-yandex-activation:v1",
        },
        feature_flags={"ai.yandexgpt.production.enabled": True},
    )


def gigachat_snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p37-gigachat-runtime:v1",
        environment="production",
        values={
            "ai.gigachat.model": "GigaChat-2-Max",
            "ai.gigachat.scope": "GIGACHAT_API_B2B",
            "ai.gigachat.base_url": "https://api.giga.chat/v1",
            "ai.gigachat.token_url": (
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
            ),
            "ai.gigachat.timeout_seconds": 10,
            "ai.gigachat.max_response_bytes": 1_048_576,
            "ai.gigachat.max_input_chars": 32_768,
            "ai.gigachat.max_output_tokens": 100,
            "ai.gigachat.max_cost": 1,
            "ai.gigachat.configuration_version": "p37-gigachat-config:v1",
            "ai.gigachat.activation_version": "p37-gigachat-activation:v1",
        },
        feature_flags={"ai.gigachat.production.enabled": True},
    )


def build_runtimes(telemetry: InMemoryTelemetrySink):
    yandex = compose_yandexgpt_runtime(
        snapshot=yandex_snapshot(),
        telemetry=telemetry,
        unit_of_work_factory=lambda: PostgresUnitOfWork(
            lambda: psycopg.connect(DATABASE_URL)
        ),
        trust_resolver=PostgresAIExecutionTrustResolver(
            lambda: psycopg.connect(DATABASE_URL)
        ),
        prompt_renderer=lambda request: "P37 deterministic prompt",
        cost_estimator=lambda input_tokens, output_tokens: 0.02,
    )
    gigachat = compose_gigachat_runtime(
        snapshot=gigachat_snapshot(),
        telemetry=telemetry,
        unit_of_work_factory=lambda: PostgresUnitOfWork(
            lambda: psycopg.connect(DATABASE_URL)
        ),
        trust_resolver=PostgresAIExecutionTrustResolver(
            lambda: psycopg.connect(DATABASE_URL)
        ),
        prompt_renderer=lambda request: "P37 deterministic prompt",
        cost_estimator=lambda input_tokens, output_tokens: 0.02,
    )
    return yandex, gigachat


def insert_truth(identity_id: str, evidence_id: str) -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        connection.execute(
            """
            insert into identity(identity_id, canonical_name, state)
            values (%s, %s, 'verified')
            """,
            (identity_id, "P37 integration identity"),
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
            (
                evidence_id,
                identity_id,
                "P37 verified evidence",
                "source:p37",
            ),
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


def execute_selected_provider(
    *,
    provider_id: str,
    identity_id: str,
    evidence_id: str,
    correlation_id: str,
    telemetry: InMemoryTelemetrySink,
    yandex,
    gigachat,
):
    selected = compose_approved_ai_runtime(
        provider_id=provider_id,
        yandexgpt=yandex,
        gigachat=gigachat,
    )

    if provider_id == "yandexgpt":
        yandex.activate_yandexgpt(
            activated_by="p37-operator",
            api_key="test-secret-not-sent",
        )
    else:
        gigachat.activate_gigachat(
            activated_by="p37-operator",
            authorization_key="test-secret-not-sent",
            requester=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("deterministic generation provider must avoid HTTP")
            ),
            token_requester=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("deterministic generation provider must avoid HTTP")
            ),
        )

    client = TestClient(
        selected.create_http_app(
            authenticator=P37TestAuthenticator(),
            telemetry=telemetry,
        )
    )
    response = client.post(
        "/v1/ai/run",
        headers={
            "Authorization": "Bearer p37-token",
            "X-Correlation-Id": correlation_id,
        },
        json={
            "taskType": "qualification",
            "promptVersion": "prompt:p37",
            "resourceRef": identity_id,
            "inputRefs": [identity_id],
            "evidenceRefs": [evidence_id],
            "maxTokens": 100,
            "maxCost": 0.50,
            "maxDurationSeconds": 5,
        },
    )
    return selected, response


def test_yandex_selected_runtime_executes_end_to_end(monkeypatch) -> None:
    apply_migrations()
    identity_id = str(uuid4())
    evidence_id = str(uuid4())
    correlation_id = f"p37-yandex:{uuid4()}"
    run_id = None

    DeterministicYandexGPTProvider.constructions = 0
    DeterministicYandexGPTProvider.invocations = 0
    DeterministicGigaChatProvider.constructions = 0
    DeterministicGigaChatProvider.invocations = 0
    monkeypatch.setattr(
        production_activation,
        "YandexGPTProvider",
        DeterministicYandexGPTProvider,
    )
    monkeypatch.setattr(
        gigachat_activation,
        "GigaChatProvider",
        DeterministicGigaChatProvider,
    )

    insert_truth(identity_id, evidence_id)
    try:
        telemetry = InMemoryTelemetrySink()
        yandex, gigachat = build_runtimes(telemetry)
        selected, response = execute_selected_provider(
            provider_id="yandexgpt",
            identity_id=identity_id,
            evidence_id=evidence_id,
            correlation_id=correlation_id,
            telemetry=telemetry,
            yandex=yandex,
            gigachat=gigachat,
        )

        assert selected.provider_id == "yandexgpt"
        assert response.status_code == 200
        body = response.json()
        run_id = body["runId"]
        assert body["providerId"] == "yandexgpt"
        assert body["output"] == f"P37 yandex result:{correlation_id}"
        assert body["correlationId"] == correlation_id
        assert DeterministicYandexGPTProvider.invocations == 1
        assert DeterministicGigaChatProvider.invocations == 0
        assert yandex.ai.gate.state.enabled is True
        assert gigachat.ai.gate.state.enabled is False

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
                "gpt://p37/yandexgpt/latest",
                "prompt:p37",
                f"P37 yandex result:{correlation_id}",
                12,
                Decimal("0.02000000"),
            )
    finally:
        cleanup_truth(identity_id, evidence_id, correlation_id, run_id)


def test_gigachat_selected_runtime_executes_end_to_end(monkeypatch) -> None:
    apply_migrations()
    identity_id = str(uuid4())
    evidence_id = str(uuid4())
    correlation_id = f"p37-gigachat:{uuid4()}"
    run_id = None

    DeterministicYandexGPTProvider.constructions = 0
    DeterministicYandexGPTProvider.invocations = 0
    DeterministicGigaChatProvider.constructions = 0
    DeterministicGigaChatProvider.invocations = 0
    monkeypatch.setattr(
        production_activation,
        "YandexGPTProvider",
        DeterministicYandexGPTProvider,
    )
    monkeypatch.setattr(
        gigachat_activation,
        "GigaChatProvider",
        DeterministicGigaChatProvider,
    )

    insert_truth(identity_id, evidence_id)
    try:
        telemetry = InMemoryTelemetrySink()
        yandex, gigachat = build_runtimes(telemetry)
        selected, response = execute_selected_provider(
            provider_id="gigachat",
            identity_id=identity_id,
            evidence_id=evidence_id,
            correlation_id=correlation_id,
            telemetry=telemetry,
            yandex=yandex,
            gigachat=gigachat,
        )

        assert selected.provider_id == "gigachat"
        assert response.status_code == 200
        body = response.json()
        run_id = body["runId"]
        assert body["providerId"] == "gigachat"
        assert body["output"] == f"P37 gigachat result:{correlation_id}"
        assert body["correlationId"] == correlation_id
        assert DeterministicGigaChatProvider.invocations == 1
        assert DeterministicYandexGPTProvider.invocations == 0
        assert gigachat.ai.gate.state.enabled is True
        assert yandex.ai.gate.state.enabled is False

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
                "gigachat",
                "GigaChat-2-Max",
                "prompt:p37",
                f"P37 gigachat result:{correlation_id}",
                12,
                Decimal("0.02000000"),
            )
    finally:
        cleanup_truth(identity_id, evidence_id, correlation_id, run_id)


def test_selected_provider_fails_closed_when_not_activated(monkeypatch) -> None:
    apply_migrations()
    identity_id = str(uuid4())
    evidence_id = str(uuid4())
    correlation_id = f"p37-inactive:{uuid4()}"

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
        yandex, gigachat = build_runtimes(telemetry)
        selected = compose_approved_ai_runtime(
            provider_id="yandexgpt",
            yandexgpt=yandex,
            gigachat=gigachat,
        )
        client = TestClient(
            selected.create_http_app(
                authenticator=P37TestAuthenticator(),
                telemetry=telemetry,
            )
        )
        response = client.post(
            "/v1/ai/run",
            headers={
                "Authorization": "Bearer p37-token",
                "X-Correlation-Id": correlation_id,
            },
            json={
                "taskType": "qualification",
                "promptVersion": "prompt:p37",
                "resourceRef": identity_id,
                "inputRefs": [identity_id],
                "evidenceRefs": [evidence_id],
                "maxTokens": 100,
                "maxCost": 0.50,
                "maxDurationSeconds": 5,
            },
        )

        assert response.status_code == 503
        assert response.json()["code"] == "ai_provider_unavailable"
        assert DeterministicYandexGPTProvider.invocations == 0
    finally:
        cleanup_truth(identity_id, evidence_id, correlation_id, None)


def test_selected_provider_fails_closed_for_expired_evidence(monkeypatch) -> None:
    apply_migrations()
    identity_id = str(uuid4())
    evidence_id = str(uuid4())
    correlation_id = f"p37-expired:{uuid4()}"

    DeterministicGigaChatProvider.constructions = 0
    DeterministicGigaChatProvider.invocations = 0
    monkeypatch.setattr(
        gigachat_activation,
        "GigaChatProvider",
        DeterministicGigaChatProvider,
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
        telemetry = InMemoryTelemetrySink()
        yandex, gigachat = build_runtimes(telemetry)
        selected = compose_approved_ai_runtime(
            provider_id="gigachat",
            yandexgpt=yandex,
            gigachat=gigachat,
        )
        gigachat.activate_gigachat(
            activated_by="p37-operator",
            authorization_key="test-secret-not-sent",
            requester=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("deterministic transport must avoid HTTP")
            ),
            token_requester=lambda *args, **kwargs: (_ for _ in ()).throw(
                AssertionError("deterministic transport must avoid HTTP")
            ),
        )
        client = TestClient(
            selected.create_http_app(
                authenticator=P37TestAuthenticator(),
                telemetry=telemetry,
            )
        )
        response = client.post(
            "/v1/ai/run",
            headers={
                "Authorization": "Bearer p37-token",
                "X-Correlation-Id": correlation_id,
            },
            json={
                "taskType": "qualification",
                "promptVersion": "prompt:p37",
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
        assert DeterministicGigaChatProvider.invocations == 0
    finally:
        cleanup_truth(identity_id, evidence_id, correlation_id, None)
