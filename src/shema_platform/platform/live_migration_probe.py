from __future__ import annotations

import json
import os
from pathlib import Path


ROOT = Path(__file__).resolve().parents[3]


def main() -> int:
    from shema_platform.platform.migrations import MigrationPlan, MigrationRunner

    database_url = os.environ.get("DATABASE_URL", "").strip()
    if not database_url:
        raise SystemExit("DATABASE_URL is not configured")

    plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")
    expected_version = plan.migrations[-1].version if plan.migrations else 0

    def connection_factory():
        import psycopg

        return psycopg.connect(database_url, connect_timeout=10)

    report = MigrationRunner(connection_factory, plan).apply()
    with connection_factory() as connection:
        row = connection.execute(
            "select current_database(), current_setting('server_version'), "
            "max(version) from schema_migration"
        ).fetchone()

    if row is None:
        raise SystemExit("schema migration verification returned no row")

    database_name, server_version, current_version = row
    if int(current_version or 0) != expected_version:
        raise SystemExit(
            f"migration version mismatch: expected {expected_version}, observed {current_version}"
        )

    print(
        json.dumps(
            {
                "status": "PASS",
                "expectedMigrationVersion": expected_version,
                "currentMigrationVersion": int(current_version or 0),
                "appliedNow": list(report.applied),
                "database": str(database_name),
                "postgresqlMajor": str(server_version).split(".", 1)[0],
                "secretValuesPrinted": False,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())