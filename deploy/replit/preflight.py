from __future__ import annotations

import os
import sys
from collections.abc import Callable, Mapping
from pathlib import Path
from urllib.parse import urlsplit

from shema_platform.platform.migrations import MigrationPlan


DEVELOPMENT_DATABASE_URL = "postgresql://postgres:postgres@localhost:5432/shema"
REPOSITORY_ROOT = Path(__file__).resolve().parents[2]


def validate_environment(environ: Mapping[str, str]) -> tuple[str, ...]:
    failures: list[str] = []

    if environ.get("APP_ENV", "").strip().lower() != "production":
        failures.append("app_env_must_be_production")

    if environ.get("REPLIT_DATA_MODE", "").strip().lower() != "synthetic_only":
        failures.append("replit_data_mode_must_be_synthetic_only")

    database_url = environ.get("DATABASE_URL", "").strip()
    if not database_url:
        failures.append("database_url_required")
    elif database_url == DEVELOPMENT_DATABASE_URL:
        failures.append("development_database_url_forbidden")
    else:
        parsed = urlsplit(database_url)
        if parsed.scheme not in {"postgres", "postgresql"} or not parsed.hostname:
            failures.append("database_url_must_be_postgresql")
        elif parsed.hostname.lower() in {"localhost", "127.0.0.1", "::1"}:
            failures.append("local_database_host_forbidden")

    issuer = environ.get("OIDC_ISSUER", "").strip()
    audience = environ.get("OIDC_AUDIENCE", "").strip()
    jwks_url = environ.get("OIDC_JWKS_URL", "").strip()

    if not issuer:
        failures.append("oidc_issuer_required")
    if not audience:
        failures.append("oidc_audience_required")
    if not jwks_url:
        failures.append("oidc_jwks_url_required")

    if issuer and jwks_url:
        issuer_url = urlsplit(issuer)
        jwks = urlsplit(jwks_url)
        if (
            issuer_url.scheme != "https"
            or jwks.scheme != "https"
            or not issuer_url.hostname
            or not jwks.hostname
        ):
            failures.append("oidc_endpoints_must_use_https")
        elif (
            issuer_url.hostname.lower() != jwks.hostname.lower()
            or issuer_url.username
            or issuer_url.password
            or issuer_url.port
            or jwks.username
            or jwks.password
            or jwks.port
        ):
            failures.append("oidc_endpoint_authority_mismatch")

    raw_port = environ.get("PORT", "8080").strip()
    try:
        port = int(raw_port)
    except ValueError:
        failures.append("port_must_be_integer")
    else:
        if not 1 <= port <= 65535:
            failures.append("port_out_of_range")

    return tuple(failures)


def validate_runtime_application(app: object) -> tuple[str, ...]:
    state = getattr(app, "state", None)
    if state is None:
        return ("production_app_state_missing",)

    failures: list[str] = []
    if getattr(state, "application", None) is None:
        failures.append("production_application_not_composed")
    if getattr(state, "authenticator", None) is None:
        failures.append("production_authenticator_not_composed")
    if getattr(state, "resource_read_authorizer", None) is None:
        failures.append("production_resource_read_authorizer_not_composed")
    if getattr(state, "telemetry", None) is None:
        failures.append("production_telemetry_not_composed")
    return tuple(failures)


def validate_migration_ledger(
    applied_rows: list[tuple[int, str, str]],
    plan: MigrationPlan,
) -> tuple[str, ...]:
    expected = {
        migration.version: (migration.name, migration.checksum)
        for migration in plan.migrations
    }
    actual: dict[int, tuple[str, str]] = {}
    for version, name, checksum in applied_rows:
        if version in actual:
            return ("database_migration_ledger_duplicate_version",)
        actual[int(version)] = (str(name), str(checksum))

    if not actual:
        return ("database_migration_ledger_empty",)

    versions = sorted(actual)
    if versions != list(range(1, len(versions) + 1)):
        return ("database_migration_ledger_has_gap",)

    for version, value in actual.items():
        if expected.get(version) != value:
            return ("database_migration_checksum_mismatch",)

    if set(actual) != set(expected):
        return ("database_migrations_pending",)

    return ()


def validate_database(
    database_url: str,
    *,
    root: Path = REPOSITORY_ROOT,
    connect: Callable | None = None,
) -> tuple[str, ...]:
    try:
        if connect is None:
            import psycopg

            connect = psycopg.connect

        plan = MigrationPlan.from_directory(root / "db" / "migrations")
        connection = connect(database_url, connect_timeout=5)
        try:
            rows = connection.execute(
                """
                select version, name, checksum
                from schema_migration
                order by version
                """
            ).fetchall()
        finally:
            connection.close()
        return validate_migration_ledger(
            [(int(row[0]), str(row[1]), str(row[2])) for row in rows],
            plan,
        )
    except Exception:
        # Never print a driver exception here: it may contain the database URL.
        return ("database_connection_or_schema_check_failed",)


def startup_failures(
    environ: Mapping[str, str],
    app: object,
    *,
    root: Path = REPOSITORY_ROOT,
    connect: Callable | None = None,
) -> tuple[str, ...]:
    failures = list(validate_environment(environ))
    if failures:
        return tuple(failures)

    failures.extend(validate_runtime_application(app))
    if failures:
        return tuple(failures)

    database_url = environ["DATABASE_URL"].strip()
    failures.extend(validate_database(database_url, root=root, connect=connect))
    return tuple(failures)


def main() -> int:
    environment = os.environ
    environment_failures = validate_environment(environment)
    if environment_failures:
        print("REPLIT_STARTUP_BLOCKED: " + ",".join(environment_failures), file=sys.stderr)
        return 78

    try:
        from shema_platform.experience.production import app
    except Exception as exc:
        print(
            "REPLIT_STARTUP_BLOCKED: production_app_import_failed:"
            + type(exc).__name__,
            file=sys.stderr,
        )
        return 78

    failures = startup_failures(environment, app)
    if failures:
        print("REPLIT_STARTUP_BLOCKED: " + ",".join(failures), file=sys.stderr)
        return 78

    print("REPLIT_STARTUP_PREFLIGHT: passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
