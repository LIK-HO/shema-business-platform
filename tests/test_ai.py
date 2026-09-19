from dataclasses import dataclass, field

import pytest

from shema_platform.application.ai import (
    AIBudget,
    AIGateway,
    AIExecutionContext,
    AIProvider,
    AIRun,
    AITask,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import AuthorizationError


@dataclass
class MemoryAuditRepository:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass
class FakeAIProvider(AIProvider):
    provider_id: str = "fake"

    def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun:
        return AIRun(
            run_id="run-1",
            task_id=task.task_id,
            provider_id=self.provider_id,
            model="fake-model",
            model_version="1",
            prompt_version=task.prompt_version,
            input_refs=input_refs,
            evidence_refs=("evidence:1",),
            output="ok",
            tokens=12,
            cost=0.04,
            duration_seconds=0.2,
        )


def gateway() -> tuple[AIGateway, MemoryAuditRepository]:
    audit = MemoryAuditRepository()
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                actor_id="operator-1",
                permissions=frozenset({Permission.AI_RUN}),
            ),
        )
    )
    return AIGateway(FakeAIProvider(), authorizer, __import__(
        "shema_platform.foundation.policy",
        fromlist=["PolicyEngine"],
    ).PolicyEngine(), audit), audit


def context() -> AIExecutionContext:
    return AIExecutionContext(
        actor_id="operator-1",
        resource_ref="identity:1",
        actor_trust_level=2,
        resource_trust_level=2,
        evidence_level=2,
        correlation_id="corr-1",
        configuration_version="cfg:v1.4",
    )


def budget() -> AIBudget:
    return AIBudget(max_tokens=20, max_cost=0.10, max_duration_seconds=1)


def test_ai_gateway_requires_evidence_for_critical_task() -> None:
    gateway_instance, _ = gateway()
    task = AITask("task-1", "qualification", "prompt:v1", evidence_required=True)

    with pytest.raises(ValueError, match="evidence is required"):
        gateway_instance.execute(
            task,
            input_refs=("identity:1",),
            evidence_refs=(),
            context=context(),
            budget=budget(),
        )


def test_ai_gateway_validates_provider_result_and_audits_success() -> None:
    gateway_instance, audit = gateway()
    task = AITask("task-1", "qualification", "prompt:v1", evidence_required=True)

    run = gateway_instance.execute(
        task,
        input_refs=("identity:1",),
        evidence_refs=("evidence:1",),
        context=context(),
        budget=budget(),
    )

    assert run.task_id == task.task_id
    assert run.prompt_version == task.prompt_version
    assert run.tokens == 12
    assert len(audit.records) == 1
    assert audit.records[0].action == "ai.run"
    assert audit.records[0].outcome == "success"


def test_ai_gateway_rejects_unsupported_evidence_reference() -> None:
    class BadProvider(FakeAIProvider):
        def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun:
            result = super().run(task, input_refs=input_refs)
            return AIRun(
                run_id=result.run_id,
                task_id=result.task_id,
                provider_id=result.provider_id,
                model=result.model,
                model_version=result.model_version,
                prompt_version=result.prompt_version,
                input_refs=result.input_refs,
                evidence_refs=("evidence:outside",),
                output=result.output,
                tokens=result.tokens,
                cost=result.cost,
                duration_seconds=result.duration_seconds,
            )

    audit = MemoryAuditRepository()
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                "operator-1",
                frozenset({Permission.AI_RUN}),
            ),
        )
    )
    gateway_instance = AIGateway(
        BadProvider(),
        authorizer,
        __import__("shema_platform.foundation.policy", fromlist=["PolicyEngine"]).PolicyEngine(),
        audit,
    )

    with pytest.raises(ValueError, match="unsupported evidence"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )


def test_ai_gateway_requires_explicit_permission_before_provider() -> None:
    audit = MemoryAuditRepository()
    authorizer = RBACAuthorizer()
    gateway_instance = AIGateway(
        FakeAIProvider(),
        authorizer,
        __import__("shema_platform.foundation.policy", fromlist=["PolicyEngine"]).PolicyEngine(),
        audit,
    )

    with pytest.raises(AuthorizationError, match="permission denied"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )

    assert audit.records == []


def test_ai_gateway_enforces_budget() -> None:
    gateway_instance, audit = gateway()

    with pytest.raises(ValueError, match="token budget"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=AIBudget(max_tokens=10, max_cost=0.10, max_duration_seconds=1),
        )

    assert audit.records == []
