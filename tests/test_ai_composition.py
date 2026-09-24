from __future__ import annotations

import json
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from datetime import UTC, datetime

import pytest

from shema_platform.adapters.ai.composition import (
    AIProviderCompositionError,
    ScopedAIProvider,
    bind_ai_execution_scope,
    current_ai_execution_scope,
    execute_scoped_ai,
)
from shema_platform.adapters.ai.contracts import (
    AIModelProvenance,
    AIProviderActivation,
    AIProviderDescriptor,
    AIProviderFailureCode,
    AIProviderKind,
    AIProviderReadiness,
    AIProviderReadinessState,
    AIProviderRequest,
    AIProviderResourceLimits,
    AIProviderResponse,
)
from shema_platform.adapters.ai.yandexgpt import (
    YandexGPTConfiguration,
    YandexGPTProvider,
)
from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIGateway,
    AIRun,
    AITask,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


@dataclass
class MemoryAIRunRepository:
    records: list[AIRun] = field(default_factory=list)

    def add(self, run: AIRun) -> None:
        self.records.append(run)

    def get(self, run_id: str) -> AIRun | None:
        return next((run for run in self.records if run.run_id == run_id), None)


@dataclass
class MemoryAuditRepository:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass
class MemoryAIState:
    audits: MemoryAuditRepository = field(default_factory=MemoryAuditRepository)
    runs: MemoryAIRunRepository = field(default_factory=MemoryAIRunRepository)


class MemoryAIUnitOfWork:
    def __init__(self, state: MemoryAIState) -> None:
        self.audits = state.audits
        self.ai_runs = state.runs

    def __enter__(self) -> MemoryAIUnitOfWork:
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


def context(correlation_id: str | None = "corr-1") -> AIExecutionContext:
    return AIExecutionContext(
        actor_id="operator-1",
        resource_ref="identity:1",
        actor_trust_level=2,
        resource_trust_level=2,
        evidence_level=2,
        correlation_id=correlation_id,
        configuration_version="cfg:v1.5",
    )


def budget() -> AIBudget:
    return AIBudget(
        max_tokens=100,
        max_cost=1,
        max_duration_seconds=5,
    )


def task() -> AITask:
    return AITask(
        task_id="task:qualification:1",
        task_type="qualification",
        prompt_version="prompt:v1",
        evidence_required=True,
    )


def configuration() -> YandexGPTConfiguration:
    return YandexGPTConfiguration(
        api_key="scope-test-secret",
        model_uri="gpt://folder/yandexgpt/latest",
        max_response_bytes=1_048_576,
        max_input_chars=1_000,
        max_output_tokens=100,
        max_cost=1,
    )


def response_body() -> bytes:
    return json.dumps(
        {
            "id": "resp:scope-1",
            "choices": [
                {"message": {"content": "bounded output"}},
            ],
            "usage": {
                "prompt_tokens": 10,
                "completion_tokens": 5,
                "total_tokens": 15,
            },
        }
    ).encode("utf-8")


def requester(*args: object, **kwargs: object) -> tuple[int, bytes]:
    return 200, response_body()


def build_gateway(
    *,
    provider,
    telemetry: InMemoryTelemetrySink | None = None,
) -> tuple[AIGateway, MemoryAIState]:
    state = MemoryAIState()
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                actor_id="operator-1",
                permissions=frozenset({Permission.AI_RUN}),
            ),
        )
    )
    scoped = ScopedAIProvider(provider, telemetry=telemetry)
    return (
        AIGateway(
            scoped,
            authorizer,
            PolicyEngine(),
            lambda: MemoryAIUnitOfWork(state),
        ),
        state,
    )


def yandex_provider(
    *,
    requester_fn=requester,
) -> YandexGPTProvider:
    return YandexGPTProvider(
        configuration(),
        prompt_renderer=lambda _: "Classify the evidence conservatively.",
        cost_estimator=lambda input_tokens, output_tokens: (
            (input_tokens + output_tokens) * 0.01
        ),
        requester=requester_fn,
    )


def test_scoped_yandex_passes_frozen_gateway_and_audits_without_scope_leak() -> None:
    telemetry = InMemoryTelemetrySink()
    provider = yandex_provider()
    gateway, state = build_gateway(provider=provider, telemetry=telemetry)

    run = execute_scoped_ai(
        gateway,
        task(),
        input_refs=("identity:1",),
        evidence_refs=("evidence:1",),
        context=context(),
        budget=budget(),
    )

    assert run.provider_id == "yandexgpt"
    assert run.task_id == "task:qualification:1"
    assert state.runs.records == [run]
    assert len(state.audits.records) == 1
    assert state.audits.records[0].correlation_id == "corr-1"
    events = telemetry.all()
    assert len(events) == 1
    assert events[0].name == "ai.provider.completed"
    assert events[0].correlation_id == "corr-1"
    assert events[0].attributes["provider"] == "yandexgpt"

    with pytest.raises(AIProviderCompositionError, match="outside a composition scope"):
        current_ai_execution_scope()


