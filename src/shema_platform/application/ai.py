from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True, slots=True)
class AITask:
    task_id: str
    task_type: str
    prompt_version: str
    evidence_required: bool = True


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
    """AI execution boundary. Domain code never calls a model provider directly."""

    def __init__(self, provider: AIProvider) -> None:
        self._provider = provider

    def execute(
        self,
        task: AITask,
        *,
        input_refs: tuple[str, ...],
        evidence_refs: tuple[str, ...],
    ) -> AIRun:
        if task.evidence_required and not evidence_refs:
            raise ValueError("evidence is required for this AI task")

        run = self._provider.run(task, input_refs=input_refs)

        if run.task_id != task.task_id:
            raise ValueError("AI provider returned mismatched task_id")
        if run.prompt_version != task.prompt_version:
            raise ValueError("AI provider returned mismatched prompt_version")
        if task.evidence_required and not set(run.evidence_refs).issubset(evidence_refs):
            raise ValueError("AI provider returned unsupported evidence references")
        if run.tokens < 0 or run.cost < 0 or run.duration_seconds < 0:
            raise ValueError("AI provider returned invalid usage metrics")
        return run
