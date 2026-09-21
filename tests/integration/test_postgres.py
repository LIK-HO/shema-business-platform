import os
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.search import SearchHit, SelectionLevel
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.errors import IdempotencyConflict, IntegrityViolation
from shema_platform.foundation.evidence import Evidence, EvidenceLifecycle, TrustLevel, TruthClass
from shema_platform.foundation.idempotency import IdempotencyRecord
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus
from shema_platform.platform.postgres_repositories import (
    PostgresAuditRepository,
    PostgresCommercialActionRepository,
    PostgresEvidenceRepository,
    PostgresIdempotencyRepository,
    PostgresIdentityRepository,
    PostgresOrderRepository,
    PostgresOutboxRepository,
    PostgresQuarantineRepository,
    PostgresSearchCandidateRepository,
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


def prepare_database(connection: psycopg.Connection) -> None:
    for migration in (
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
        "0005_ai_run.sql",
        "0006_job_execution.sql",
        "0007_outbox_delivery_lease.sql",
        "0008_commercial_send_reservation.sql",
    ):
        apply_migration(connection, ROOT / "db/migrations" / migration)


def test_postgres_transaction_rollback_restores_database_truth() -> None:
    identity_id = str(uuid4())
    tax_id = str(uuid4().int % 10_000_000_000).zfill(10)

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        PostgresIdentityRepository(connection).add(
            Identity(
                identity_id=identity_id,
                canonical_name="ООО Rollback Test",
                state=IdentityState.IDENTIFIED,
                tax_id=tax_id,
            )
        )
        connection.rollback()

        assert PostgresIdentityRepository(connection).find_by_tax_id(tax_id) is None


def test_postgres_core_persistence_round_trip() -> None:
    identity_id = str(uuid4())
    tax_id = str(uuid4().int % 10_000_000_000).zfill(10)
    event_id = str(uuid4())
    evidence_id = str(uuid4())
    audit_id = str(uuid4())
    candidate_ref = f"candidate:{uuid4()}"
    quarantine_ref = f"quarantine:{uuid4()}"
    observed = datetime.now(UTC)
    occurred = observed + timedelta(seconds=1)

    identity = Identity(
        identity_id=identity_id,
        canonical_name="ООО Integration Test",
        state=IdentityState.IDENTIFIED,
        tax_id=tax_id,
        registration_id=str(uuid4().int % 100_000_000),
    )
    candidate = SearchHit(
        candidate_ref=candidate_ref,
        name="ООО Integration Test",
        region="Moscow",
        industries=frozenset({"logistics"}),
        source_ref="provider:integration",
        tax_id=tax_id,
        selection_level=SelectionLevel.CANDIDATE,
        observed_at=observed,
        captured_at=occurred,
    )
    evidence = Evidence(
        evidence_id=evidence_id,
        subject_ref=f"identity:{identity_id}",
        claim="Integration test evidence",
        source_ref="provider:integration",
        observed_at=observed,
        captured_at=occurred,
        truth_class=TruthClass.FACT,
        trust_level=TrustLevel.T2_VERIFIED,
        confidence=0.99,
        provenance={"provider": "integration"},
        lifecycle=EvidenceLifecycle.ACTIVE,
    )
    audit = AuditRecord(
        audit_id=audit_id,
        actor_id="integration-test",
        action="integration.round_trip",
        resource_type="identity",
        resource_id=identity_id,
        outcome="success",
        occurred_at=occurred,
        metadata={"case": "kernel"},
        correlation_id="corr:integration",
        configuration_version="cfg:v1.4",
    )
    event = OutboxEvent(
        event_id=event_id,
        event_type="identity.identified",
        aggregate_type="identity",
        aggregate_id=identity_id,
        payload={"state": "identified", "identity_id": identity_id},
        occurred_at=occurred,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)

        PostgresIdentityRepository(connection).add(identity)
        assert PostgresIdentityRepository(connection).find_by_tax_id(tax_id) == identity

        PostgresSearchCandidateRepository(connection).add(candidate)

        PostgresEvidenceRepository(connection).add(evidence)

        PostgresAuditRepository(connection).append(audit)

        idempotency = PostgresIdempotencyRepository(connection)
        reserved = idempotency.reserve("integration:kernel", "hash:1", identity_id)
        assert isinstance(reserved, IdempotencyRecord)
        assert reserved.result_ref == identity_id
        assert idempotency.reserve("integration:kernel", "hash:1", identity_id) == reserved
        with pytest.raises(IdempotencyConflict):
            idempotency.reserve("integration:kernel", "hash:2", identity_id)

        quarantine = PostgresQuarantineRepository(connection)
        quarantine.add(
            object_type="search_candidate",
            object_ref=quarantine_ref,
            reason_code="integration_test",
            payload={"identity_id": identity_id},
        )

        outbox = PostgresOutboxRepository(connection)
        assert outbox.append(event) == event
        assert outbox.append(event) == event
        assert event in outbox.pending()

        connection.commit()

        row = connection.execute(
            """
            select actor_id, correlation_id, configuration_version
            from audit_log
            where audit_id = %s
            """,
            (audit_id,),
        ).fetchone()
        assert row == ("integration-test", "corr:integration", "cfg:v1.4")

        row = connection.execute(
            """
            select subject_ref, lifecycle
            from evidence
            where evidence_id = %s
            """,
            (evidence_id,),
        ).fetchone()
        assert row == (f"identity:{identity_id}", "active")

        row = connection.execute(
            """
            select candidate_ref, selection_level, source_ref
            from search_candidate
            where candidate_ref = %s
            """,
            (candidate_ref,),
        ).fetchone()
        assert row == (candidate_ref, "candidate", "provider:integration")

        delivery = outbox.claim_pending(
            "integration-test",
            lease_seconds=60,
            now=occurred,
            limit=1,
        )
        assert len(delivery) == 1
        assert delivery[0].event.event_id == event_id

        loaded_event = outbox.mark_published(
            event_id,
            "integration-test",
            now=occurred + timedelta(seconds=1),
        )
        assert loaded_event.status is OutboxStatus.PUBLISHED
        assert event not in outbox.pending()

        connection.execute("delete from outbox_event where event_id = %s", (event_id,))
        connection.execute("delete from evidence where evidence_id = %s", (evidence_id,))
        connection.execute("delete from audit_log where audit_id = %s", (audit_id,))
        connection.execute(
            "delete from idempotency_key where key = %s",
            ("integration:kernel",),
        )
        connection.execute(
            "delete from search_candidate where candidate_ref = %s",
            (candidate_ref,),
        )
        connection.execute(
            "delete from quarantine_record where object_ref = %s",
            (quarantine_ref,),
        )
        connection.execute("delete from identity where identity_id = %s", (identity_id,))
        connection.commit()


def test_postgres_order_lifecycle_persists_cancel_and_failure_states() -> None:
    action_id = f"action:{uuid4()}"
    identity_id = f"identity:{uuid4()}"
    cancelled_order_id = f"order:{uuid4()}"
    failed_order_id = f"order:{uuid4()}"

    action = CommercialAction(
        action_id=action_id,
        identity_id=identity_id,
        contact_ref="max:integration",
        channel="max",
        evidence_refs=("evidence:integration",),
    ).mark_ready().mark_sending(
        worker_id="integration-order-worker",
        lease_until=datetime.now(UTC) + timedelta(minutes=5),
        attempt=1,
    ).mark_sent()

    cancelled = Order(
        order_id=cancelled_order_id,
        identity_id=identity_id,
        source_action_id=action_id,
        lines=(
            OrderLine("line:cancel", "Погрузка", Decimal("1"), Money(1000, "RUB")),
        ),
    )
    failed = Order(
        order_id=failed_order_id,
        identity_id=identity_id,
        source_action_id=action_id,
        lines=(
            OrderLine("line:fail", "Такелаж", Decimal("1"), Money(2000, "RUB")),
        ),
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        commercial_actions = PostgresCommercialActionRepository(connection)
        commercial_actions.add(action)
        orders = PostgresOrderRepository(connection)

        orders.add(cancelled)
        orders.save(cancelled.cancel())
        loaded_cancelled = orders.get(cancelled_order_id)
        assert loaded_cancelled is not None
        assert loaded_cancelled.status is OrderStatus.CANCELLED

        orders.add(failed)
        confirmed = failed.confirm()
        running = confirmed.start()
        orders.save(confirmed)
        orders.save(running)
        orders.save(running.fail())
        loaded_failed = orders.get(failed_order_id)
        assert loaded_failed is not None
        assert loaded_failed.status is OrderStatus.FAILED

        with pytest.raises(IntegrityViolation, match="status transition"):
            orders.save(
                Order(
                    order_id=cancelled_order_id,
                    identity_id=identity_id,
                    source_action_id=action_id,
                    lines=cancelled.lines,
                    status=OrderStatus.COMPLETED,
                )
            )

        connection.execute(
            "delete from order_line where order_id in (%s, %s)",
            (cancelled_order_id, failed_order_id),
        )
        connection.execute(
            "delete from order_header where order_id in (%s, %s)",
            (cancelled_order_id, failed_order_id),
        )
        connection.execute(
            "delete from commercial_action where action_id = %s",
            (action_id,),
        )
        connection.commit()

def test_postgres_outbox_rejects_event_id_collision() -> None:
    event_id = str(uuid4())
    occurred = datetime.now(UTC)

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)

        outbox = PostgresOutboxRepository(connection)
        outbox.append(
            OutboxEvent(
                event_id=event_id,
                event_type="identity.identified",
                aggregate_type="identity",
                aggregate_id="identity-1",
                payload={"state": "identified"},
                occurred_at=occurred,
            )
        )

        with pytest.raises(IntegrityViolation):
            outbox.append(
                OutboxEvent(
                    event_id=event_id,
                    event_type="identity.changed",
                    aggregate_type="identity",
                    aggregate_id="identity-1",
                    payload={"state": "active"},
                    occurred_at=occurred,
                )
            )

        connection.rollback()
        connection.execute("delete from outbox_event where event_id = %s", (event_id,))
        connection.commit()
