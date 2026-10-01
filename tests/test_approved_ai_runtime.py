import pytest

from shema_platform.experience.approved_ai_runtime import (
    AIProviderSelectionError,
    ApprovedAIRuntimeAssembly,
    compose_approved_ai_runtime,
)
from shema_platform.experience.gigachat_runtime_composition import (
    GigaChatRuntimeAssembly,
    compose_gigachat_runtime,
)
from shema_platform.experience.runtime_composition import (
    YandexGPTRuntimeAssembly,
    compose_yandexgpt_runtime,
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
        raise AssertionError("trust resolver must not run during provider selection")


def yandex_snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="runtime:yandex:v1",
        environment="production",
        values={
            "ai.yandexgpt.model_uri": "gpt://folder/yandexgpt/latest",
            "ai.yandexgpt.base_url": "https://ai.example.test/v1",
            "ai.yandexgpt.timeout_seconds": 10,
            "ai.yandexgpt.max_response_bytes": 1_048_576,
            "ai.yandexgpt.max_input_chars": 32_768,
            "ai.yandexgpt.max_output_tokens": 100,
            "ai.yandexgpt.max_cost": 1,
            "ai.yandexgpt.configuration_version": "yandexgpt-config:v1",
            "ai.yandexgpt.activation_version": "yandexgpt-activation:v1",
        },
        feature_flags={"ai.yandexgpt.production.enabled": True},
    )


def gigachat_snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="runtime:gigachat:v1",
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


def build_yandex() -> YandexGPTRuntimeAssembly:
    return compose_yandexgpt_runtime(
        snapshot=yandex_snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        trust_resolver=StaticTrustResolver(),
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda input_tokens, output_tokens: 0.01,
    )


def build_gigachat() -> GigaChatRuntimeAssembly:
    return compose_gigachat_runtime(
        snapshot=gigachat_snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        trust_resolver=StaticTrustResolver(),
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda input_tokens, output_tokens: 0.01,
    )


def test_select_yandexgpt_without_activation_or_fallback() -> None:
    yandex = build_yandex()
    gigachat = build_gigachat()

    assembly = compose_approved_ai_runtime(
        provider_id="yandexgpt",
        yandexgpt=yandex,
        gigachat=gigachat,
    )

    assert isinstance(assembly, ApprovedAIRuntimeAssembly)
    assert assembly.provider_id == "yandexgpt"
    assert yandex.ai.gate.state.enabled is False
    assert gigachat.ai.gate.state.enabled is False


def test_select_gigachat_without_activation_or_fallback() -> None:
    yandex = build_yandex()
    gigachat = build_gigachat()

    assembly = compose_approved_ai_runtime(
        provider_id=" gigachat ",
        yandexgpt=yandex,
        gigachat=gigachat,
    )

    assert assembly.provider_id == "gigachat"
    assert yandex.ai.gate.state.enabled is False
    assert gigachat.ai.gate.state.enabled is False


def test_unsupported_provider_fails_closed() -> None:
    yandex = build_yandex()
    gigachat = build_gigachat()

    with pytest.raises(
        AIProviderSelectionError,
        match="unsupported AI provider selection",
    ):
        compose_approved_ai_runtime(
            provider_id="openai",
            yandexgpt=yandex,
            gigachat=gigachat,
        )

    assert yandex.ai.gate.state.enabled is False
    assert gigachat.ai.gate.state.enabled is False


def test_missing_selected_provider_does_not_fallback() -> None:
    gigachat = build_gigachat()

    with pytest.raises(
        AIProviderSelectionError,
        match="yandexgpt.*not composed",
    ):
        compose_approved_ai_runtime(
            provider_id="yandexgpt",
            gigachat=gigachat,
        )

    assert gigachat.ai.gate.state.enabled is False


def test_selection_is_immutable() -> None:
    assembly = compose_approved_ai_runtime(
        provider_id="yandexgpt",
        yandexgpt=build_yandex(),
    )

    with pytest.raises(AttributeError):
        assembly.provider_id = "gigachat"

    assert assembly.provider_id == "yandexgpt"


def test_selection_does_not_perform_provider_io() -> None:
    yandex = build_yandex()
    gigachat = build_gigachat()

    assembly = compose_approved_ai_runtime(
        provider_id="yandexgpt",
        yandexgpt=yandex,
        gigachat=gigachat,
    )

    assert assembly.api_application() is not None
    assert yandex.ai.gate.state.enabled is False
    assert gigachat.ai.gate.state.enabled is False
