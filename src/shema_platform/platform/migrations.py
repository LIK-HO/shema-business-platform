from __future__ import annotations

import re
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import Callable

from shema_platform.platform.postgres import DBConnection


class MigrationError(RuntimeError):
    """Base migration safety error."""


class MigrationIntegrityError(MigrationError):
    """A previously applied migration differs from the approved checksum."""


class MigrationPlanError(MigrationError):
    """The migration set is invalid or contains a gap."""


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
    def from_directory(cls, directory: Path) -> "MigrationPlan":
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


class MigrationRunner:
    """Apply an ordered migration plan under one PostgreSQL transaction."""

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

            applied_rows = connection.execute(
                """
                select version, name, checksum
                from schema_migration
                order by version
                """
            ).fetchall()
            applied = {
                int(version): (str(name), str(checksum))
                for version, name, checksum in applied_rows
            }

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
