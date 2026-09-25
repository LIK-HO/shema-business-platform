from dataclasses import dataclass, field

import pytest

from shema_platform.application.ai import AIRun
from shema_platform.application.ai_runtime import (
    AIExecutionRequest,
    AIExecutionService,
    AIExecutionTrust,
)
from shema_platform.application.ports import AIRunRepository
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.policy import PolicyEngine


@dataclass
class MemoryRuns(AIRunRepository):
    records: list[AIRun] = field(default_factory=list)

    def add(self, run: AIRun) -> None:
        self.records.append(run)

    def get(self, run_id: str) -> AIRun | None:
        return next((run for run in self.records if run.run_id == run_id), None)


@dataclass
class MemoryAudits:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


class MemoryUnitOfWork:
    def __init__(self) -> None:
        self.ai_runs = MemoryRuns()
        self.audits = MemoryAudits()

    def __enter__(self) -> "MemoryUnitOfWork":
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


class StaticTrustResolver:
    def resolve(self, *, resource_ref: str, evidence_refs: tuple[str, ...]) -> AIExecutionTrust:
        assert resource_ref == "identity-1"
        assert evidence_refs == ("evidence-1",)
        return AIExecutionTrust(resource_trust_level=2, evidence_level=2)


class FakeProvider:
    provider_id = "yandexgpt"

    def run(self, task, *, input_refs):
        return AIRun(
            run_id="run-1",
            task_id=task.task_id,
            provider_id=self.provider_id,
            model="gpt://folder/yandexgpt/latest",
            model_version="latest",
            prompt_version=task.prompt_version,
            input_refs=input_refs,
            evidence_refs=("evidence-1",),
            output="bounded output",
            tokens=10,
            cost=0.01,
            duration_seconds=0.1,
        )


def request(**overrides) -> AIExecutionRequest:
    values = {
        "task_type": "qualification",
        "prompt_version": "prompt:v1",
        "resource_ref": "identity-1",
        "input_refs": ("identity-1",),
        "evidence_refs": ("evidence-1",),
        "evidence_required": True,
        "max_tokens": 100,
        "max_cost": 1,
        "max_duration_seconds": 5,
        "actor_id": "operator-1",
        "actor_trust_level": 2,
        "permissions": frozenset({Permission.AI_RUN}),
        "correlation_id": "corr-1",
    }
    values.update(overrides)
    return AIExecutionRequest(**values)


def service(provider_factory=FakeProvider):
    return AIExecutionService(
        provider_factory=provider_factory,
        unit_of_work_factory=MemoryUnitOfWork,
        trust_resolver=StaticTrustResolver(),
        configuration_version_provider=lambda: "yandexgpt-config:v1",
        policy=PolicyEngine(),
        scoped_executor=_execute_scoped,
    )


def _execute_scoped(gateway, task, **kwargs):
    from shema_platform.adapters.ai.composition import execute_scoped_ai

    return execute_scoped_ai(gateway, task, **kwargs)


def test_ai_application_service_uses_server_trust_and_frozen_gateway() -> None:
    result = service().execute(request())

    assert result.provider_id == "yandexgpt"
    assert result.task_id
    assert result.evidence_refs == ("evidence-1",)


def test_ai_application_service_rejects_missing_ai_permission() -> None:
    with pytest.raises(Exception, match="permission denied"):
        service().execute(request(permissions=frozenset()))


def test_ai_application_request_rejects_duplicate_references() -> None:
    with pytest.raises(ValueError, match="input_refs must be unique"):
        request(input_refs=("identity-1", "identity-1"))


def test_ai_application_requires_active_configuration() -> None:
    instance = AIExecutionService(
        provider_factory=FakeProvider,
        unit_of_work_factory=MemoryUnitOfWork,
        trust_resolver=StaticTrustResolver(),
        configuration_version_provider=lambda: "",
        policy=PolicyEngine(),
        scoped_executor=_execute_scoped,
    )

    with pytest.raises(RuntimeError, match="configuration is not active"):
        instance.execute(request())


def test_ai_execution_trust_rejects_negative_levels() -> None:
    with pytest.raises(ValueError, match="trust levels cannot be negative"):
        AIExecutionTrust(resource_trust_level=-1, evidence_level=2)
