from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path

from shema_platform.platform.postgres import DBConnection


class MigrationError(RuntimeError):
    """Base migration safety error."""


class MigrationIntegrityError(MigrationError):
    """A previously applied migration differs from the approved checksum."""


class MigrationPlanError(MigrationError):
    """The migration set is invalid or contains a gap."""


class MigrationBaselineError(MigrationError):
    """An existing schema cannot be safely adopted into the migration ledger."""


@dataclass(frozen=True, slots=True)
class Migration:
    version: int
    name: str
    sql: str

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("migration version must be >= 1")
        if not self.name.strip():
            raise ValueError("migration name is required")
        if not self.sql.strip():
            raise ValueError("migration SQL is required")

    @property
    def checksum(self) -> str:
        return sha256(self.sql.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class MigrationPlan:
    migrations: tuple[Migration, ...]

    def __post_init__(self) -> None:
        versions = [migration.version for migration in self.migrations]
        if versions != sorted(versions):
            raise MigrationPlanError("migrations must be ordered by version")
        if len(versions) != len(set(versions)):
            raise MigrationPlanError("migration versions must be unique")
        if versions and versions != list(range(1, len(versions) + 1)):
            raise MigrationPlanError("migration versions must be contiguous from 1")

    @classmethod
    def from_directory(cls, directory: Path) -> MigrationPlan:
        pattern = re.compile(r"^(?P<version>\d{4})_(?P<name>[a-z0-9_]+)\.sql$")
        migrations: list[Migration] = []

        for path in sorted(directory.glob("*.sql")):
            match = pattern.fullmatch(path.name)
            if match is None:
                raise MigrationPlanError(
                    f"migration filename is invalid: {path.name}"
                )
            migrations.append(
                Migration(
                    version=int(match.group("version")),
                    name=match.group("name"),
                    sql=path.read_text(encoding="utf-8"),
                )
            )

        return cls(tuple(migrations))


@dataclass(frozen=True, slots=True)
class MigrationReport:
    applied: tuple[int, ...]
    current_version: int


V1_4_BASELINE_VERSION = 8
_V1_4_REQUIRED_COLUMNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "identity",
        (
            "identity_id",
            "canonical_name",
            "state",
            "tax_id",
            "registration_id",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "evidence",
        (
            "evidence_id",
            "subject_ref",
            "claim",
            "source_ref",
            "truth_class",
            "trust_level",
            "confidence",
            "provenance",
            "observed_at",
            "captured_at",
            "expires_at",
            "lifecycle",
        ),
    ),
    (
        "idempotency_key",
        ("key", "request_hash", "result_ref", "created_at"),
    ),
    (
        "audit_log",
        (
            "audit_id",
            "actor_id",
            "action",
            "resource_type",
            "resource_id",
            "outcome",
            "occurred_at",
            "metadata",
            "correlation_id",
            "configuration_version",
        ),
    ),
    (
        "outbox_event",
        (
            "event_id",
            "event_type",
            "aggregate_type",
            "aggregate_id",
            "payload",
            "occurred_at",
            "published_at",
            "delivery_attempt",
            "delivery_worker_id",
            "delivery_lease_until",
        ),
    ),
    (
        "search_candidate",
        (
            "candidate_id",
            "candidate_ref",
            "name",
            "region",
            "selection_level",
            "source_ref",
            "tax_id",
            "registration_id",
            "contact_refs",
            "raw_payload",
            "observed_at",
            "captured_at",
            "lifecycle",
            "created_at",
        ),
    ),
    (
        "quarantine_record",
        (
            "quarantine_id",
            "object_type",
            "object_ref",
            "reason_code",
            "payload",
            "created_at",
            "resolved_at",
            "resolution",
        ),
    ),
    (
        "commercial_action",
        (
            "action_id",
            "identity_id",
            "contact_ref",
            "channel",
            "evidence_refs",
            "status",
            "created_at",
            "updated_at",
            "send_attempt",
            "send_worker_id",
            "send_lease_until",
        ),
    ),
    (
        "order_header",
        (
            "order_id",
            "identity_id",
            "source_action_id",
            "status",
            "created_at",
            "updated_at",
        ),
    ),
    (
        "order_line",
        (
            "line_id",
            "order_id",
            "description",
            "quantity",
            "unit_price",
            "currency",
            "created_at",
        ),
    ),
    (
        "economic_entry",
        (
            "entry_id",
            "entity_ref",
            "kind",
            "amount",
            "currency",
            "source_ref",
            "occurred_at",
        ),
    ),
    (
        "ai_run",
        (
            "run_id",
            "task_id",
            "provider_id",
            "model",
            "model_version",
            "prompt_version",
            "input_refs",
            "evidence_refs",
            "output",
            "tokens",
            "cost",
            "duration_seconds",
            "created_at",
        ),
    ),
    (
        "job_execution",
        (
            "job_id",
            "job_type",
            "attempt",
            "state",
            "idempotency_key",
            "payload",
            "available_at",
            "worker_id",
            "lease_until",
            "last_error",
            "completed_at",
            "created_at",
            "updated_at",
        ),
    ),
)


