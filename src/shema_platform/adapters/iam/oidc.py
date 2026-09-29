from __future__ import annotations

import os
from dataclasses import dataclass
from threading import Lock
from time import monotonic
from typing import Any, NoReturn, Protocol

import jwt

MAX_BEARER_TOKEN_BYTES = 16_384

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


class SigningKeyProvider(Protocol):
    """Resolve an approved issuer signing key."""

    def signing_key(self, token: str) -> Any: ...


@dataclass(frozen=True, slots=True)
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

    @classmethod
    def from_environment(cls) -> OIDCConfiguration:
        """Build production OIDC configuration from environment variables."""

        values = {
            "issuer": os.getenv("OIDC_ISSUER", "").strip(),
            "audience": os.getenv("OIDC_AUDIENCE", "").strip(),
            "jwks_url": os.getenv("OIDC_JWKS_URL", "").strip(),
        }
        missing = tuple(name for name, value in values.items() if not value)
        if missing:
            raise ValueError(
                "missing OIDC environment configuration: " + ", ".join(missing)
            )
        return cls(**values)

    def __post_init__(self) -> None:
        issuer_url = urlsplit(self.issuer)
        jwks_url = urlsplit(self.jwks_url)
        if issuer_url.scheme != "https" or not issuer_url.hostname:
            raise ValueError("OIDC issuer must use HTTPS")
        if issuer_url.username or issuer_url.password or issuer_url.port:
            raise ValueError("OIDC issuer must not contain credentials or an explicit port")
        if not self.audience.strip():
            raise ValueError("OIDC audience is required")
        if jwks_url.scheme != "https" or not jwks_url.hostname:
            raise ValueError("OIDC JWKS URL must use HTTPS")
        if jwks_url.username or jwks_url.password or jwks_url.port:
            raise ValueError("OIDC JWKS URL must not contain credentials or an explicit port")
        if jwks_url.hostname != issuer_url.hostname:
            raise ValueError(
                "OIDC JWKS URL host must match the configured issuer host"
            )
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


class _BoundedPyJWKClient(jwt.PyJWKClient):
    """Bound forced JWKS refreshes caused by attacker-controlled unknown kid values."""

    def __init__(self, uri: str, cache_seconds: int) -> None:
        super().__init__(
            uri,
            cache_jwk_set=True,
            lifespan=cache_seconds,
            cache_keys=True,
            max_cached_keys=16,
        )
        self._refresh_lock = Lock()
        self._next_forced_refresh_at = 0.0
        self._refresh_cooldown_seconds = float(cache_seconds)

    def get_signing_key(self, kid: str):  # type: ignore[override]
        signing_keys = self.get_signing_keys()
        signing_key = self.match_kid(signing_keys, kid)
        if signing_key is not None:
            return signing_key

        now = monotonic()
        with self._refresh_lock:
            now = monotonic()
            if now < self._next_forced_refresh_at:
                raise jwt.PyJWKClientError(
                    "JWKS forced-refresh cooldown is active"
                )
            self._next_forced_refresh_at = (
                now + self._refresh_cooldown_seconds
            )
            signing_keys = self.get_signing_keys(refresh=True)

        signing_key = self.match_kid(signing_keys, kid)
        if signing_key is None:
            raise jwt.PyJWKClientError(
                f'Unable to find a signing key that matches: "{kid}"'
            )
        return signing_key


