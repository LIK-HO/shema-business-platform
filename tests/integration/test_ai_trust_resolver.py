import os

import psycopg
import pytest

from shema_platform.platform.ai_trust import PostgresAIExecutionTrustResolver
from shema_platform.foundation.errors import QuarantineRequired

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)


def setup_schema(connection: psycopg.Connection) -> None:
    root = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
    for name in ("0001_foundation.sql", "0002_discovery.sql"):
        statements = open(os.path.join(root, "db", "migrations", name), encoding="utf-8").read()
        for statement in statements.split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)
    connection.commit()


def test_postgres_ai_trust_resolver_uses_canonical_identity_and_active_evidence() -> None:
    with psycopg.connect(DATABASE_URL) as connection:
        setup_schema(connection)
        connection.execute("delete from evidence")
        connection.execute("delete from identity")

        connection.execute(
            """
            insert into identity(identity_id, canonical_name, state)
            values (%s, %s, 'verified')
            """,
            ("00000000-0000-0000-0000-000000000101", "Test identity"),
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
            (
                "00000000-0000-0000-0000-000000000201",
                "00000000-0000-0000-0000-000000000101",
                "verified claim",
                "source:test",
            ),
        )
        connection.commit()

        resolver = PostgresAIExecutionTrustResolver(lambda: psycopg.connect(DATABASE_URL))
        trust = resolver.resolve(
            resource_ref="00000000-0000-0000-0000-000000000101",
            evidence_refs=("00000000-0000-0000-0000-000000000201",),
        )

        assert trust.resource_trust_level == 2
        assert trust.evidence_level == 2

        connection.execute(
            "update evidence set lifecycle = 'expired' where evidence_id = %s",
            ("00000000-0000-0000-0000-000000000201",),
        )
        connection.commit()

        with pytest.raises(QuarantineRequired, match="not active"):
            resolver.resolve(
                resource_ref="00000000-0000-0000-0000-000000000101",
                evidence_refs=("00000000-0000-0000-0000-000000000201",),
            )

        connection.execute(
            "delete from evidence where evidence_id = %s",
            ("00000000-0000-0000-0000-000000000201",),
        )
        connection.execute(
            "delete from identity where identity_id = %s",
            ("00000000-0000-0000-0000-000000000101",),
        )
        connection.commit()
