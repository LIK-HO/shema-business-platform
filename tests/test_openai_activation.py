import pytest

from shema_platform.adapters.ai.activation import OpenAIProviderFactory
from shema_platform.foundation.configuration import ConfigurationSnapshot


def snapshot(
    *,
    enabled: bool,
    values: dict[str, object] | None = None,
) -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p24-openai-2026-09-24",
        environment="production",
        values=values or {},
        feature_flags={
            OpenAIProviderFactory.FEATURE_FLAG: enabled,
        },
    )


def resolvers():
    return (
        lambda task, refs: "Analyze the supplied evidence.",
        lambda refs: tuple(refs),
    )


def test_disabled_openai_provider_does_not_activate() -> None:
    assert OpenAIProviderFactory.from_snapshot(snapshot(enabled=False)) is None


def test_enabled_openai_provider_requires_runtime_secret(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    prompt_resolver, evidence_resolver = resolvers()

    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        OpenAIProviderFactory.from_snapshot(
            snapshot(enabled=True),
            prompt_resolver=prompt_resolver,
            evidence_resolver=evidence_resolver,
        )


def test_enabled_openai_provider_requires_resolvers(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-secret")

    with pytest.raises(ValueError, match="prompt_resolver"):
        OpenAIProviderFactory.from_snapshot(
            snapshot(enabled=True),
            evidence_resolver=lambda refs: tuple(refs),
        )


def test_enabled_openai_provider_composes_from_snapshot(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "runtime-secret")
    prompt_resolver, evidence_resolver = resolvers()

    provider = OpenAIProviderFactory.from_snapshot(
        snapshot(
            enabled=True,
            values={
                "openai.model": "gpt-6-luna",
                "openai.timeout_seconds": 10,
                "openai.max_output_tokens": 2048,
                "openai.max_cost_usd_per_call": 0.01,
            },
        ),
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
    )

    assert provider is not None
    assert provider.provider_id == "openai"


def test_explicit_api_key_stays_outside_snapshot() -> None:
    prompt_resolver, evidence_resolver = resolvers()

    provider = OpenAIProviderFactory.from_snapshot(
        snapshot(enabled=True),
        api_key="runtime-secret",
        prompt_resolver=prompt_resolver,
        evidence_resolver=evidence_resolver,
    )

    assert provider is not None
