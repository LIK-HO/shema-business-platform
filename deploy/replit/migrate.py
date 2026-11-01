from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

import psycopg

from shema_platform.platform.migrations import MigrationPlan, MigrationRunner


ROOT = Path(__file__).resolve().parents[2]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect or explicitly apply the approved PostgreSQL migration plan."
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply migrations; requires REPLIT_MIGRATION_APPROVED=YES.",
    )
    parser.add_argument(
        "--adopt-existing-schema",
        action="store_true",
        help="Verify and adopt an existing v1.4 schema before applying later migrations.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    plan = MigrationPlan.from_directory(ROOT / "db" / "migrations")

    if args.adopt_existing_schema and not args.apply:
        print("--adopt-existing-schema requires --apply", file=sys.stderr)
        return 2

    print("Approved migration plan:")
    for migration in plan.migrations:
        print(f"{migration.version:04d}_{migration.name} {migration.checksum}")

    if not args.apply:
        print("No database changes made. Pass --apply to execute after backup and review.")
        return 0

    if os.getenv("APP_ENV", "").strip().lower() != "production":
        print("Migration blocked: APP_ENV must be production.", file=sys.stderr)
        return 78
    if os.getenv("REPLIT_DATA_MODE", "").strip().lower() != "synthetic_only":
        print("Migration blocked: REPLIT_DATA_MODE must be synthetic_only.", file=sys.stderr)
        return 78
    if os.getenv("REPLIT_MIGRATION_APPROVED") != "YES":
        print(
            "Migration blocked: explicit REPLIT_MIGRATION_APPROVED=YES is required.",
            file=sys.stderr,
        )
        return 78

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("Migration blocked: DATABASE_URL is required.", file=sys.stderr)
        return 78

    backup_reference = os.getenv("REPLIT_BACKUP_REFERENCE", "").strip()
    if args.adopt_existing_schema and not backup_reference:
        print(
            "Migration blocked: REPLIT_BACKUP_REFERENCE is required for schema adoption.",
            file=sys.stderr,
        )
        return 78

    runner = MigrationRunner(
        connection_factory=lambda: psycopg.connect(
            database_url,
            connect_timeout=5,
        ),
        plan=plan,
    )
    try:
        if args.adopt_existing_schema:
            report = runner.adopt_existing_schema()
            print(f"Existing schema verified and adopted at version {report.current_version}.")

        report = runner.apply()
    except Exception as exc:
        # Driver exceptions can contain credentials; expose only the exception type.
        print("Migration failed: " + type(exc).__name__, file=sys.stderr)
        return 1

    print(
        "Migration completed: "
        f"applied={list(report.applied)} current_version={report.current_version}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