class PyJWTSigningKeyProvider:
    """Production JWKS resolver with bounded cache and unknown-kid refresh rate limiting."""

    UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS = 5.0

    def __init__(self, jwks_url: str, cache_seconds: int) -> None:
        self._client = _BoundedPyJWKClient(
            jwks_url,
            cache_seconds,
        )
        self._refresh_lock = Lock()
        self._last_unknown_kid_refresh_at = 0.0

    def signing_key(self, token: str) -> Any:
        header = jwt.get_unverified_header(token)
        kid = header.get("kid")
        if not isinstance(kid, str) or not kid.strip() or len(kid) > 256:
            raise jwt.PyJWKClientError("JWT signing key id is invalid")

        try:
            signing_keys = self._client.get_signing_keys(refresh=False)
            matched = next(
                (key for key in signing_keys if key.key_id == kid),
                None,
            )
            if matched is not None:
                return matched
        except jwt.PyJWTError:
            # Fall through to the bounded refresh path.
            pass

        now = monotonic()
        with self._refresh_lock:
            now = monotonic()
            if (
                now - self._last_unknown_kid_refresh_at
                < self.UNKNOWN_KID_REFRESH_COOLDOWN_SECONDS
            ):
                raise jwt.PyJWKClientError(
                    "unknown JWT key id refresh is rate limited"
                )

            self._last_unknown_kid_refresh_at = now
            return self._client.get_signing_key_from_jwt(token)


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

    def authenticate(self, authorization: str | None) -> Any:
        from shema_platform.foundation.authentication import AuthenticatedActor

        token = self._bearer_token(authorization)
        try:
            header = jwt.get_unverified_header(token)
            algorithm = header.get("alg")
            if algorithm not in self.configuration.algorithms:
                self._authentication_error()
            if header.get("crit"):
                # No critical extensions are supported until they have a dedicated verifier.
                self._authentication_error()

            signing_key = self.key_provider.signing_key(token)
            key_algorithm = getattr(signing_key, "algorithm_name", None)
            if key_algorithm is not None and key_algorithm != algorithm:
                self._authentication_error()

            raw_key = getattr(signing_key, "key", signing_key)
            claims = jwt.decode(
                token,
                raw_key,
                algorithms=(algorithm,),
                audience=self.configuration.audience,
                issuer=self.configuration.issuer,
                leeway=self.configuration.clock_skew_seconds,
                options={"require": ["exp", self.configuration.actor_id_claim]},
            )
        except (jwt.PyJWTError, ValueError, TypeError, AttributeError):
            self._authentication_error()

        actor_id = self._required_string_claim(
            claims,
            self.configuration.actor_id_claim,
        )
        trust_level = self._trust_level(claims)
        permissions = self._permissions(claims)

        return AuthenticatedActor(
            actor_id=actor_id,
            trust_level=trust_level,
            permissions=permissions,
        )

    @staticmethod
    def _authentication_error() -> NoReturn:
        from shema_platform.foundation.authentication import AuthenticationRequired

        raise AuthenticationRequired()

    @staticmethod
    def _bearer_token(authorization: str | None) -> str:
        if authorization is None:
            OIDCJWTAuthenticator._authentication_error()
        parts = authorization.strip().split()
        if len(parts) != 2 or parts[0].lower() != "bearer" or not parts[1]:
            OIDCJWTAuthenticator._authentication_error()
        token = parts[1]
        if len(token.encode("utf-8")) > MAX_BEARER_TOKEN_BYTES:
            OIDCJWTAuthenticator._authentication_error()
        return token

    @staticmethod
    def _required_string_claim(claims: dict[str, Any], name: str) -> str:
        value = claims.get(name)
        if not isinstance(value, str) or not value.strip():
            OIDCJWTAuthenticator._authentication_error()
        return value.strip()

    def _trust_level(self, claims: dict[str, Any]) -> int:
        value = claims.get(self.configuration.trust_level_claim, 0)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            OIDCJWTAuthenticator._authentication_error()
        return value

    def _permissions(self, claims: dict[str, Any]) -> frozenset[Any]:
        from shema_platform.foundation.authorization import Permission

        value = claims.get(self.configuration.permissions_claim, ())
        if isinstance(value, str):
            raw = tuple(item for item in value.split() if item)
        elif isinstance(value, (list, tuple, set, frozenset)):
            raw = tuple(value)
        else:
            OIDCJWTAuthenticator._authentication_error()

        permissions: set[Permission] = set()
        for item in raw:
            if not isinstance(item, str):
                OIDCJWTAuthenticator._authentication_error()
            try:
                permissions.add(Permission(item))
            except ValueError:
                OIDCJWTAuthenticator._authentication_error()
        return frozenset(permissions)
