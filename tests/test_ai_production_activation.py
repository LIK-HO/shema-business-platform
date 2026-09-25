from __future__ import annotations

import pytest

from shema_platform.adapters.ai.production_activation import (
    PRODUCTION_FEATURE_FLAG,
    AIProductionActivationError,
    YandexGPTProductionGate,
)
from shema_platform.application.ai import AIBudget, AIExecutionContext
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


def snapshot(
    *,
    enabled: bool = True,
    environment: str = "production",
    overrides: dict[str, object] | None = None,
) -> ConfigurationSnapshot:
    values: dict[str, object] = {
        "ai.yandexgpt.model_uri": "gpt://folder/yandexgpt/latest",
        "ai.yandexgpt.base_url": "https://ai.api.cloud.yandex.net/v1",
        "ai.yandexgpt.timeout_seconds": 10,
        "ai.yandexgpt.max_response_bytes": 1_048_576,
        "ai.yandexgpt.max_input_chars": 32_768,
        "ai.yandexgpt.max_output_tokens": 1_024,
        "ai.yandexgpt.max_cost": 0.50,
        "ai.yandexgpt.configuration_version": "cfg:yandexgpt-prod-v1",
        "ai.yandexgpt.activation_version": "activation:yandexgpt-prod-v1",
    }
    values.update(overrides or {})
    return ConfigurationSnapshot(
        version="prod-snapshot-v1",
        environment=environment,
        values=values,
        feature_flags={PRODUCTION_FEATURE_FLAG: enabled},
    )


def context(configuration_version: str | None = "cfg:yandexgpt-prod-v1") -> AIExecutionContext:
    return AIExecutionContext(
        actor_id="operator-1",
        resource_ref="identity:1",
        actor_trust_level=2,
        resource_trust_level=2,
        evidence_level=2,
        correlation_id="corr-prod-1",
        configuration_version=configuration_version,
    )


def test_activation_is_default_disabled_and_feature_flag_gated() -> None:
    telemetry = InMemoryTelemetrySink()
    gate = YandexGPTProductionGate(telemetry=telemetry)

    assert gate.state.enabled is False

    with pytest.raises(AIProductionActivationError, match="disabled by configuration"):
        gate.activate(
            snapshot(enabled=False),
            activated_by="operator-1",
            prompt_renderer=lambda _: "prompt",
            cost_estimator=lambda _input, _output: 0.01,
            api_key="runtime-secret",
        )

    assert gate.state.enabled is False
    assert telemetry.all() == ()


def test_activation_requires_production_environment() -> None:
    gate = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())

    with pytest.raises(AIProductionActivationError, match="production environment"):
        gate.activate(
            snapshot(environment="staging"),
            activated_by="operator-1",
            prompt_renderer=lambda _: "prompt",
            cost_estimator=lambda _input, _output: 0.01,
            api_key="runtime-secret",
        )


def test_activation_requires_runtime_secret_and_complete_snapshot() -> None:
    gate = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())

    with pytest.raises(AIProductionActivationError, match="YANDEXGPT_API_KEY"):
        gate.activate(
            snapshot(),
            activated_by="operator-1",
            prompt_renderer=lambda _: "prompt",
            cost_estimator=lambda _input, _output: 0.01,
            api_key="",
        )

    incomplete = snapshot()
    values = dict(incomplete.values)
    values.pop("ai.yandexgpt.max_cost")
    incomplete = ConfigurationSnapshot(
        version=incomplete.version,
        environment=incomplete.environment,
        values=values,
        feature_flags=incomplete.feature_flags,
    )

    with pytest.raises(AIProductionActivationError, match="missing required values"):
        gate.activate(
            incomplete,
            activated_by="operator-1",
            prompt_renderer=lambda _: "prompt",
            cost_estimator=lambda _input, _output: 0.01,
            api_key="runtime-secret",
        )


