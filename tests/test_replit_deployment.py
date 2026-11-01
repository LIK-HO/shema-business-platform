from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from deploy.replit.preflight import (
    validate_environment,
    validate_migration_ledger,
    validate_runtime_application,
)
from shema_platform.platform.migrations import Migration, MigrationPlan


ROOT = Path(__file__).resolve().parents[1]


def production_environment(**overrides: str) -> dict[str, str]:
    values = {
        "APP_ENV": "production",
        "REPLIT_DATA_MODE": "synthetic_only",
        "DATABASE_URL": (
            "postgresql://operator:secret@db.example.test:5432/shema"
            "?sslmode=require"
        ),
        "OIDC_ISSUER": "https://identity.example.test/",
        "OIDC_AUDIENCE": "shema-business-platform",
        "OIDC_JWKS_URL": "https://identity.example.test/.well-known/jwks.json",
        "PORT": "8080",
    }
    values.update(overrides)
    return values


def test_replit_environment_accepts_complete_synthetic_production_configuration() -> None:
    assert validate_environment(production_environment()) == ()


def test_replit_environment_fails_closed_without_synthetic_data_declaration() -> None:
    failures = validate_environment(production_environment(REPLIT_DATA_MODE="real_data"))

    assert failures == ("replit_data_mode_must_be_synthetic_only",)


def test_replit_environment_rejects_development_and_local_database() -> None:
    failures = validate_environment(
        production_environment(
            APP_ENV="development",
            DATABASE_URL="postgresql://postgres:postgres@localhost:5432/shema",
        )
    )

    assert "app_env_must_be_production" in failures
    assert "local_database_host_forbidden" in failures


def test_replit_environment_requires_postgresql_and_secure_oidc() -> None:
    failures = validate_environment(
        production_environment(
            DATABASE_URL="sqlite:///tmp/shema.db",
            OIDC_ISSUER="http://identity.example.test/",
            OIDC_JWKS_URL="http://identity.example.test/jwks",
            OIDC_AUDIENCE="",
        )
    )

    assert "database_url_must_be_postgresql" in failures
    assert "oidc_audience_required" in failures
    assert "oidc_endpoints_must_use_https" in failures


def test_replit_environment_rejects_jwks_authority_mismatch_and_invalid_port() -> None:
    failures = validate_environment(
        production_environment(
            OIDC_JWKS_URL="https://other.example.test/jwks",
            PORT="not-a-port",
        )
    )

    assert "oidc_endpoint_authority_mismatch" in failures
    assert "port_must_be_integer" in failures


def test_runtime_application_gate_rejects_uncomposed_production_app() -> None:
    app = SimpleNamespace(
        state=SimpleNamespace(
            application=None,
            authenticator=object(),
            resource_read_authorizer=None,
            telemetry=object(),
        )
    )

    assert validate_runtime_application(app) == (
        "production_application_not_composed",
        "production_resource_read_authorizer_not_composed",
    )


def test_runtime_application_gate_accepts_required_composition() -> None:
    app = SimpleNamespace(
        state=SimpleNamespace(
            application=object(),
            authenticator=object(),
            resource_read_authorizer=object(),
            telemetry=object(),
        )
    )

    assert validate_runtime_application(app) == ()


def sample_plan() -> MigrationPlan:
    return MigrationPlan(
        (
            Migration(version=1, name="foundation", sql="create table example(id int);"),
            Migration(version=2, name="audit", sql="alter table example add column note text;"),
        )
    )


def test_migration_ledger_requires_exact_ordered_checksums() -> None:
    plan = sample_plan()
    rows = [
        (migration.version, migration.name, migration.checksum)
        for migration in plan.migrations
    ]

    assert validate_migration_ledger(rows, plan) == ()


def test_migration_ledger_rejects_gaps_duplicates_checksum_changes_and_pending() -> None:
    plan = sample_plan()
    first, second = plan.migrations

    assert validate_migration_ledger(
        [(2, second.name, second.checksum)],
        plan,
    ) == ("database_migration_ledger_has_gap",)

    assert validate_migration_ledger(
        [
            (1, first.name, first.checksum),
            (1, first.name, first.checksum),
        ],
        plan,
    ) == ("database_migration_ledger_duplicate_version",)

    assert validate_migration_ledger(
        [
            (1, first.name, "incorrect"),
            (2, second.name, second.checksum),
        ],
        plan,
    ) == ("database_migration_checksum_mismatch",)

    assert validate_migration_ledger(
        [(1, first.name, first.checksum)],
        plan,
    ) == ("database_migrations_pending",)


def test_actual_repository_migration_plan_is_contiguous_and_nonempty() -> None:
    plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")

    assert len(plan.migrations) >= 9
    assert [item.version for item in plan.migrations] == list(
        range(1, len(plan.migrations) + 1)
    )
