from __future__ import annotations

from contextlib import contextmanager
from contextvars import ContextVar, Token
from dataclasses import dataclass
from time import monotonic
from typing import Iterator

from shema_platform.adapters.ai.contracts import (
    AIProviderActivation,
    AIProviderAdapter,
    AIProviderFailure,
    AIProviderFailureCode,
    AIProviderReadinessState,
    AIProviderRequest,
    validate_provider_activation,
    validate_provider_response,
)
from shema_platform.application.ai import (
    AIBudget,
    AIExecutionContext,
    AIGateway,
    AIRun,
    AITask,
)
from shema_platform.foundation.telemetry import TelemetrySink, build_event


class AIProviderCompositionError(RuntimeError):
    """Fail-closed composition error at the frozen-gateway/provider boundary."""

    def __init__(self, failure: AIProviderFailure) -> None:
        super().__init__(failure.message)
        self.failure = failure


@dataclass(frozen=True, slots=True)
class AIExecutionScope:
    """Request-scoped data that the frozen AIGateway cannot pass into AIProvider.run."""

    evidence_refs: tuple[str, ...]
    context: AIExecutionContext
    budget: AIBudget
    deadline_seconds: float

    def __post_init__(self) -> None:
        correlation_id = self.context.correlation_id
        if not correlation_id or not correlation_id.strip():
            raise ValueError(
                "AI provider composition requires a correlation_id"
            )
        if self.deadline_seconds <= 0:
            raise ValueError("AI provider composition deadline must be positive")
        if (
            self.budget.max_duration_seconds <= 0
            or self.deadline_seconds > self.budget.max_duration_seconds
        ):
            raise ValueError(
                "AI provider composition deadline must fit the AI budget"
            )
        if len(self.evidence_refs) != len(set(self.evidence_refs)):
            raise ValueError("evidence_refs must be unique")



_CURRENT_SCOPE: ContextVar[AIExecutionScope | None] = ContextVar(
    "shema_ai_execution_scope",
    default=None,
)


@contextmanager
def bind_ai_execution_scope(
    *,
    evidence_refs: tuple[str, ...],
    context: AIExecutionContext,
    budget: AIBudget,
    deadline_seconds: float | None = None,
) -> Iterator[AIExecutionScope]:
    scope = AIExecutionScope(
        evidence_refs=tuple(evidence_refs),
        context=context,
        budget=budget,
        deadline_seconds=(
            budget.max_duration_seconds
            if deadline_seconds is None
            else deadline_seconds
        ),
    )
    token: Token[AIExecutionScope | None] = _CURRENT_SCOPE.set(scope)
    try:
        yield scope
    finally:
        _CURRENT_SCOPE.reset(token)


def current_ai_execution_scope() -> AIExecutionScope:
    scope = _CURRENT_SCOPE.get()
    if scope is None:
        raise AIProviderCompositionError(
            AIProviderFailure(
                code=AIProviderFailureCode.NOT_READY,
                message="AI provider invocation is outside a composition scope",
            )
        )
    return scope


def execute_scoped_ai(
    gateway: AIGateway,
    task: AITask,
    *,
    input_refs: tuple[str, ...],
    evidence_refs: tuple[str, ...],
    context: AIExecutionContext,
    budget: AIBudget,
    deadline_seconds: float | None = None,
) -> AIRun:
    with bind_ai_execution_scope(
        evidence_refs=evidence_refs,
        context=context,
        budget=budget,
        deadline_seconds=deadline_seconds,
    ):
        return gateway.execute(
            task,
            input_refs=input_refs,
            evidence_refs=evidence_refs,
            context=context,
            budget=budget,
        )


class ScopedAIProvider:
    """Frozen AIProvider facade over a P25 provider adapter."""

    def __init__(
        self,
        adapter: AIProviderAdapter,
        *,
        telemetry: TelemetrySink | None = None,
    ) -> None:
        self._adapter = adapter
        self._telemetry = telemetry
        self.provider_id = adapter.descriptor().provider_id
        validate_provider_activation(
            adapter.descriptor(),
            adapter.activation(),
        )

    def run(
        self,
        task: AITask,
        *,
        input_refs: tuple[str, ...],
    ) -> AIRun:
        scope = current_ai_execution_scope()
        started = monotonic()

        descriptor = self._adapter.descriptor()
        activation = self._adapter.activation()
        try:
            validate_provider_activation(descriptor, activation)
        except ValueError as exc:
            failure = AIProviderFailure(
                code=AIProviderFailureCode.POLICY_DENIED,
                message="AI provider activation policy rejected the provider",
            )
            self._emit_failure(task, scope, failure, started)
            raise AIProviderCompositionError(failure) from exc

        if not activation.enabled or not activation.explicit:
            failure = AIProviderFailure(
                code=AIProviderFailureCode.NOT_READY,
                message="AI provider activation is not explicitly enabled",
            )
            self._emit_failure(task, scope, failure, started)
            raise AIProviderCompositionError(failure)

        readiness = self._adapter.readiness()
        if readiness.state is not AIProviderReadinessState.READY:
            failure = AIProviderFailure(
                code=AIProviderFailureCode.NOT_READY,
                message=(
                    "AI provider is not ready"
                    if not readiness.error_code
                    else "AI provider readiness is blocked"
                ),
            )
            self._emit_failure(task, scope, failure, started)
            raise AIProviderCompositionError(failure)

        request = AIProviderRequest(
            operation_id=f"{scope.context.correlation_id}:{task.task_id}",
            task=task,
            input_refs=tuple(input_refs),
            evidence_refs=scope.evidence_refs,
            context=scope.context,
            budget=scope.budget,
            deadline_seconds=scope.deadline_seconds,
        )

        try:
            response = self._adapter.invoke(request)
            validate_provider_response(
                descriptor,
                request,
                response,
            )
        except AIProviderCompositionError:
            raise
        except Exception as exc:
            failure = getattr(exc, "failure", None)
            if not isinstance(failure, AIProviderFailure):
                failure = AIProviderFailure(
                    code=AIProviderFailureCode.TRANSPORT,
                    message="AI provider adapter execution failed",
                )
            self._emit_failure(task, scope, failure, started)
            raise AIProviderCompositionError(failure) from exc

        self._emit_success(task, scope, response.run, started)
        return response.run

    def _emit_success(
        self,
        task: AITask,
        scope: AIExecutionScope,
        run: AIRun,
        started: float,
    ) -> None:
        if self._telemetry is None:
            return
        try:
            self._telemetry.emit(
                build_event(
                    name="ai.provider.completed",
                    correlation_id=scope.context.correlation_id or "",
                    attributes={
                        "component": "ai.provider",
                        "operation": task.task_type,
                        "provider": run.provider_id,
                        "duration_ms": round((monotonic() - started) * 1000, 2),
                    },
                )
            )
        except Exception:
            return

    def _emit_failure(
        self,
        task: AITask,
        scope: AIExecutionScope,
        failure: AIProviderFailure,
        started: float,
    ) -> None:
        if self._telemetry is None:
            return
        try:
            self._telemetry.emit(
                build_event(
                    name="ai.provider.failed",
                    correlation_id=scope.context.correlation_id or "",
                    attributes={
                        "component": "ai.provider",
                        "operation": task.task_type,
                        "provider": self.provider_id,
                        "error_code": failure.code.value,
                        "duration_ms": round((monotonic() - started) * 1000, 2),
                    },
                )
            )
        except Exception:
            return
