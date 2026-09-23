import pytest

from shema_platform.foundation.telemetry import StructuredLoggingTelemetrySink
from shema_platform.foundation.runtime_security import (
    RuntimeSecurityConfiguration,
    RuntimeSecurityViolation,
)


def production(**overrides):
    values = {
        "environment": "production",
        "docs_enabled": False,
        "oidc_issuer": "https://issuer.example.com/",
        "oidc_audience": "shema-business-platform",
        "oidc_jwks_url": "https://issuer.example.com/.well-known/jwks.json",
        "database_url": "postgresql://app:secret@db.internal:5432/shema",
    }
    values.update(overrides)
    return RuntimeSecurityConfiguration(**values)


def test_production_configuration_is_safe_when_all_gates_pass() -> None:
    production().enforce()


@pytest.mark.parametrize(
    ("field", "value", "expected"),
    [
        ("docs_enabled", True, "production_docs_must_be_disabled"),
        ("oidc_issuer", "http://issuer.example.com/", "production_oidc_issuer_must_be_https"),
        ("oidc_audience", "", "production_oidc_audience_required"),
        (
            "oidc_jwks_url",
            "http://issuer.example.com/.well-known/jwks.json",
            "production_oidc_jwks_url_must_be_https",
        ),
        ("database_url", "", "production_database_url_required"),
        (
            "database_url",
            "postgresql://postgres:postgres@localhost:5432/shema",
            "development_database_url_forbidden",
        ),
    ],
)
def test_production_security_gate_fails_closed(field, value, expected) -> None:
    configuration = production(**{field: value})

    assert expected in configuration.validate()

    with pytest.raises(RuntimeSecurityViolation, match=expected):
        configuration.enforce()


def test_non_production_is_not_blocked_by_production_only_requirements() -> None:
    configuration = RuntimeSecurityConfiguration(
        environment="development",
        docs_enabled=True,
        oidc_issuer=None,
        oidc_audience=None,
        oidc_jwks_url=None,
        database_url="postgresql://postgres:postgres@localhost:5432/shema",
    )

    configuration.enforce()


def test_api_startup_enforces_production_security_from_environment(monkeypatch) -> None:
    from shema_platform.experience.api import create_app

    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("OIDC_ISSUER", "http://issuer.example.com/")
    monkeypatch.setenv("OIDC_AUDIENCE", "shema-business-platform")
    monkeypatch.setenv(
        "OIDC_JWKS_URL",
        "https://issuer.example.com/.well-known/jwks.json",
    )
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://app:secret@db.internal:5432/shema",
    )

    with pytest.raises(
        RuntimeSecurityViolation,
        match="production_oidc_issuer_must_be_https",
    ):
        create_app(enable_docs=False)


def test_api_startup_auto_wires_oidc_in_production(monkeypatch) -> None:
    from shema_platform.adapters.iam.oidc import OIDCJWTAuthenticator
    from shema_platform.experience.api import create_app

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

    app = create_app(enable_docs=False)

    assert isinstance(app.state.authenticator, OIDCJWTAuthenticator)
    assert app.state.authenticator.configuration.audience == "shema-business-platform"
    assert isinstance(app.state.telemetry, StructuredLoggingTelemetrySink)


def test_api_startup_allows_development_environment(monkeypatch) -> None:
    from shema_platform.experience.api import create_app

    monkeypatch.setenv("APP_ENV", "development")
    create_app(enable_docs=True)