class MigrationRunner:
    """Apply or safely adopt an ordered migration plan under one PostgreSQL transaction."""

    LEDGER_SQL = """
        create table if not exists schema_migration (
            version integer primary key check (version >= 1),
            name text not null unique,
            checksum text not null,
            applied_at timestamptz not null default now()
        )
    """
    LOCK_SQL = """
        select pg_advisory_xact_lock(
            hashtextextended('shema:schema_migrations', 0)
        )
    """

    def __init__(
        self,
        connection_factory: Callable[[], DBConnection],
        plan: MigrationPlan,
    ) -> None:
        self._connection_factory = connection_factory
        self._plan = plan

    def apply(self) -> MigrationReport:
        connection = self._connection_factory()
        try:
            connection.execute(self.LOCK_SQL)
            connection.execute(self.LEDGER_SQL)

            applied = self._read_applied(connection)
            self._validate_applied_ledger(applied)

            applied_now: list[int] = []
            for migration in self._plan.migrations:
                existing = applied.get(migration.version)
                if existing is not None:
                    existing_name, existing_checksum = existing
                    if existing_name != migration.name or existing_checksum != migration.checksum:
                        raise MigrationIntegrityError(
                            "applied migration differs from approved checksum: "
                            f"{migration.version:04d}_{migration.name}"
                        )
                    continue

                connection.execute(migration.sql)
                connection.execute(
                    """
                    insert into schema_migration (version, name, checksum)
                    values (%s, %s, %s)
                    """,
                    (migration.version, migration.name, migration.checksum),
                )
                applied_now.append(migration.version)

            connection.commit()
            return MigrationReport(
                applied=tuple(applied_now),
                current_version=(
                    self._plan.migrations[-1].version
                    if self._plan.migrations
                    else 0
                ),
            )
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def adopt_existing_schema(
        self,
        baseline_version: int = V1_4_BASELINE_VERSION,
    ) -> MigrationReport:
        """Adopt a verified legacy schema without re-running historical DDL.

        The v1.4 baseline is intentionally fixed at migration 0008. Adoption
        verifies required schema-owned columns, transactionally bootstraps
        immutable ledger rows for 0001-0008, and leaves later migrations for
        the normal runner. This closes the destructive-reapply path.
        """
        if baseline_version != V1_4_BASELINE_VERSION:
            raise MigrationBaselineError(
                f"only v1.4 baseline adoption at version {V1_4_BASELINE_VERSION} is supported"
            )
        if len(self._plan.migrations) < baseline_version:
            raise MigrationBaselineError(
                "current migration plan does not contain the complete v1.4 baseline"
            )

        connection = self._connection_factory()
        try:
            connection.execute(self.LOCK_SQL)
            ledger_exists = connection.execute(
                "select to_regclass(%s)",
                (f"{self._current_schema(connection)}.schema_migration",),
            ).fetchone()

            if ledger_exists is not None and ledger_exists[0] is not None:
                existing_rows = connection.execute(
                    """
                    select version, name, checksum
                    from schema_migration
                    order by version
                    """
                ).fetchall()
                if existing_rows:
                    raise MigrationBaselineError(
                        "existing migration ledger is populated; use normal migration apply"
                    )

            self._verify_v1_4_schema(connection)
            connection.execute(self.LEDGER_SQL)

            for migration in self._plan.migrations[:baseline_version]:
                connection.execute(
                    """
                    insert into schema_migration (version, name, checksum)
                    values (%s, %s, %s)
                    """,
                    (migration.version, migration.name, migration.checksum),
                )

            connection.commit()
            return MigrationReport(applied=(), current_version=baseline_version)
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    @staticmethod
    def _current_schema(connection: DBConnection) -> str:
        row = connection.execute("select current_schema()").fetchone()
        if row is None or row[0] is None:
            raise MigrationBaselineError("current PostgreSQL schema is not defined")
        return str(row[0])

    @staticmethod
    def _read_applied(connection: DBConnection) -> dict[int, tuple[str, str]]:
        rows = connection.execute(
            """
            select version, name, checksum
            from schema_migration
            order by version
            """
        ).fetchall()
        return {
            int(version): (str(name), str(checksum))
            for version, name, checksum in rows
        }

    def _validate_applied_ledger(
        self,
        applied: dict[int, tuple[str, str]],
    ) -> None:
        applied_versions = sorted(applied)
        if not applied_versions:
            return

        expected_versions = list(range(1, applied_versions[-1] + 1))
        if applied_versions != expected_versions:
            raise MigrationIntegrityError(
                "applied migration ledger contains a version gap"
            )
        plan_versions = {migration.version for migration in self._plan.migrations}
        unknown_versions = set(applied_versions) - plan_versions
        if unknown_versions:
            raise MigrationIntegrityError(
                "applied migration is missing from current plan: "
                + ", ".join(str(version) for version in sorted(unknown_versions))
            )

    @staticmethod
    def _verify_v1_4_schema(connection: DBConnection) -> None:
        schema = MigrationRunner._current_schema(connection)
        rows = connection.execute(
            """
            select table_name, column_name
            from information_schema.columns
            where table_schema = %s
            """,
            (schema,),
        ).fetchall()
        actual = {(str(table), str(column)) for table, column in rows}

        missing = sorted(
            f"{table}.{column}"
            for table, columns in _V1_4_REQUIRED_COLUMNS
            for column in columns
            if (table, column) not in actual
        )
        if missing:
            preview = ", ".join(missing[:8])
            suffix = " ..." if len(missing) > 8 else ""
            raise MigrationBaselineError(
                "existing schema is not compatible with v1.4 baseline; "
                f"missing required columns: {preview}{suffix}"
            )
