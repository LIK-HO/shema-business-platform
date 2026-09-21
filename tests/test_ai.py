from dataclasses import dataclass, field
from typing import Callable

import pytest

from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIGateway,
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
from shema_platform.foundation.policy import PolicyEngine


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
    active: bool = False


class MemoryAIUnitOfWork:
    def __init__(self, state: MemoryAIState) -> None:
        self._state = state
        self.audits = state.audits
        self.ai_runs = state.runs

    def __enter__(self) -> "MemoryAIUnitOfWork":
        self._state.active = True
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        self._state.active = False
        return False


@dataclass
class FakeAIProvider(AIProvider):
    provider_id: str = "fake"
    transaction_probe: Callable[[], bool] | None = None

    def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun:
        if self.transaction_probe is not None and self.transaction_probe():
            raise AssertionError("AI provider call occurred inside Unit of Work")
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


def gateway(
    provider: AIProvider | None = None,
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
    gateway_instance = AIGateway(
        provider or FakeAIProvider(transaction_probe=lambda: state.active),
        authorizer,
        PolicyEngine(),
        lambda: MemoryAIUnitOfWork(state),
    )
    return gateway_instance, state


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
    gateway_instance, state = gateway()
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
    assert len(state.audits.records) == 1
    assert state.runs.records == [run]
    assert state.audits.records[0].action == "ai.run"
    assert state.audits.records[0].outcome == "success"


def test_ai_gateway_provider_call_is_outside_transaction() -> None:
    gateway_instance, state = gateway()

    run = gateway_instance.execute(
        AITask("task-1", "qualification", "prompt:v1"),
        input_refs=("identity:1",),
        evidence_refs=("evidence:1",),
        context=context(),
        budget=budget(),
    )

    assert state.active is False
    assert run.run_id == "run-1"


def test_ai_gateway_rejects_missing_evidence_in_provider_result() -> None:
    class MissingEvidenceProvider(FakeAIProvider):
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
                evidence_refs=(),
                output=result.output,
                tokens=result.tokens,
                cost=result.cost,
                duration_seconds=result.duration_seconds,
            )

    gateway_instance, state = gateway(
        MissingEvidenceProvider(transaction_probe=lambda: state.active)
    )

    with pytest.raises(ValueError, match="no evidence references"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1", evidence_required=True),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )

    assert state.audits.records == []


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

    gateway_instance, state = gateway(
        BadProvider(transaction_probe=lambda: state.active)
    )

    with pytest.raises(ValueError, match="unsupported evidence"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )

    assert state.audits.records == []


def test_ai_gateway_requires_explicit_permission_before_provider() -> None:
    state = MemoryAIState()
    authorizer = RBACAuthorizer()
    gateway_instance = AIGateway(
        FakeAIProvider(transaction_probe=lambda: state.active),
        authorizer,
        PolicyEngine(),
        lambda: MemoryAIUnitOfWork(state),
    )

    with pytest.raises(AuthorizationError, match="permission denied"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=budget(),
        )

    assert state.audits.records == []
    assert state.active is False


def test_ai_gateway_enforces_budget() -> None:
    gateway_instance, state = gateway()

    with pytest.raises(ValueError, match="token budget"):
        gateway_instance.execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
            context=context(),
            budget=AIBudget(
                max_tokens=10,
                max_cost=0.10,
                max_duration_seconds=1,
            ),
        )

    assert state.audits.records == []
