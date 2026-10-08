import importlib

from fastapi.testclient import TestClient

from shema_platform.experience.runtime_application import (
    ProviderNeutralRuntimeApplication,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
)


class RuntimeAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer runtime-test-token":
            return AuthenticatedActor(
                "runtime-operator",
                trust_level=2,
                permissions=frozenset(),
            )
        raise AssertionError("unexpected authorization")


def configure_production_environment(monkeypatch) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example.com/")
    monkeypatch.setenv("OIDC_AUDIENCE", "shema-business-platform")
    monkeypatch.setenv(
        "OIDC_JWKS_URL",
        "https://issuer.example.com/.well-known/jwks.json",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://app:secret@db.internal:5432/shema",
    )


def test_production_module_composes_provider_neutral_application(monkeypatch) -> None:
    configure_production_environment(monkeypatch)

    module = importlib.import_module("shema_platform.experience.production")

    assert isinstance(module.app.state.application, ProviderNeutralRuntimeApplication)


def test_provider_neutral_runtime_does_not_activate_external_capabilities(monkeypatch) -> None:
    configure_production_environment(monkeypatch)

    module = importlib.import_module("shema_platform.experience.production")
    application = module.app.state.application

    assert isinstance(application, ProviderNeutralRuntimeApplication)
    assert application._capabilities == {}


def test_production_runtime_serves_root_and_readiness(monkeypatch) -> None:
    configure_production_environment(monkeypatch)

    module = importlib.import_module("shema_platform.experience.production")
    client = TestClient(module.app)

    root = client.get("/")
    ready = client.get("/health/ready")

    assert root.status_code == 200
    assert "Shema" in root.text
    assert ready.status_code == 200
    assert ready.json() == {"ready": True}


def test_provider_neutral_application_fails_closed_for_uncomposed_capability() -> None:
    from shema_platform.experience.api import create_app

    client = TestClient(
        create_app(
            application=ProviderNeutralRuntimeApplication(),
            authenticator=RuntimeAuthenticator(),
        )
    )

    response = client.post(
        "/v1/search",
        headers={"Authorization": "Bearer runtime-test-token"},
        json={"region": "Moscow", "industries": ["logistics"]},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"


def test_provider_neutral_application_diagnostics_are_explicit() -> None:
    from shema_platform.experience.api import create_app
    from shema_platform.foundation.authorization import Permission

    class DiagnosticsAuthenticator(AuthenticationPort):
        def authenticate(self, authorization: str | None) -> AuthenticatedActor:
            return AuthenticatedActor(
                "runtime-operator",
                trust_level=2,
                permissions=frozenset({Permission.DIAGNOSTICS_READ}),
            )

    client = TestClient(
        create_app(
            application=ProviderNeutralRuntimeApplication(),
            authenticator=DiagnosticsAuthenticator(),
        )
    )

    response = client.get(
        "/v1/diagnostics",
        headers={"Authorization": "Bearer runtime-test-token"},
    )

    assert response.status_code == 200
    assert response.json()["healthy"] is True
    assert response.json()["checks"][0]["checkId"] == "canonical_application"
    assert response.json()["checks"][0]["status"] == "pass"
