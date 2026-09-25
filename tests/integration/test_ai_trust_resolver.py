import os
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.foundation.errors import QuarantineRequired
from shema_platform.platform.ai_trust import PostgresAIExecutionTrustResolver

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migrations(connection: psycopg.Connection) -> None:
    for name in ("0001_foundation.sql", "0002_discovery.sql"):
        for statement in (ROOT / "db" / "migrations" / name).read_text().split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)
    connection.commit()


def test_postgres_ai_trust_resolver_uses_canonical_identity_and_active_evidence() -> None:
    identity_id = str(uuid4())
    evidence_id = str(uuid4())

    with psycopg.connect(DATABASE_URL) as connection:
        apply_migrations(connection)
        connection.execute(
            """
            insert into identity(identity_id, canonical_name, state)
            values (%s, %s, 'verified')
            """,
            (identity_id, "P30 test identity"),
        )
        connection.execute(
            """
            insert into evidence(
                evidence_id, subject_ref, claim, source_ref, trust_level,
                confidence, observed_at, captured_at, lifecycle
            )
            values (
                %s, %s, %s, %s, 'T2', 1.0, now(), now(), 'active'
            )
            """,
            (evidence_id, identity_id, "verified claim", "source:p30-test"),
        )
        connection.commit()

        resolver = PostgresAIExecutionTrustResolver(
            lambda: psycopg.connect(DATABASE_URL)
        )
        trust = resolver.resolve(
            resource_ref=identity_id,
            evidence_refs=(evidence_id,),
        )

        assert trust.resource_trust_level == 2
        assert trust.evidence_level == 2

        connection.execute(
            "update evidence set lifecycle = 'expired' where evidence_id = %s",
            (evidence_id,),
        )
        connection.commit()

        with pytest.raises(QuarantineRequired, match="not active"):
            resolver.resolve(
                resource_ref=identity_id,
                evidence_refs=(evidence_id,),
            )

        connection.execute("delete from evidence where evidence_id = %s", (evidence_id,))
        connection.execute("delete from identity where identity_id = %s", (identity_id,))
        connection.commit()
