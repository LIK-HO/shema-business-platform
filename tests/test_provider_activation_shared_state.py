from datetime import UTC, datetime

import pytest

from shema_platform.adapters.ai.production_activation import (
    AIProductionActivationError,
    YandexGPTProductionGate,
)
from shema_platform.foundation.provider_activation import (
    InMemoryProviderActivationStateStore,
)
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


class ReadyProvider:
    class Readiness:
        state = "ready"
        error_code = None

    def readiness(self):
        from shema_platform.adapters.ai.contracts import (
            AIProviderReadiness,
            AIProviderReadinessState,
        )

        return AIProviderReadiness(
            provider_id="yandexgpt",
            state=AIProviderReadinessState.READY,
            checked_at=datetime.now(UTC),
        )

    def descriptor(self):
        from shema_platform.adapters.ai.contracts import (
            AIModelProvenance,
            AIProviderDescriptor,
            AIProviderKind,
            AIProviderResourceLimits,
        )

        return AIProviderDescriptor(
            provider_id="yandexgpt",
            kind=AIProviderKind.CLOUD,
            model_id="test-model",
            model_version="1",
            configuration_version="shared-config:v1",
            capabilities=frozenset({"text_generation"}),
            resource_limits=AIProviderResourceLimits(
                max_duration_seconds=10,
                max_response_bytes=1024,
                max_input_chars=1024,
                max_output_tokens=128,
                max_calls=1,
                max_cost=1,
            ),
            provenance=AIModelProvenance(
                source_ref="https://example.test",
                license_name="test",
                license_url="https://example.test/license",
                license_checked_at=None,
                artifact_digest=None,
                runtime="test",
                security_status="test-only",
                free_commercial_use_verified=False,
            ),
        )

    def activation(self):
        from shema_platform.adapters.ai.contracts import AIProviderActivation

        return AIProviderActivation(
            enabled=True,
            activation_version="shared-activation:v1",
            explicit=True,
            reason="shared-state test",
        )


def test_activation_and_rollback_are_global_across_replicas() -> None:
    store = InMemoryProviderActivationStateStore()

    gate_a = YandexGPTProductionGate(
        telemetry=InMemoryTelemetrySink(),
        activation_state_store=store,
        provider_factory=lambda secret, **kwargs: ReadyProvider(),
        configuration_version="shared-config:v1",
    )
    gate_b = YandexGPTProductionGate(
        telemetry=InMemoryTelemetrySink(),
        activation_state_store=store,
        provider_factory=lambda secret, **kwargs: ReadyProvider(),
        configuration_version="shared-config:v1",
    )

    snapshot = {
        "environment": "production",
        "values": {
            "ai.yandexgpt.model_uri": "gpt://test/model",
            "ai.yandexgpt.base_url": "https://ai.api.cloud.yandex.net/v1",
            "ai.yandexgpt.timeout_seconds": 10,
            "ai.yandexgpt.max_response_bytes": 1024,
            "ai.yandexgpt.max_input_chars": 1024,
            "ai.yandexgpt.max_output_tokens": 128,
            "ai.yandexgpt.max_cost": 1,
            "ai.yandexgpt.configuration_version": "shared-config:v1",
            "ai.yandexgpt.activation_version": "shared-activation:v1",
        },
        "feature_flags": {"ai.yandexgpt.production.enabled": True},
    }

    from shema_platform.foundation.configuration import ConfigurationSnapshot

    gate_a.activate(
        ConfigurationSnapshot(**snapshot),
        activated_by="operator-a",
        prompt_renderer=lambda _: "unused",
        cost_estimator=lambda *_: 0.01,
        api_key="secret",
    )

    assert gate_b.state.enabled is True
    assert gate_b.provider() is not None

    gate_a.rollback(
        rolled_back_by="operator-a",
        reason="kill switch",
    )

    assert gate_b.state.enabled is False
    assert gate_b.allows_request(configuration_version="shared-config:v1") is False

    with pytest.raises(AIProductionActivationError):
        gate_b.provider()
