from dataclasses import dataclass

import pytest

from shema_platform.application.ai import AIGateway, AIRun, AITask, AIProvider


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


def test_ai_gateway_requires_evidence_for_critical_task() -> None:
    task = AITask("task-1", "qualification", "prompt:v1", evidence_required=True)

    with pytest.raises(ValueError, match="evidence is required"):
        AIGateway(FakeAIProvider()).execute(
            task,
            input_refs=("identity:1",),
            evidence_refs=(),
        )


def test_ai_gateway_validates_provider_result() -> None:
    task = AITask("task-1", "qualification", "prompt:v1", evidence_required=True)
    run = AIGateway(FakeAIProvider()).execute(
        task,
        input_refs=("identity:1",),
        evidence_refs=("evidence:1",),
    )

    assert run.task_id == task.task_id
    assert run.prompt_version == task.prompt_version
    assert run.tokens == 12


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

    with pytest.raises(ValueError, match="unsupported evidence"):
        AIGateway(BadProvider()).execute(
            AITask("task-1", "qualification", "prompt:v1"),
            input_refs=("identity:1",),
            evidence_refs=("evidence:1",),
        )