def test_activation_requires_explicit_operator_and_emits_non_authoritative_event() -> None:
    telemetry = InMemoryTelemetrySink()
    gate = YandexGPTProductionGate(telemetry=telemetry)

    with pytest.raises(AIProductionActivationError, match="explicit operator"):
        gate.activate(
            snapshot(),
            activated_by="",
            prompt_renderer=lambda _: "prompt",
            cost_estimator=lambda _input, _output: 0.01,
            api_key="runtime-secret",
        )

    provider = gate.activate(
        snapshot(),
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    assert provider.provider_id == "yandexgpt"
    assert gate.state.enabled is True
    assert gate.state.configuration_version == "cfg:yandexgpt-prod-v1"
    events = telemetry.all()
    assert [event.name for event in events] == ["ai.production.activated"]
    event = events[0]
    assert event.attributes["provider"] == "yandexgpt"
    assert event.attributes["operator"] == "operator-1"
    assert event.attributes["configuration_version"] == "cfg:yandexgpt-prod-v1"
    assert "api_key" not in event.attributes
    assert "prompt" not in event.attributes


def test_gate_blocks_request_when_configuration_version_does_not_match() -> None:
    gate = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    provider = gate.activate(
        snapshot(),
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    from shema_platform.adapters.ai.composition import (
        AIExecutionScope,
        bind_ai_execution_scope,
    )

    scope = AIExecutionScope(
        evidence_refs=("evidence:1",),
        context=context("different-config"),
        budget=AIBudget(100, 0.10, 5),
        deadline_seconds=5,
    )
    with bind_ai_execution_scope(
        evidence_refs=scope.evidence_refs,
        context=scope.context,
        budget=scope.budget,
        deadline_seconds=scope.deadline_seconds,
    ):
        with pytest.raises(RuntimeError, match="configuration"):
            provider.run(
                type("Task", (), {
                    "task_id": "task:1",
                    "task_type": "classification",
                    "prompt_version": "prompt:v1",
                    "evidence_required": True,
                })(),
                input_refs=("identity:1",),
            )


def test_gate_enforces_cost_and_deadline_ceilings() -> None:
    gate = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    provider = gate.activate(
        snapshot(),
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    from shema_platform.adapters.ai.composition import bind_ai_execution_scope
    from shema_platform.application.ai import AITask

    with bind_ai_execution_scope(
        evidence_refs=("evidence:1",),
        context=context(),
        budget=AIBudget(100, 0.60, 11),
        deadline_seconds=11,
    ):
        with pytest.raises(RuntimeError, match="production activation ceilings"):
            provider.run(
                AITask("task:1", "classification", "prompt:v1"),
                input_refs=("identity:1",),
            )


def test_rollback_is_reversible_and_blocks_future_traffic() -> None:
    telemetry = InMemoryTelemetrySink()
    gate = YandexGPTProductionGate(telemetry=telemetry)
    provider = gate.activate(
        snapshot(),
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    gate.rollback(
        rolled_back_by="operator-2",
        reason="controlled production rollback",
    )

    assert gate.state.enabled is False
    assert gate.state.rollback_from_configuration_version == "cfg:yandexgpt-prod-v1"
    assert gate.state.rollback_by == "operator-2"
    assert provider is not None
    events = telemetry.all()
    assert [event.name for event in events] == [
        "ai.production.activated",
        "ai.production.rolled_back",
    ]


def test_rollback_requires_operator_and_reason() -> None:
    gate = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    gate.activate(
        snapshot(),
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    with pytest.raises(AIProductionActivationError, match="explicit operator"):
        gate.rollback(rolled_back_by="", reason="reason")

    with pytest.raises(AIProductionActivationError, match="reason"):
        gate.rollback(rolled_back_by="operator-1", reason="")


def test_process_local_gate_starts_disabled_after_new_instance() -> None:
    first = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    first.activate(
        snapshot(),
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    second = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    assert second.state.enabled is False


def test_configuration_values_are_immutable_snapshot_inputs() -> None:
    telemetry = InMemoryTelemetrySink()
    gate = YandexGPTProductionGate(telemetry=telemetry)
    snap = snapshot()
    gate.activate(
        snap,
        activated_by="operator-1",
        prompt_renderer=lambda _: "prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="runtime-secret",
    )

    assert snap.version == "prod-snapshot-v1"
    assert snap.values["ai.yandexgpt.configuration_version"] == "cfg:yandexgpt-prod-v1"
