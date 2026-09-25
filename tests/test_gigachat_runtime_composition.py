import pytest

from shema_platform.experience.ai_application import AIOnlyAPIApplication
from shema_platform.experience.gigachat_runtime_composition import (
    GigaChatRuntimeAssembly,
    compose_gigachat_runtime,
)
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


class StaticTrustResolver:
    def resolve(
        self,
        *,
        resource_ref: str,
        evidence_refs: tuple[str, ...],
    ):
        raise AssertionError("trust resolver must not run during assembly")


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


def build() -> GigaChatRuntimeAssembly:
    return compose_gigachat_runtime(
        snapshot=snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        trust_resolver=StaticTrustResolver(),
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda input_tokens, output_tokens: 0.01,
    )


def test_runtime_assembly_is_explicit_and_does_not_activate_provider() -> None:
    assembly = build()

    assert isinstance(assembly, GigaChatRuntimeAssembly)
    assert isinstance(assembly.api_application(), AIOnlyAPIApplication)
    assert assembly.ai.gate.state.enabled is False

    with pytest.raises(Exception, match="not activated"):
        assembly.ai.configuration_version()


def test_runtime_assembly_activation_requires_explicit_operator() -> None:
    assembly = build()

    with pytest.raises(Exception, match="explicit operator"):
        assembly.activate_gigachat(activated_by="")

    assert assembly.ai.gate.state.enabled is False


def test_runtime_assembly_activation_has_no_network_side_effect() -> None:
    calls = 0

    def requester(*args):
        nonlocal calls
        calls += 1
        return 200, b"{}"

    assembly = build()
    assembly.activate_gigachat(
        activated_by="operator",
        authorization_key="runtime-secret",
        requester=requester,
        token_requester=requester,
    )

    assert assembly.ai.gate.state.enabled is True
    assert calls == 0


def test_runtime_assembly_rollback_is_explicit() -> None:
    assembly = build()
    assembly.activate_gigachat(
        activated_by="operator",
        authorization_key="runtime-secret",
    )

    assembly.rollback_gigachat(
        rolled_back_by="operator",
        reason="runtime assembly test rollback",
    )

    assert assembly.ai.gate.state.enabled is False
