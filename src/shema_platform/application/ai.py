from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from datetime import UTC, datetime
from typing import Protocol
from uuid import uuid4

from shema_platform.application.ports import AuditRepository
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import PolicyDenied
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


@dataclass(frozen=True, slots=True)
class AITask:
    task_id: str
    task_type: str
    prompt_version: str
    evidence_required: bool = True

    def __post_init__(self) -> None:
        if not self.task_id.strip() or not self.task_type.strip():
            raise ValueError("task_id and task_type are required")
        if not self.prompt_version.strip():
            raise ValueError("prompt_version is required")


@dataclass(frozen=True, slots=True)
class AIBudget:
    max_tokens: int
    max_cost: float
    max_duration_seconds: float

    def __post_init__(self) -> None:
        if self.max_tokens < 0:
            raise ValueError("max_tokens cannot be negative")
        if (
            not isfinite(self.max_cost)
            or not isfinite(self.max_duration_seconds)
            or self.max_cost < 0
            or self.max_duration_seconds < 0
        ):
            raise ValueError("AI budget values must be finite and non-negative")


@dataclass(frozen=True, slots=True)
class AIExecutionContext:
    actor_id: str
    resource_ref: str
    actor_trust_level: int
    resource_trust_level: int
    evidence_level: int
    correlation_id: str | None = None
    configuration_version: str | None = None

    def __post_init__(self) -> None:
        if not self.actor_id.strip() or not self.resource_ref.strip():
            raise ValueError("actor_id and resource_ref are required")
        if min(
            self.actor_trust_level,
            self.resource_trust_level,
            self.evidence_level,
        ) < 0:
            raise ValueError("trust and evidence levels cannot be negative")


@dataclass(frozen=True, slots=True)
class AIRun:
    run_id: str
    task_id: str
    provider_id: str
    model: str
    model_version: str
    prompt_version: str
    input_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    output: str
    tokens: int
    cost: float
    duration_seconds: float


class AIProvider(Protocol):
    provider_id: str

    def run(self, task: AITask, *, input_refs: tuple[str, ...]) -> AIRun: ...


class AIGateway:
    """AI boundary: authorization, policy, evidence, budget and audit precede release of a run."""

    def __init__(
        self,
        provider: AIProvider,
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
        audit_repository: AuditRepository,
    ) -> None:
        self._provider = provider
        self._authorizer = authorizer
        self._policy = policy
        self._audit = audit_repository

    def execute(
        self,
        task: AITask,
        *,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
        context: AIExecutionContext,
        budget: AIBudget,
    ) -> AIRun:
        self._authorizer.require(context.actor_id, Permission.AI_RUN)

        if task.evidence_required and not evidence_refs:
            raise ValueError("evidence is required for this AI task")

        decision = self._policy.evaluate(
            PolicyContext(
                actor_id=context.actor_id,
                action="ai_run",
                resource_type="ai_task",
                resource_id=context.resource_ref,
                actor_trust_level=context.actor_trust_level,
                resource_trust_level=context.resource_trust_level,
                evidence_level=context.evidence_level,
                evidence_required=task.evidence_required,
            )
        )
        if decision.decision is not Decision.ALLOW:
            raise PolicyDenied(decision.reason)

        run = self._provider.run(task, input_refs=input_refs)

        if run.provider_id != self._provider.provider_id:
            raise ValueError("AI provider returned mismatched provider_id")
        if run.task_id != task.task_id:
            raise ValueError("AI provider returned mismatched task_id")
        if run.prompt_version != task.prompt_version:
            raise ValueError("AI provider returned mismatched prompt_version")
        if tuple(run.input_refs) != tuple(input_refs):
            raise ValueError("AI provider returned mismatched input references")
        if task.evidence_required and not set(run.evidence_refs).issubset(evidence_refs):
            raise ValueError("AI provider returned unsupported evidence references")
        if run.tokens < 0 or run.cost < 0 or run.duration_seconds < 0:
            raise ValueError("AI provider returned invalid usage metrics")
        if run.tokens > budget.max_tokens:
            raise ValueError("AI provider exceeded token budget")
        if run.cost > budget.max_cost:
            raise ValueError("AI provider exceeded cost budget")
        if run.duration_seconds > budget.max_duration_seconds:
            raise ValueError("AI provider exceeded duration budget")

        self._audit.append(
            AuditRecord(
                audit_id=str(uuid4()),
                actor_id=context.actor_id,
                action="ai.run",
                resource_type="ai_task",
                resource_id=context.resource_ref,
                outcome="success",
                occurred_at=datetime.now(UTC),
                metadata={
                    "task_id": task.task_id,
                    "provider_id": run.provider_id,
                    "model": run.model,
                    "model_version": run.model_version,
                    "prompt_version": run.prompt_version,
                    "tokens": run.tokens,
                    "cost": run.cost,
                    "duration_seconds": run.duration_seconds,
                    "input_ref_count": len(run.input_refs),
                    "evidence_ref_count": len(run.evidence_refs),
                },
                correlation_id=context.correlation_id,
                configuration_version=context.configuration_version,
            )
        )
        return run

