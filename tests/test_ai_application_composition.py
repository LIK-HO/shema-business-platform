from datetime import UTC, datetime

import pytest

from fastapi.testclient import TestClient

from shema_platform.adapters.ai.application_composition import (
    YandexGPTApplicationComposition,
)
from shema_platform.adapters.ai.composition import AIProviderCompositionError
from shema_platform.application.ai_runtime import AIExecutionTrust
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.errors import QuarantineRequired
from shema_platform.foundation.telemetry import InMemoryTelemetrySink
from shema_platform.experience.ai_application import AIOnlyAPIApplication
from shema_platform.experience.api import create_app
from shema_platform.foundation.authentication import AuthenticatedActor, AuthenticationPort
from shema_platform.foundation.policy import PolicyEngine


class FakeAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer test":
            from shema_platform.foundation.authorization import Permission

            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset({Permission.AI_RUN}),
            )
        raise RuntimeError("unexpected auth")


class StaticTrustResolver:
    def resolve(self, *, resource_ref: str, evidence_refs: tuple[str, ...]) -> AIExecutionTrust:
        return AIExecutionTrust(resource_trust_level=2, evidence_level=2)


class MissingTrustResolver:
    def resolve(self, *, resource_ref: str, evidence_refs: tuple[str, ...]) -> AIExecutionTrust:
        raise QuarantineRequired("evidence is not usable")


def snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="runtime:v1",
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


def test_yandex_application_composition_is_disabled_until_explicit_activation() -> None:
    composition = YandexGPTApplicationComposition(
        snapshot=snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        trust_resolver=StaticTrustResolver(),
        prompt_renderer=lambda request: "unused",
        cost_estimator=lambda input_tokens, output_tokens: 0.01,
        policy=PolicyEngine(),
    )

    with pytest.raises(AIProviderCompositionError, match="not activated"):
        composition.configuration_version()

    with pytest.raises(AIProviderCompositionError, match="not activated"):
        composition.provider()

    assert composition.gate.state.enabled is False


def test_yandex_application_composition_requires_explicit_operator_on_activation() -> None:
    composition = YandexGPTApplicationComposition(
        snapshot=snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        trust_resolver=StaticTrustResolver(),
        prompt_renderer=lambda request: "unused",
        cost_estimator=lambda input_tokens, output_tokens: 0.01,
    )

    with pytest.raises(Exception, match="explicit operator"):
        composition.activate(activated_by="")

    assert composition.gate.state.enabled is False


def test_ai_only_api_application_returns_503_for_unavailable_provider() -> None:
    class InactiveService:
        def execute(self, request):
            raise AIProviderCompositionError(
                type("Failure", (), {})()
            )

    # Use the real composition failure type through a tiny explicit provider factory.
    class FailingService:
        def execute(self, request):
            from shema_platform.adapters.ai.contracts import (
                AIProviderFailure,
                AIProviderFailureCode,
            )

            raise AIProviderCompositionError(
                AIProviderFailure(
                    code=AIProviderFailureCode.NOT_READY,
                    message="YandexGPT production application is not activated",
                )
            )

    application = AIOnlyAPIApplication(FailingService())
    client = TestClient(create_app(application, FakeAuthenticator()))

    response = client.post(
        "/v1/ai/run",
        headers={"Authorization": "Bearer test"},
        json={
            "taskType": "qualification",
            "promptVersion": "prompt:v1",
            "resourceRef": "identity-1",
            "inputRefs": ["identity-1"],
            "evidenceRefs": ["evidence-1"],
            "maxTokens": 100,
            "maxCost": 0.1,
            "maxDurationSeconds": 1,
        },
    )

    assert response.status_code == 503
    assert response.json()["code"] == "ai_provider_unavailable"
    assert response.json()["details"]["failureCode"] == "not_ready"


def test_ai_only_api_application_keeps_uncomposed_capabilities_unavailable() -> None:
    class InactiveService:
        def execute(self, request):
            raise AssertionError()

    application = AIOnlyAPIApplication(InactiveService())
    client = TestClient(create_app(application, FakeAuthenticator()))

    response = client.get(
        "/v1/diagnostics",
        headers={"Authorization": "Bearer test"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"
