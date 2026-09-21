from __future__ import annotations

import dataclasses
import typing

import jwt
from jwt import PyJWKClient, PyJWTError

import shema_platform.foundation.authentication as authentication
import shema_platform.foundation.authorization as authorization


_SAFE_ASYMMETRIC_ALGORITHMS = frozenset(
    {
        "RS256",
        "RS384",
        "RS512",
        "PS256",
        "PS384",
        "PS512",
        "ES256",
        "ES384",
        "ES512",
        "EdDSA",
    }
)


class SigningKeyProvider(typing.Protocol):
    """Resolves a verified issuer signing key without exposing IAM to the domain."""

    def signing_key(self, token: str) -> typing.Any: ...


@dataclasses.dataclass(frozen=True, slots=True)
class OIDCConfiguration:
    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    clock_skew_seconds: int = 30
    jwks_cache_seconds: int = 300
    actor_id_claim: str = "sub"
    trust_level_claim: str = "trust_level"
    permissions_claim: str = "permissions"

    def __post_init__(self) -> None:
        if not self.issuer.startswith("https://"):
            raise ValueError("OIDC issuer must use HTTPS")
        if not self.audience.strip():
            raise ValueError("OIDC audience is required")
        if not self.jwks_url.startswith("https://"):
            raise ValueError("OIDC JWKS URL must use HTTPS")
        if not self.algorithms or any(
            algorithm not in _SAFE_ASYMMETRIC_ALGORITHMS for algorithm in self.algorithms
        ):
            raise ValueError("OIDC algorithms must use an explicit asymmetric allow-list")
        if self.clock_skew_seconds < 0:
            raise ValueError("clock_skew_seconds cannot be negative")
        if self.jwks_cache_seconds <= 0:
            raise ValueError("jwks_cache_seconds must be positive")
        for name in (
            self.actor_id_claim,
            self.trust_level_claim,
            self.permissions_claim,
        ):
            if not name.strip():
                raise ValueError("OIDC claim names are required")


class PyJWTSigningKeyProvider:
    """Production JWKS resolver with bounded in-process key caching."""

    def __init__(self, jwks_url: str, cache_seconds: int) -> None:
        self._client = PyJWKClient(
            jwks_url,
            cache_jwk_set=True,
            lifespan=cache_seconds,
            cache_keys=True,
            max_cached_keys=16,
        )

    def signing_key(self, token: str) -> Any:
        return self._client.get_signing_key_from_jwt(token).key


@dataclass(frozen=True, slots=True)
class OIDCJWTAuthenticator:
    """Provider-neutral OIDC JWT verifier at the runtime adapter boundary."""

    configuration: OIDCConfiguration
    key_provider: SigningKeyProvider

    @classmethod
    def production(cls, configuration: OIDCConfiguration) -> OIDCJWTAuthenticator:
        return cls(
            configuration=configuration,
            key_provider=PyJWTSigningKeyProvider(
                configuration.jwks_url,
                configuration.jwks_cache_seconds,
            ),
        )

    def authenticate(self, authorization: str | None) -> authentication.AuthenticatedActor:
        token = self._bearer_token(authorization)
        try:
            signing_key = self.key_provider.signing_key(token)
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=self.configuration.algorithms,
                audience=self.configuration.audience,
                issuer=self.configuration.issuer,
                leeway=self.configuration.clock_skew_seconds,
                options={"require": ["exp", self.configuration.actor_id_claim]},
            )
        except (PyJWTError, ValueError, TypeError):
            raise authentication.AuthenticationRequired() from None

        actor_id = self._required_string_claim(
            claims,
            self.configuration.actor_id_claim,
        )
        trust_level = self._trust_level(claims)
        permissions = self._permissions(claims)

        return authentication.AuthenticatedActor(
            actor_id=actor_id,
            trust_level=trust_level,
            permissions=permissions,
        )

    @staticmethod
    def _bearer_token(authorization: str | None) -> str:
        if authorization is None:
            raise AuthenticationRequired()
        parts = authorization.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            raise AuthenticationRequired()
        return parts[1]

    @staticmethod
    def _required_string_claim(claims: dict[str, Any], name: str) -> str:
        value = claims.get(name)
        if not isinstance(value, str) or not value.strip():
            raise AuthenticationRequired()
        return value.strip()

    def _trust_level(self, claims: dict[str, Any]) -> int:
        value = claims.get(self.configuration.trust_level_claim, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AuthenticationRequired()
        return value

    def _permissions(self, claims: dict[str, Any]) -> frozenset[authorization.Permission]:
        value = claims.get(self.configuration.permissions_claim, ())
        if isinstance(value, str):
            raw = tuple(item for item in value.split() if item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            raw = tuple(value)
        else:
            raise AuthenticationRequired()

        permissions: set[authorization.Permission] = set()
        for item in raw:
            if not isinstance(item, str):
                raise AuthenticationRequired()
            try:
                permissions.add(authorization.Permission(item))
            except ValueError:
                raise AuthenticationRequired() from None
        return frozenset(permissions)
