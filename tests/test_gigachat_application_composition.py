import pytest

from shema_platform.adapters.ai.composition import AIProviderCompositionError
from shema_platform.adapters.ai.gigachat_application_composition import (
    GigaChatApplicationComposition,
)
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


def snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="runtime:v1",
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
            "ai.gigachat.configuration_version": "gigachat-config:v1",
            "ai.gigachat.activation_version": "gigachat-activation:v1",
        },
        feature_flags={"ai.gigachat.production.enabled": True},
    )


def build() -> GigaChatApplicationComposition:
    return GigaChatApplicationComposition(
        snapshot=snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(
            AssertionError("UoW must not be created during composition")
        ),
        trust_resolver=lambda **_: None,
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda *_: 0.01,
    )


def test_composition_is_disabled_by_default() -> None:
    composition = build()

    assert composition.gate.state.enabled is False

    with pytest.raises(
        AIProviderCompositionError,
        match="not activated",
    ):
        composition.configuration_version()

    with pytest.raises(
        AIProviderCompositionError,
        match="not activated",
    ):
        composition.provider()


def test_composition_service_does_not_activate_provider() -> None:
    composition = build()

    service = composition.service()

    assert service is not None
    assert composition.gate.state.enabled is False


def test_activation_is_explicit_and_does_not_make_network_calls() -> None:
    calls = 0

    def requester(*args):
        nonlocal calls
        calls += 1
        return 200, b"{}"

    composition = build()
    composition.activate(
        activated_by="operator",
        authorization_key="runtime-secret",
        requester=requester,
        token_requester=requester,
    )

    assert composition.gate.state.enabled is True
    assert calls == 0


def test_activation_requires_explicit_operator() -> None:
    composition = build()

    with pytest.raises(Exception, match="explicit operator"):
        composition.activate(
            activated_by="",
            authorization_key="runtime-secret",
        )

    assert composition.gate.state.enabled is False


def test_rollback_removes_provider_from_composition() -> None:
    composition = build()
    composition.activate(
        activated_by="operator",
        authorization_key="runtime-secret",
    )

    composition.rollback(
        rolled_back_by="operator",
        reason="composition test rollback",
    )

    assert composition.gate.state.enabled is False
    with pytest.raises(
        AIProviderCompositionError,
        match="not activated",
    ):
        composition.provider()
