from __future__ import annotations

import os
from dataclasses import dataclass
from urllib.parse import urlparse


class RuntimeSecurityViolation(RuntimeError):
    """Production runtime configuration is not safe to activate."""


@dataclass(frozen=True, slots=True)
class RuntimeSecurityConfiguration:
    environment: str
    docs_enabled: bool
    oidc_issuer: str | None
    oidc_audience: str | None
    oidc_jwks_url: str | None
    database_url: str | None

    @classmethod
    def from_environment(cls, *, docs_enabled: bool) -> "RuntimeSecurityConfiguration":
        return cls(
            environment=os.getenv("APP_ENV", "development").strip().lower(),
            docs_enabled=docs_enabled,
            oidc_issuer=os.getenv("OIDC_ISSUER"),
            oidc_audience=os.getenv("OIDC_AUDIENCE"),
            oidc_jwks_url=os.getenv("OIDC_JWKS_URL"),
            database_url=os.getenv("DATABASE_URL"),
        )

    def validate(self) -> tuple[str, ...]:
        if self.environment != "production":
            return ()

        failures: list[str] = []

        if self.docs_enabled:
            failures.append("production_docs_must_be_disabled")

        if not self.oidc_issuer:
            failures.append("production_oidc_issuer_required")
        elif not _is_https_endpoint(self.oidc_issuer):
            failures.append("production_oidc_issuer_must_be_https")

        if not self.oidc_audience or not self.oidc_audience.strip():
            failures.append("production_oidc_audience_required")

        if not self.oidc_jwks_url:
            failures.append("production_oidc_jwks_url_required")
        elif not _is_https_endpoint(self.oidc_jwks_url):
            failures.append("production_oidc_jwks_url_must_be_https")

        if not self.database_url or not self.database_url.strip():
            failures.append("production_database_url_required")
        elif self.database_url.strip() == _DEVELOPMENT_DATABASE_URL:
            failures.append("development_database_url_forbidden")

        return tuple(failures)

    def enforce(self) -> None:
        failures = self.validate()
        if failures:
            raise RuntimeSecurityViolation(", ".join(failures))


_DEVELOPMENT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/shema"


def _is_https_endpoint(value: str) -> bool:
    parsed = urlparse(value)
    return parsed.scheme == "https" and bool(parsed.netloc)
