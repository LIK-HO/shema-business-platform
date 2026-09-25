import pytest

from shema_platform.adapters.ai.composition import (
    bind_ai_execution_scope,
)
from shema_platform.adapters.ai.contracts import AIProviderFailureCode
from shema_platform.adapters.ai.gigachat_activation import (
    GigaChatProductionGate,
)
from shema_platform.adapters.ai.production_activation import (
    YandexGPTProductionGate,
)
from shema_platform.application.ai import AIBudget, AITask, AIExecutionContext
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink
from shema_platform.platform.ai_promotion_gate import (
    approve_ai_promotion,
    assess_ai_promotion,
)

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def yandex_snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p40-yandex-runtime:v1",
        environment="production",
        values={
            "ai.yandexgpt.model_uri": "gpt://p40/yandexgpt/latest",
            "ai.yandexgpt.base_url": "https://ai.example.test/v1",
            "ai.yandexgpt.timeout_seconds": 10,
            "ai.yandexgpt.max_response_bytes": 1_048_576,
            "ai.yandexgpt.max_input_chars": 32_768,
            "ai.yandexgpt.max_output_tokens": 100,
            "ai.yandexgpt.max_cost": 1,
            "ai.yandexgpt.configuration_version": "p40-yandex-config:v1",
            "ai.yandexgpt.activation_version": "p40-yandex-activation:v1",
        },
        feature_flags={"ai.yandexgpt.production.enabled": True},
    )


def gigachat_snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p40-gigachat-runtime:v1",
        environment="production",
        values={
            "ai.gigachat.model": "GigaChat-2-Max",
            "ai.gigachat.scope": "GIGACHAT_API_B2B",
            "ai.gigachat.base_url": "https://api.giga.chat/v1",
            "ai.gigachat.token_url": (
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
            ),
            "ai.gigachat.timeout_seconds": 10,
            "ai.gigachat.max_response_bytes": 1_048_576,
            "ai.gigachat.max_input_chars": 32_768,
            "ai.gigachat.max_output_tokens": 100,
            "ai.gigachat.max_cost": 1,
            "ai.gigachat.configuration_version": "p40-gigachat-config:v1",
            "ai.gigachat.activation_version": "p40-gigachat-activation:v1",
        },
        feature_flags={"ai.gigachat.production.enabled": True},
    )


def execution_context(configuration_version: str) -> AIExecutionContext:
    return AIExecutionContext(
        correlation_id=f"p40:{configuration_version}",
        configuration_version=configuration_version,
        actor_id="p40-operator",
    )


def exercise_rolled_back_provider(provider, configuration_version: str) -> None:
    with bind_ai_execution_scope(
        evidence_refs=("evidence:p40",),
        context=execution_context(configuration_version),
        budget=AIBudget(max_tokens=100, max_cost=0.50, max_duration_seconds=5),
        deadline_seconds=5,
    ):
        with pytest.raises(Exception) as exc_info:
            provider.run(
                AITask("task:p40", "qualification", "prompt:p40"),
                input_refs=("identity:p40",),
            )

    failure = getattr(exc_info.value, "failure", None)
    if failure is None:
        raise AssertionError("rollback must fail through provider composition boundary")
    assert failure.code is AIProviderFailureCode.NOT_READY


def test_green_promotion_approval_does_not_activate_either_provider() -> None:
    assessment = assess_ai_promotion(ROOT)
    approval = approve_ai_promotion(
        assessment,
        approved_by="p40-operator",
        reason="controlled production activation rehearsal",
    )

    assert approval.approved_by == "p40-operator"

    yandex = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    gigachat = GigaChatProductionGate(telemetry=InMemoryTelemetrySink())

    assert yandex.state.enabled is False
    assert gigachat.state.enabled is False


def test_yandex_activation_and_rollback_rehearsal_has_no_external_traffic() -> None:
    calls = 0

    telemetry = InMemoryTelemetrySink()
    gate = YandexGPTProductionGate(telemetry=telemetry)

    provider = gate.activate(
        yandex_snapshot(),
        activated_by="p40-operator",
        prompt_renderer=lambda _: "deterministic test prompt",
        cost_estimator=lambda _input, _output: 0.01,
        api_key="p40-runtime-secret",
    )

    assert calls == 0
    assert gate.state.enabled is True
    assert provider.provider_id == "yandexgpt"

    gate.rollback(
        rolled_back_by="p40-operator",
        reason="P40 controlled rehearsal rollback",
    )

    assert gate.state.enabled is False
    exercise_rolled_back_provider(
        provider,
        "p40-yandex-config:v1",
    )
    assert [event.name for event in telemetry.all()] == [
        "ai.production.activated",
        "ai.production.rolled_back",
    ]


def test_gigachat_activation_and_rollback_rehearsal_has_no_external_traffic() -> None:
    calls = 0

    def requester(*_args, **_kwargs):
        nonlocal calls
        calls += 1
        return 500, b"unexpected external call"

    telemetry = InMemoryTelemetrySink()
    gate = GigaChatProductionGate(telemetry=telemetry)

    provider = gate.activate(
        gigachat_snapshot(),
        activated_by="p40-operator",
        prompt_renderer=lambda _: "deterministic test prompt",
        cost_estimator=lambda _input, _output: 0.01,
        authorization_key="p40-runtime-secret",
        requester=requester,
        token_requester=requester,
    )

    assert calls == 0
    assert gate.state.enabled is True
    assert provider.provider_id == "gigachat"

    gate.rollback(
        rolled_back_by="p40-operator",
        reason="P40 controlled rehearsal rollback",
    )

    assert gate.state.enabled is False
    exercise_rolled_back_provider(
        provider,
        "p40-gigachat-config:v1",
    )
    assert calls == 0
    assert [event.name for event in telemetry.all()] == [
        "ai.production.activated",
        "ai.production.rolled_back",
    ]


def test_rehearsal_requires_explicit_activation_for_each_provider() -> None:
    yandex = YandexGPTProductionGate(telemetry=InMemoryTelemetrySink())
    gigachat = GigaChatProductionGate(telemetry=InMemoryTelemetrySink())

    assert yandex.state.enabled is False
    assert gigachat.state.enabled is False

    with pytest.raises(Exception, match="explicit operator"):
        yandex.activate(
            yandex_snapshot(),
            activated_by="",
            prompt_renderer=lambda _: "unused",
            cost_estimator=lambda *_: 0.01,
            api_key="secret",
        )

    with pytest.raises(Exception, match="explicit operator"):
        gigachat.activate(
            gigachat_snapshot(),
            activated_by="",
            prompt_renderer=lambda _: "unused",
            cost_estimator=lambda *_: 0.01,
            authorization_key="secret",
        )

    assert yandex.state.enabled is False
    assert gigachat.state.enabled is False
