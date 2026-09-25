from __future__ import annotations

from pathlib import Path

from shema_platform.adapters.ai import production_activation
from shema_platform.adapters.ai.gigachat_activation import GigaChatProductionGate
from shema_platform.adapters.ai.production_activation import YandexGPTProductionGate
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink
from shema_platform.platform.ai_promotion_gate import (
    approve_ai_promotion,
    assess_ai_promotion,
)

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


def test_promotion_approval_does_not_activate_provider() -> None:
    assessment = assess_ai_promotion(ROOT)
    approval = approve_ai_promotion(
        assessment,
        approved_by="operator-p40",
        reason="deterministic activation rehearsal",
    )

    yandex_gate = YandexGPTProductionGate(
        telemetry=InMemoryTelemetrySink(),
    )
    gigachat_gate = GigaChatProductionGate(
        telemetry=InMemoryTelemetrySink(),
    )

    assert approval.approved_by == "operator-p40"
    assert yandex_gate.state.enabled is False
    assert gigachat_gate.state.enabled is False


def test_yandex_activation_and_rollback_are_explicit_without_network(
    monkeypatch,
) -> None:
    calls = 0
    real_provider = production_activation.YandexGPTProvider

    def forbidden_requester(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        raise AssertionError("P40 rehearsal must not call YandexGPT")

    def deterministic_provider(configuration, *, prompt_renderer, cost_estimator):
        return real_provider(
            configuration,
            prompt_renderer=prompt_renderer,
            cost_estimator=cost_estimator,
            requester=forbidden_requester,
        )

    monkeypatch.setattr(
        production_activation,
        "YandexGPTProvider",
        deterministic_provider,
    )

    telemetry = InMemoryTelemetrySink()
    gate = YandexGPTProductionGate(telemetry=telemetry)

    provider = gate.activate(
        yandex_snapshot(),
        activated_by="operator-p40",
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda *_: 0.01,
        api_key="test-secret",
    )

    assert provider.provider_id == "yandexgpt"
    assert gate.state.enabled is True
    assert calls == 0

    gate.rollback(
        rolled_back_by="operator-p40",
        reason="P40 rehearsal rollback",
    )

    assert gate.state.enabled is False
    assert gate.allows_request(
        configuration_version="p40-yandex-config:v1",
    ) is False
    assert [event.name for event in telemetry.all()] == [
        "ai.production.activated",
        "ai.production.rolled_back",
    ]


def test_gigachat_activation_and_rollback_are_explicit_without_network() -> None:
    calls = 0

    def forbidden_requester(*args: object, **kwargs: object):
        nonlocal calls
        calls += 1
        raise AssertionError("P40 rehearsal must not call GigaChat")

    telemetry = InMemoryTelemetrySink()
    gate = GigaChatProductionGate(telemetry=telemetry)

    provider = gate.activate(
        gigachat_snapshot(),
        activated_by="operator-p40",
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda *_: 0.01,
        authorization_key="test-secret",
        requester=forbidden_requester,
        token_requester=forbidden_requester,
    )

    assert provider.provider_id == "gigachat"
    assert gate.state.enabled is True
    assert calls == 0

    gate.rollback(
        rolled_back_by="operator-p40",
        reason="P40 rehearsal rollback",
    )

    assert gate.state.enabled is False
    assert gate.allows_request(
        configuration_version="p40-gigachat-config:v1",
    ) is False
    assert [event.name for event in telemetry.all()] == [
        "ai.production.activated",
        "ai.production.rolled_back",
    ]


def test_rehearsal_never_persists_or_changes_business_state() -> None:
    assessment = assess_ai_promotion(ROOT)
    approval = approve_ai_promotion(
        assessment,
        approved_by="operator-p40",
        reason="no-live rehearsal",
    )

    assert approval.assessment_evidence_refs == assessment.evidence_refs
    assert approval.approved_by == "operator-p40"
    assert "ai_run" not in approval.assessment_evidence_refs
