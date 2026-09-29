import pytest
from fastapi.testclient import TestClient

from shema_platform.experience.ai_application import AIOnlyAPIApplication
from shema_platform.experience.api_models import SearchResponse
from shema_platform.experience.runtime_composition import (
    YandexGPTRuntimeAssembly,
    compose_yandexgpt_runtime,
)
from shema_platform.experience.search_composition import SearchAugmentedAPIApplication
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.configuration import ConfigurationSnapshot
from shema_platform.foundation.provider_activation import (
    InMemoryProviderActivationStateStore,
)
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


class StaticTrustResolver:
    def resolve(
        self,
        *,
        resource_ref: str,
        evidence_refs: tuple[str, ...],
    ):
        raise AssertionError("trust resolver must not run during assembly")


class FakeAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization != "Bearer test-token":
            raise AssertionError("unexpected authorization")
        return AuthenticatedActor(
            "operator-1",
            trust_level=2,
            permissions=frozenset({Permission.SEARCH_RUN}),
        )


class MockSearchApplication:
    def search(self, request, context):
        return SearchResponse(
            results=[],
            correlationId=context.correlation_id,
        )


def snapshot() -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="runtime:v1",
        environment="production",
        values={
            "ai.yandexgpt.model_uri": "gpt://folder/yandexgpt/latest",
            "ai.yandexgpt.base_url": "https://ai.api.cloud.yandex.net/v1",
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


def build() -> YandexGPTRuntimeAssembly:
    return compose_yandexgpt_runtime(
        snapshot=snapshot(),
        telemetry=InMemoryTelemetrySink(),
        unit_of_work_factory=lambda: (_ for _ in ()).throw(AssertionError()),
        trust_resolver=StaticTrustResolver(),
        prompt_renderer=lambda request: "unused",
        cost_estimator=lambda input_tokens, output_tokens: 0.01,
        activation_state_store=InMemoryProviderActivationStateStore(),
    )


def test_public_intake_runtime_requires_server_side_security_prerequisites() -> None:
    from shema_platform.experience.runtime_composition import compose_public_intake_runtime

    def failing_connection():
        raise AssertionError(
            "database must not be touched during insecure composition"
        )

    def failing_uow():
        raise AssertionError(
            "canonical DB must not be touched during insecure composition"
        )

    with pytest.raises(ValueError, match="origin allowlist"):
        compose_public_intake_runtime(
            intake_connection_factory=failing_connection,
            shema_unit_of_work_factory=failing_uow,
        )

    with pytest.raises(ValueError, match="bot challenge verifier"):
        compose_public_intake_runtime(
            intake_connection_factory=failing_connection,
            shema_unit_of_work_factory=failing_uow,
            allowed_origins=frozenset({"https://example.test"}),
        )


def test_runtime_assembly_is_explicit_and_does_not_activate_provider() -> None:
    assembly = build()

    assert isinstance(assembly, YandexGPTRuntimeAssembly)
    assert isinstance(assembly.api_application(), AIOnlyAPIApplication)
    assert assembly.ai.gate.state.enabled is False
    with pytest.raises(Exception, match="not (activated|enabled)"):
        assembly.ai.configuration_version()


def test_runtime_assembly_can_compose_search_without_provider_activation() -> None:
    assembly = build()
    search_application = MockSearchApplication()

    composed = assembly.api_application(search_application=search_application)

    assert isinstance(composed, SearchAugmentedAPIApplication)
    assert assembly.ai.gate.state.enabled is False


def test_runtime_assembly_activation_is_explicit() -> None:
    assembly = build()

    with pytest.raises(Exception, match="explicit operator"):
        assembly.activate_yandexgpt(activated_by="")

    assert assembly.ai.gate.state.enabled is False


def test_runtime_http_composes_search_without_changing_provider_activation() -> None:
    assembly = build()
    client = TestClient(
        assembly.create_http_app(
            authenticator=FakeAuthenticator(),
            search_application=MockSearchApplication(),
        )
    )

    response = client.post(
        "/v1/search",
        headers={
            "Authorization": "Bearer test-token",
            "X-Correlation-Id": "corr-runtime-search",
        },
        json={"region": "Moscow", "industries": ["logistics"]},
    )

    assert response.status_code == 200
    assert response.json()["results"] == []
    assert response.json()["correlationId"]
    assert response.json()["correlationId"] != "corr-runtime-search"
    assert assembly.ai.gate.state.enabled is False
