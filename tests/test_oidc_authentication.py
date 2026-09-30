from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from shema_platform.adapters.iam.oidc import (
    OIDCConfiguration,
    OIDCJWTAuthenticator,
)
from shema_platform.foundation.authentication import AuthenticationRequired
from shema_platform.foundation.authorization import Permission


class FakeSigningKeyProvider:
    def __init__(self, key: object) -> None:
        self.key = key

    def signing_key(self, token: str) -> object:
        return self.key


@pytest.fixture()
def key_pair():
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return private_key, private_key.public_key()


@pytest.fixture()
def authenticator(key_pair):
    private_key, public_key = key_pair
    configuration = OIDCConfiguration(
        issuer="https://issuer.example.test",
        audience="shema-business-platform",
        jwks_url="https://issuer.example.test/.well-known/jwks.json",
    )
    return (
        OIDCJWTAuthenticator(
            configuration=configuration,
            key_provider=FakeSigningKeyProvider(public_key),
        ),
        private_key,
    )


def token(private_key, **overrides) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://issuer.example.test",
        "aud": "shema-business-platform",
        "sub": "operator-1",
        "trust_level": 2,
        "permissions": [
            Permission.ORDER_CREATE.value,
            Permission.COMMERCIAL_ACTION_SEND.value,
        ],
        "iat": now,
        "exp": now + timedelta(minutes=5),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256")


def test_oidc_authentication_verifies_signature_issuer_audience_and_claims(authenticator) -> None:
    verifier, private_key = authenticator

    actor = verifier.authenticate(f"Bearer {token(private_key)}")

    assert actor.actor_id == "operator-1"
    assert actor.trust_level == 2
    assert actor.permissions == frozenset(
        {
            Permission.ORDER_CREATE,
            Permission.COMMERCIAL_ACTION_SEND,
        }
    )


def test_oidc_rejects_missing_bearer_token(authenticator) -> None:
    verifier, _ = authenticator

    with pytest.raises(AuthenticationRequired):
        verifier.authenticate(None)


@pytest.mark.parametrize(
    "authorization",
    [
        "",
        "Basic abc",
        "Bearer",
        "Bearer one two",
    ],
)
def test_oidc_rejects_malformed_authorization(authorization, authenticator) -> None:
    verifier, _ = authenticator

    with pytest.raises(AuthenticationRequired):
        verifier.authenticate(authorization)


def test_oidc_rejects_wrong_issuer(authenticator) -> None:
    verifier, private_key = authenticator

    with pytest.raises(AuthenticationRequired):
        verifier.authenticate(
            f"Bearer {token(private_key, iss='https://evil.example.test')}"
        )


def test_oidc_rejects_wrong_audience(authenticator) -> None:
    verifier, private_key = authenticator

    with pytest.raises(AuthenticationRequired):
        verifier.authenticate(
            f"Bearer {token(private_key, aud='other-service')}"
        )


def test_oidc_rejects_expired_token(authenticator) -> None:
    verifier, private_key = authenticator
    now = datetime.now(UTC)

    with pytest.raises(AuthenticationRequired):
        verifier.authenticate(
            f"Bearer {token(private_key, exp=now - timedelta(seconds=31))}"
        )


def test_oidc_rejects_unknown_permission(authenticator) -> None:
    verifier, private_key = authenticator

    with pytest.raises(AuthenticationRequired):
        verifier.authenticate(
            f"Bearer {token(private_key, permissions=['operator.superuser'])}"
        )


def test_oidc_configuration_loads_from_environment(monkeypatch) -> None:
    monkeypatch.setenv("OIDC_ISSUER", "https://issuer.example.test/")
    monkeypatch.setenv("OIDC_AUDIENCE", "shema-business-platform")
    monkeypatch.setenv(
        "OIDC_JWKS_URL",
        "https://issuer.example.test/.well-known/jwks.json",
    )

    configuration = OIDCConfiguration.from_environment()

    assert configuration.issuer == "https://issuer.example.test/"
    assert configuration.audience == "shema-business-platform"
    assert configuration.jwks_url.endswith("/.well-known/jwks.json")


def test_oidc_configuration_rejects_missing_environment(monkeypatch) -> None:
    for name in ("OIDC_ISSUER", "OIDC_AUDIENCE", "OIDC_JWKS_URL"):
        monkeypatch.delenv(name, raising=False)

    with pytest.raises(ValueError, match="missing OIDC environment configuration"):
        OIDCConfiguration.from_environment()


def test_oidc_requires_https_and_safe_algorithms() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        OIDCConfiguration(
            issuer="http://issuer.example.test",
            audience="shema-business-platform",
            jwks_url="https://issuer.example.test/.well-known/jwks.json",
        )

    with pytest.raises(ValueError, match="asymmetric"):
        OIDCConfiguration(
            issuer="https://issuer.example.test",
            audience="shema-business-platform",
            jwks_url="https://issuer.example.test/.well-known/jwks.json",
            algorithms=("HS256",),
        )
