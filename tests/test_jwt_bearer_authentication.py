from datetime import UTC, datetime, timedelta

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import rsa

from shema_platform.adapters.identity.jwt_bearer import (
    JWTAuthenticationConfig,
    JWTBearerAuthentication,
)
from shema_platform.foundation.authentication import AuthenticationRequired


class FakeSigningKey:
    def __init__(self, key: object) -> None:
        self.key = key


class FakeJWKClient:
    def __init__(self, key: object) -> None:
        self.key = key

    def get_signing_key_from_jwt(self, token: str) -> FakeSigningKey:
        return FakeSigningKey(self.key)


def token(private_key: object, **overrides: object) -> str:
    now = datetime.now(UTC)
    claims = {
        "iss": "https://issuer.example",
        "sub": "operator-1",
        "aud": "shema-api",
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=5)).timestamp()),
    }
    claims.update(overrides)
    return jwt.encode(claims, private_key, algorithm="RS256", headers={"kid": "key-1"})


def authenticator(
    private_key: object,
    **config_overrides: object,
) -> JWTBearerAuthentication:
    config = JWTAuthenticationConfig(
        issuer="https://issuer.example",
        audience="shema-api",
        jwks_url="https://issuer.example/.well-known/jwks.json",
        **config_overrides,
    )
    return JWTBearerAuthentication(
        config,
        jwks_client=FakeJWKClient(private_key.public_key()),
    )


def test_valid_bearer_jwt_authenticates() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    actor = authenticator(private_key).authenticate(
        "Bearer " + token(private_key),
    )

    assert actor.actor_id == "operator-1"
    assert actor.trust_level == 0


def test_trust_level_is_explicitly_mapped_when_configured() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    actor = authenticator(
        private_key,
        trust_level_claim="trust_level",
    ).authenticate(
        "Bearer " + token(private_key, trust_level=2),
    )

    assert actor.trust_level == 2


@pytest.mark.parametrize(
    "authorization",
    [None, "", "Basic abc", "Bearer", "Bearer ", "Bearer one token"],
)
def test_malformed_bearer_header_is_rejected(authorization: str | None) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(AuthenticationRequired):
        authenticator(private_key).authenticate(authorization)


def test_expired_token_is_rejected() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    expired = token(
        private_key,
        exp=int((datetime.now(UTC) - timedelta(minutes=1)).timestamp()),
    )

    with pytest.raises(AuthenticationRequired):
        authenticator(private_key).authenticate("Bearer " + expired)


@pytest.mark.parametrize(
    "claim, value",
    [("iss", "https://other.example"), ("aud", "other-api")],
)
def test_wrong_issuer_or_audience_is_rejected(claim: str, value: str) -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(AuthenticationRequired):
        authenticator(private_key).authenticate(
            "Bearer " + token(private_key, **{claim: value}),
        )


def test_roles_and_scopes_are_extracted_without_becoming_permissions() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    actor = authenticator(
        private_key,
        roles_claim="roles",
        scopes_claim="scope",
    ).authenticate(
        "Bearer " + token(
            private_key,
            roles=["operator", "dispatcher"],
            scope="orders:read orders:write",
        ),
    )

    assert actor.roles == ("operator", "dispatcher")
    assert actor.scopes == ("orders:read", "orders:write")


def test_invalid_configured_authorization_claims_fail_closed() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(AuthenticationRequired):
        authenticator(
            private_key,
            roles_claim="roles",
        ).authenticate(
            "Bearer " + token(private_key, roles="operator"),
        )


def test_invalid_trust_level_is_rejected() -> None:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

    with pytest.raises(AuthenticationRequired):
        authenticator(
            private_key,
            trust_level_claim="trust_level",
        ).authenticate(
            "Bearer " + token(private_key, trust_level="admin"),
        )


def test_config_requires_https_for_issuer_and_jwks() -> None:
    with pytest.raises(ValueError, match="HTTPS"):
        JWTAuthenticationConfig(
            issuer="http://issuer.example",
            audience="shema-api",
            jwks_url="https://issuer.example/jwks",
        )