def test_direct_provider_call_fails_closed_without_scope_before_network() -> None:
    called = False

    def forbidden_requester(*args: object, **kwargs: object) -> tuple[int, bytes]:
        nonlocal called
        called = True
        raise AssertionError("external provider I/O must not happen")

    scoped = ScopedAIProvider(
        yandex_provider(requester_fn=forbidden_requester),
    )

    with pytest.raises(AIProviderCompositionError, match="outside a composition scope"):
        scoped.run(task(), input_refs=("identity:1",))

    assert called is False


def test_missing_correlation_id_is_rejected_before_scope_binding() -> None:
    provider = yandex_provider()
    gateway, _ = build_gateway(provider=provider)

    with pytest.raises(ValueError, match="correlation_id"):
        execute_scoped_ai(
            gateway,
            task(),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(correlation_id=None),
            budget=budget(),
        )


def test_failed_provider_call_resets_scope_and_emits_typed_failure() -> None:
    telemetry = InMemoryTelemetrySink()

    def failing_requester(*args: object, **kwargs: object) -> tuple[int, bytes]:
        return 401, b"{}"

    provider = yandex_provider(requester_fn=failing_requester)
    gateway, _ = build_gateway(provider=provider, telemetry=telemetry)

    with pytest.raises(AIProviderCompositionError) as exc:
        execute_scoped_ai(
            gateway,
            task(),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )

    assert exc.value.failure.code is AIProviderFailureCode.AUTHENTICATION
    assert provider.readiness().state is AIProviderReadinessState.UNHEALTHY
    assert telemetry.all()[0].name == "ai.provider.failed"

    with pytest.raises(AIProviderCompositionError, match="outside a composition scope"):
        current_ai_execution_scope()


def test_scope_isolation_and_restore_across_threads() -> None:
    def worker(correlation_id: str) -> tuple[str, str]:
        with bind_ai_execution_scope(
            evidence_refs=("evidence:1",),
            context=context(correlation_id=correlation_id),
            budget=budget(),
        ) as scope:
            return (
                current_ai_execution_scope().context.correlation_id or "",
                scope.context.resource_ref,
            )

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = tuple(
            executor.map(worker, ("corr-a", "corr-b"))
        )

    assert results[0][0] == "corr-a"
    assert results[1][0] == "corr-b"
    assert results[0][1] != results[1][1]

    with pytest.raises(AIProviderCompositionError):
        current_ai_execution_scope()


def test_nested_scope_restores_outer_context() -> None:
    outer_context = context("corr-outer")
    inner_context = context("corr-inner")

    with bind_ai_execution_scope(
        evidence_refs=("evidence:outer",),
        context=outer_context,
        budget=budget(),
    ):
        assert current_ai_execution_scope().context.correlation_id == "corr-outer"

        with bind_ai_execution_scope(
            evidence_refs=("evidence:inner",),
            context=inner_context,
            budget=budget(),
        ):
            assert current_ai_execution_scope().context.correlation_id == "corr-inner"

        assert current_ai_execution_scope().context.correlation_id == "corr-outer"


@dataclass(frozen=True)
class DisabledAdapter:
    descriptor_value: AIProviderDescriptor

    @property
    def provider_id(self) -> str:
        return self.descriptor_value.provider_id

    def descriptor(self) -> AIProviderDescriptor:
        return self.descriptor_value

    def activation(self) -> AIProviderActivation:
        return AIProviderActivation(
            enabled=False,
            activation_version="disabled:v1",
            explicit=True,
            reason="test disabled provider",
        )

    def readiness(self) -> AIProviderReadiness:
        return AIProviderReadiness(
            provider_id=self.provider_id,
            state=AIProviderReadinessState.DISABLED,
            checked_at=datetime.now(UTC),
        )

    def invoke(self, request: AIProviderRequest) -> AIProviderResponse:
        raise AssertionError("disabled provider must not be invoked")


def test_disabled_provider_never_reaches_adapter_invoke() -> None:
    provenance = AIModelProvenance(
        source_ref="https://example.test/provider",
        license_name="Example",
        license_url="https://example.test/license",
        license_checked_at=None,
        artifact_digest=None,
        runtime="test",
        security_status="verified",
        free_commercial_use_verified=False,
    )
    adapter = DisabledAdapter(
        descriptor_value=AIProviderDescriptor(
            provider_id="yandexgpt",
            kind=AIProviderKind.CLOUD,
            model_id="model",
            model_version="1",
            configuration_version="cfg:1",
            capabilities=frozenset({"text_generation"}),
            resource_limits=AIProviderResourceLimits(
                max_duration_seconds=5,
                max_response_bytes=1024,
                max_input_chars=1024,
                max_output_tokens=100,
                max_calls=1,
                max_cost=1,
            ),
            provenance=provenance,
        )
    )

    gateway, _ = build_gateway(provider=adapter)

    with pytest.raises(AIProviderCompositionError, match="activation"):
        execute_scoped_ai(
            gateway,
            task(),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )
