import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.platform.postgres_repositories import (
    PostgresIdentityRepository,
    PostgresQuarantineRepository,
)


pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)


ROOT = Path(__file__).resolve().parents[2]


def apply_migration(connection: psycopg.Connection, path: Path) -> None:
    statements = [
        statement.strip()
        for statement in path.read_text().split(";")
        if statement.strip()
    ]
    for statement in statements:
        connection.execute(statement)


def test_postgres_round_trip_for_identity_and_quarantine() -> None:
    tax_id = str(uuid4().int % 10_000_000_000).zfill(10)
    identity_id = str(uuid4())

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migration(connection, ROOT / "db/migrations/0001_foundation.sql")
        apply_migration(connection, ROOT / "db/migrations/0002_discovery.sql")

        identity = Identity(
            identity_id=identity_id,
            canonical_name="ООО Integration Test",
            state=IdentityState.IDENTIFIED,
            tax_id=tax_id,
        )
        identity_repository = PostgresIdentityRepository(connection)
        identity_repository.add(identity)

        loaded = identity_repository.find_by_tax_id(tax_id)
        assert loaded == identity

        quarantine_repository = PostgresQuarantineRepository(connection)
        quarantine_repository.add(
            object_type="search_candidate",
            object_ref=f"candidate:{uuid4()}",
            reason_code="integration_test",
            payload={"identity_id": identity_id},
        )

        connection.commit()
        row = connection.execute(
            """
            select count(*)
            from quarantine_record
            where reason_code = %s
            """,
            ("integration_test",),
        ).fetchone()
        assert row is not None
        assert row[0] >= 1

        connection.execute(
            "delete from identity where identity_id = %s",
            (identity_id,),
        )
        connection.execute(
            "delete from quarantine_record where reason_code = %s",
            ("integration_test",),
        )
        connection.commit()
