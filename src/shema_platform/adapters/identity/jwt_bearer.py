from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from urllib.parse import urlparse

import jwt
from jwt import PyJWKClient
from jwt.exceptions import InvalidTokenError, PyJWKClientError

from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)

_SUPPORTED_JWKS_ALGORITHMS = frozenset(
    {"RS256", "RS384", "RS512", "ES256", "ES384", "ES512", "EdDSA"}
)


@dataclass(frozen=True, slots=True)
class JWTAuthenticationConfig:
    """Provider-neutral JWT/JWKS verification settings."""

    issuer: str
    audience: str
    jwks_url: str
    algorithms: tuple[str, ...] = ("RS256",)
    leeway_seconds: int = 30
    trust_level_claim: str | None = None

    def __post_init__(self) -> None:
        for name, value in (
            ("issuer", self.issuer),
            ("audience", self.audience),
            ("jwks_url", self.jwks_url),
        ):
            if not value.strip():
                raise ValueError(f"{name} is required")

        issuer = urlparse(self.issuer)
        jwks = urlparse(self.jwks_url)
        if issuer.scheme != "https" or not issuer.netloc or issuer.query or issuer.fragment:
            raise ValueError("issuer must be an HTTPS URL without query or fragment")
        if jwks.scheme != "https" or not jwks.netloc or jwks.query or jwks.fragment:
            raise ValueError("jwks_url must be an HTTPS URL without query or fragment")

        if not self.algorithms:
            raise ValueError("at least one JWT algorithm is required")
        if any(algorithm not in _SUPPORTED_JWKS_ALGORITHMS for algorithm in self.algorithms):
            raise ValueError("unsupported JWT algorithm")
        if self.leeway_seconds < 0:
            raise ValueError("leeway_seconds cannot be negative")
        if self.trust_level_claim is not None and not self.trust_level_claim.strip():
            raise ValueError("trust_level_claim cannot be empty")


class SigningKeyClient(Protocol):
    """Narrow JWKS boundary so authentication stays independently testable."""

    def get_signing_key_from_jwt(self, token: str) -> object: ...


class JWTBearerAuthentication(AuthenticationPort):
    """Production JWT bearer adapter with fail-closed token validation."""

    def __init__(
        self,
        config: JWTAuthenticationConfig,
        *,
        jwks_client: SigningKeyClient | None = None,
    ) -> None:
        self._config = config
        self._jwks_client = jwks_client or PyJWKClient(
            config.jwks_url,
            cache_jwk_set=True,
            lifespan=300,
            cache_keys=True,
            timeout=5,
            cooldown_duration=30,
        )

    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        token = self._extract_bearer_token(authorization)
        try:
            signing_key = self._jwks_client.get_signing_key_from_jwt(token)
            claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=list(self._config.algorithms),
                audience=self._config.audience,
                issuer=self._config.issuer,
                leeway=self._config.leeway_seconds,
                options={"require": ["exp", "iss", "sub", "aud"]},
            )
        except (
            InvalidTokenError,
            PyJWKClientError,
            AttributeError,
            TypeError,
            ValueError,
        ) as exc:
            raise AuthenticationRequired() from exc

        actor_id = claims.get("sub")
        if not isinstance(actor_id, str) or not actor_id.strip():
            raise AuthenticationRequired()

        trust_level = self._trust_level(claims)
        return AuthenticatedActor(actor_id=actor_id, trust_level=trust_level)

    @staticmethod
    def _extract_bearer_token(authorization: str | None) -> str:
        if authorization is None:
            raise AuthenticationRequired()

        parts = authorization.split(" ", 1)
        if len(parts) != 2 or parts[0].lower() != "bearer":
            raise AuthenticationRequired()

        token = parts[1].strip()
        if not token or any(char.isspace() for char in token):
            raise AuthenticationRequired()
        return token

    def _trust_level(self, claims: dict[str, object]) -> int:
        claim = self._config.trust_level_claim
        if claim is None:
            return 0

        value = claims.get(claim)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise AuthenticationRequired()
        return value
