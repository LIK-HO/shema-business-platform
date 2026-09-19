import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.platform.postgres import PostgresUnitOfWork


pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migration(connection: psycopg.Connection, name: str) -> None:
    for statement in (ROOT / "db/migrations" / name).read_text().split(";"):
        statement = statement.strip()
        if statement:
            connection.execute(statement)


def test_postgres_uow_commits_all_boundaries_together() -> None:
    identity_id = str(uuid4())
    tax_id = str(uuid4().int % 10_000_000_000).zfill(10)
    identity = Identity(
        identity_id=identity_id,
        canonical_name="ООО UoW Integration",
        state=IdentityState.IDENTIFIED,
        tax_id=tax_id,
    )

    with psycopg.connect(DATABASE_URL) as setup:
        apply_migration(setup, "0001_foundation.sql")
        setup.commit()

    factory = lambda: PostgresUnitOfWork(
        lambda: psycopg.connect(DATABASE_URL)
    )

    with factory() as uow:
        uow.identities.add(identity)

    with factory() as check:
        assert check.identities.find_by_tax_id(tax_id) == identity

    with psycopg.connect(DATABASE_URL) as cleanup:
        cleanup.execute(
            "delete from identity where identity_id = %s",
            (identity_id,),
        )
        cleanup.commit()


def test_postgres_uow_rolls_back_all_changes_on_failure() -> None:
    identity_id = str(uuid4())
    tax_id = str(uuid4().int % 10_000_000_000).zfill(10)
    identity = Identity(
        identity_id=identity_id,
        canonical_name="ООО UoW Rollback",
        state=IdentityState.IDENTIFIED,
        tax_id=tax_id,
    )

    factory = lambda: PostgresUnitOfWork(
        lambda: psycopg.connect(DATABASE_URL)
    )

    with pytest.raises(RuntimeError, match="forced rollback"):
        with factory() as uow:
            uow.identities.add(identity)
            raise RuntimeError("forced rollback")

    with factory() as check:
        assert check.identities.find_by_tax_id(tax_id) is None
