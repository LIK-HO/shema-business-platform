from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIGateway,
    AIProvider,
    AIRun,
    AITask,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.policy import PolicyEngine


@dataclass(frozen=True, slots=True)
class AIExecutionTrust:
    resource_trust_level: int
    evidence_level: int

    def __post_init__(self) -> None:
        if self.resource_trust_level < 0 or self.evidence_level < 0:
            raise ValueError("trust levels cannot be negative")


class AIExecutionTrustResolver(Protocol):
    def resolve(
        self,
        *,
        resource_ref: str,
        evidence_refs: tuple[str, ...],
    ) -> AIExecutionTrust: ...


@dataclass(frozen=True, slots=True)
class AIExecutionRequest:
    task_type: str
    prompt_version: str
    resource_ref: str
    input_refs: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    evidence_required: bool
    max_tokens: int
    max_cost: float
    max_duration_seconds: float
    actor_id: str
    actor_trust_level: int
    permissions: frozenset[Permission]
    correlation_id: str

    def __post_init__(self) -> None:
        if not self.task_type.strip() or not self.prompt_version.strip():
            raise ValueError("task_type and prompt_version are required")
        if not self.resource_ref.strip() or not self.actor_id.strip():
            raise ValueError("resource_ref and actor_id are required")
        if not self.correlation_id.strip():
            raise ValueError("correlation_id is required")
        if not self.input_refs or len(self.input_refs) > 64:
            raise ValueError("input_refs must contain 1..64 references")
        if not self.evidence_refs or len(self.evidence_refs) > 64:
            raise ValueError("evidence_refs must contain 1..64 references")
        if len(self.input_refs) != len(set(self.input_refs)):
            raise ValueError("input_refs must be unique")
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")
        if any(not ref.strip() for ref in self.input_refs + self.evidence_refs):
            raise ValueError("references cannot be empty")
        if self.actor_trust_level < 0:
            raise ValueError("actor_trust_level cannot be negative")


class AIExecutionService:
    """Application workflow over the frozen AI Gateway and provider composition."""

    def __init__(
        self,
        *,
        provider_factory: Callable[[], AIProvider],
        unit_of_work_factory: Callable[[], UnitOfWork],
        trust_resolver: AIExecutionTrustResolver,
        configuration_version_provider: Callable[[], str],
        policy: PolicyEngine | None = None,
        scoped_executor: Callable[..., AIRun] | None = None,
    ) -> None:
        self._provider_factory = provider_factory
        self._unit_of_work_factory = unit_of_work_factory
        self._trust_resolver = trust_resolver
        self._configuration_version_provider = configuration_version_provider
        self._policy = policy or PolicyEngine()
        self._scoped_executor = scoped_executor

    def execute(self, request: AIExecutionRequest) -> AIRun:
        trust = self._trust_resolver.resolve(
            resource_ref=request.resource_ref,
            evidence_refs=request.evidence_refs,
        )
        configuration_version = self._configuration_version_provider()
        if not configuration_version.strip():
            raise RuntimeError("AI provider configuration is not active")

        authorizer = RBACAuthorizer(
            (
                AuthorizationSubject(
                    actor_id=request.actor_id,
                    permissions=request.permissions,
                ),
            )
        )
        gateway = AIGateway(
            self._provider_factory(),
            authorizer,
            self._policy,
            self._unit_of_work_factory,
        )

        task = AITask(
            task_id=str(uuid4()),
            task_type=request.task_type,
            prompt_version=request.prompt_version,
            evidence_required=request.evidence_required,
        )
        budget = AIBudget(
            max_tokens=request.max_tokens,
            max_cost=request.max_cost,
            max_duration_seconds=request.max_duration_seconds,
        )
        context = AIExecutionContext(
            actor_id=request.actor_id,
            resource_ref=request.resource_ref,
            actor_trust_level=request.actor_trust_level,
            resource_trust_level=trust.resource_trust_level,
            evidence_level=trust.evidence_level,
            correlation_id=request.correlation_id,
            configuration_version=configuration_version,
        )
        if self._scoped_executor is None:
            raise RuntimeError("AI scoped executor is not configured")
        return self._scoped_executor(
            gateway,
            task,
            input_refs=request.input_refs,
            evidence_refs=request.evidence_refs,
            context=context,
            budget=budget,
        )
