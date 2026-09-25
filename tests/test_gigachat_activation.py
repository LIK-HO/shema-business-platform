import pytest

from shema_platform.adapters.ai.gigachat_activation import (
    GigaChatProductionActivationError,
    GigaChatProductionGate,
)
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


def snapshot(scope: str = "GIGACHAT_API_B2B") -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="runtime:v1",
        environment="production",
        values={
            "ai.gigachat.model": "GigaChat-2-Max",
            "ai.gigachat.scope": scope,
            "ai.gigachat.base_url": "https://api.giga.chat/v1",
            "ai.gigachat.token_url": (
                "https://ngw.devices.sberbank.ru:9443/api/v2/oauth"
            ),
            "ai.gigachat.timeout_seconds": 10,
            "ai.gigachat.max_response_bytes": 1_048_576,
            "ai.gigachat.max_input_chars": 32_768,
            "ai.gigachat.max_output_tokens": 100,
            "ai.gigachat.max_cost": 1,
            "ai.gigachat.configuration_version": "gigachat-config:v1",
            "ai.gigachat.activation_version": "gigachat-activation:v1",
        },
        feature_flags={"ai.gigachat.production.enabled": True},
    )


def build() -> GigaChatProductionGate:
    return GigaChatProductionGate(telemetry=InMemoryTelemetrySink())


def test_gate_is_disabled_by_default() -> None:
    gate = build()
    assert gate.state.enabled is False


def test_gate_requires_explicit_operator() -> None:
    gate = build()

    with pytest.raises(
        GigaChatProductionActivationError,
        match="explicit operator",
    ):
        gate.activate(
            snapshot(),
            activated_by="",
            prompt_renderer=lambda _: "unused",
            cost_estimator=lambda *_: 0.01,
            authorization_key="secret",
        )


def test_gate_rejects_personal_freemium_scope_for_production() -> None:
    gate = build()

    with pytest.raises(
        GigaChatProductionActivationError,
        match="B2B or CORP",
    ):
        gate.activate(
            snapshot("GIGACHAT_API_PERS"),
            activated_by="operator",
            prompt_renderer=lambda _: "unused",
            cost_estimator=lambda *_: 0.01,
            authorization_key="secret",
        )


def test_gate_activation_does_not_make_http_traffic() -> None:
    calls = 0

    def requester(*args):
        nonlocal calls
        calls += 1
        return 200, b"{}"

    gate = build()
    provider = gate.activate(
        snapshot(),
        activated_by="operator",
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda *_: 0.01,
        authorization_key="secret",
        requester=requester,
        token_requester=requester,
    )

    assert gate.state.enabled is True
    assert provider.provider_id == "gigachat"
    assert calls == 0


def test_gate_rollback_disables_future_requests() -> None:
    gate = build()
    gate.activate(
        snapshot(),
        activated_by="operator",
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda *_: 0.01,
        authorization_key="secret",
    )

    assert gate.state.enabled is True
    gate.rollback(rolled_back_by="operator", reason="test rollback")
    assert gate.state.enabled is False
    assert gate.allows_request(
        configuration_version="gigachat-config:v1"
    ) is False


def test_gate_fails_closed_without_runtime_secret() -> None:
    gate = build()

    with pytest.raises(
        GigaChatProductionActivationError,
        match="GIGACHAT_AUTHORIZATION_KEY",
    ):
        gate.activate(
            snapshot(),
            activated_by="operator",
            prompt_renderer=lambda _: "unused",
            cost_estimator=lambda *_: 0.01,
            authorization_key="",
        )
