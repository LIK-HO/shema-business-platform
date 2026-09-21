import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import psycopg
import pytest

from shema_platform.domain.money import Money
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    PaymentIntentStatus,
    ProviderEvent,
    ProviderEventStatus,
)
from shema_platform.domain.settlement import (
    ReconciliationItem,
    ReconciliationStatus,
    SettlementLine,
    SettlementRecord,
    SettlementStatus,
)
from shema_platform.platform.postgres_repositories import (
    PostgresPaymentAttemptRepository,
    PostgresPaymentIntentRepository,
    PostgresProviderEventRepository,
    PostgresReconciliationRepository,
    PostgresSettlementRepository,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migration(connection: psycopg.Connection, path: Path) -> None:
    for statement in path.read_text().split(";"):
        statement = statement.strip()
        if statement:
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
        "0009_payment_settlement.sql",
        "0010_settlement_lines.sql",
        "0011_settlement_statement_hash.sql",
    ):
        apply_migration(connection, ROOT / "db/migrations" / migration)


def test_postgres_payment_intent_and_attempt_are_lease_guarded() -> None:
    payment_id = f"payment:{uuid4()}"
    order_id = f"order:{uuid4()}"
    attempt_id = f"attempt:{uuid4()}"
    now = datetime.now(UTC)

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        connection.execute(
            """
            insert into commercial_action (
                action_id, identity_id, contact_ref, channel, status
            )
            values (%s, %s, %s, %s, 'ready')
            """,
            (
                f"action:{uuid4()}",
                f"identity:{uuid4()}",
                "contact:test",
                "MAX",
            ),
        )
        action_id = connection.execute(
            "select action_id from commercial_action order by created_at desc limit 1"
        ).fetchone()[0]
        connection.execute(
            """
            insert into order_header (order_id, identity_id, source_action_id, status)
            values (%s, %s, %s, 'confirmed')
            """,
            (order_id, f"identity:{uuid4()}", action_id),
        )

        payment_repository = PostgresPaymentIntentRepository(connection)
        attempt_repository = PostgresPaymentAttemptRepository(connection)

        payment = PaymentIntent(
            payment_id=payment_id,
            order_id=order_id,
            amount=Money(6000, "RUB"),
            idempotency_key=f"payment-key:{uuid4()}",
        ).begin()
        payment_repository.add(payment)

        attempt = PaymentAttempt(
            attempt_id=attempt_id,
            payment_id=payment_id,
            attempt_number=1,
            external_idempotency_key=f"provider-key:{uuid4()}",
        )
        attempt_repository.add(attempt)
        sending = attempt_repository.claim_for_send(
            attempt_id,
            "worker-1",
            lease_until=now + timedelta(minutes=5),
            now=now,
        )
        assert sending.status is PaymentAttemptStatus.SENDING

        completed = attempt_repository.complete(
            attempt_id,
            "worker-1",
            status=PaymentAttemptStatus.SUCCEEDED,
            provider_ref="provider-payment-1",
            now=now + timedelta(seconds=1),
        )
        assert completed.status is PaymentAttemptStatus.SUCCEEDED

        loaded_payment = payment_repository.get(payment_id)
        assert loaded_payment is not None
        assert loaded_payment.status is PaymentIntentStatus.PENDING

        connection.rollback()


def test_provider_event_is_idempotent_and_signature_verified() -> None:
    now = datetime.now(UTC)
    event = ProviderEvent(
        event_id=f"event:{uuid4()}",
        provider_ref="provider-payment-1",
        event_type="payment.succeeded",
        signature_verified=True,
        payload_hash="sha256:test",
        received_at=now,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresProviderEventRepository(connection)
        repository.add(event)
        repository.add(event)

        loaded = repository.get(event.event_id)
        assert loaded is not None
        assert loaded.status is ProviderEventStatus.RECEIVED

        processed = repository.mark_processed(
            event.event_id,
            status=ProviderEventStatus.PROCESSED,
            processed_at=now + timedelta(seconds=1),
        )
        assert processed.status is ProviderEventStatus.PROCESSED

        duplicate = repository.mark_processed(
            event.event_id,
            status=ProviderEventStatus.PROCESSED,
            processed_at=now + timedelta(seconds=2),
        )
        assert duplicate.status is ProviderEventStatus.PROCESSED

        connection.rollback()


def test_settlement_reconciliation_persists_discrepancy_state() -> None:
    now = datetime.now(UTC)
    settlement = SettlementRecord(
        settlement_id=f"settlement:{uuid4()}",
        provider_settlement_ref=f"provider-settlement:{uuid4()}",
        statement_hash="sha256:statement-test",
        gross=Money(6000, "RUB"),
        fees=Money(150, "RUB"),
        net=Money(5850, "RUB"),
        settled_at=now,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        settlement_repository = PostgresSettlementRepository(connection)
        reconciliation_repository = PostgresReconciliationRepository(connection)

        settlement_repository.add(settlement)
        reconciling = settlement.begin_reconciliation()
        settlement_repository.save(reconciling)
        discrepancy = reconciling.mark_discrepancy()
        settlement_repository.save(discrepancy)

        item = ReconciliationItem(
            reconciliation_id=f"recon:{uuid4()}",
            settlement_id=settlement.settlement_id,
            reason_code="amount_mismatch",
            expected_amount=Money(6000, "RUB"),
            observed_amount=Money(5900, "RUB"),
            currency="RUB",
            status=ReconciliationStatus.OPEN,
            created_at=now,
        )
        reconciliation_repository.add(item)
        loaded = reconciliation_repository.get(item.reconciliation_id)
        assert loaded == item

        connection.rollback()


def test_postgres_settlement_lines_and_statement_hash_are_immutable() -> None:
    now = datetime.now(UTC)
    settlement = SettlementRecord(
        settlement_id=f"settlement:{uuid4()}",
        provider_settlement_ref=f"provider-settlement:{uuid4()}",
        statement_hash="sha256:statement-lines",
        gross=Money(6000, "RUB"),
        fees=Money(150, "RUB"),
        net=Money(5850, "RUB"),
        settled_at=now,
    )
    line = SettlementLine(
        line_id=f"line:{uuid4()}",
        settlement_id=settlement.settlement_id,
        provider_ref="provider-payment-1",
        amount=Money(6000, "RUB"),
        statement_ref="statement-1",
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        repository = PostgresSettlementRepository(connection)
        repository.add(settlement)
        repository.add_line(line)

        loaded = repository.get(settlement.settlement_id)
        assert loaded is not None
        assert loaded.statement_hash == settlement.statement_hash
        assert repository.list_lines(settlement.settlement_id) == (line,)

        with pytest.raises(Exception, match="immutable"):
            repository.save(
                SettlementRecord(
                    settlement_id=settlement.settlement_id,
                    provider_settlement_ref=settlement.provider_settlement_ref,
                    statement_hash="sha256:tampered",
                    gross=settlement.gross,
                    fees=settlement.fees,
                    net=settlement.net,
                    settled_at=settlement.settled_at,
                    status=SettlementStatus.RECONCILING,
                )
            )

        connection.rollback()


def test_postgres_reconciliation_can_resolve_and_close_settlement() -> None:
    now = datetime.now(UTC)
    settlement = SettlementRecord(
        settlement_id=f"settlement:{uuid4()}",
        provider_settlement_ref=f"provider-settlement:{uuid4()}",
        statement_hash="sha256:resolve",
        gross=Money(6000, "RUB"),
        fees=Money(150, "RUB"),
        net=Money(5850, "RUB"),
        settled_at=now,
    )

    with psycopg.connect(DATABASE_URL) as connection:
        prepare_database(connection)
        settlement_repository = PostgresSettlementRepository(connection)
        reconciliation_repository = PostgresReconciliationRepository(connection)

        settlement_repository.add(settlement)
        discrepancy = settlement.begin_reconciliation().mark_discrepancy()
        settlement_repository.save(discrepancy)

        item = ReconciliationItem(
            reconciliation_id=f"recon:{uuid4()}",
            settlement_id=settlement.settlement_id,
            reason_code="amount_mismatch",
            expected_amount=Money(6000, "RUB"),
            observed_amount=Money(5900, "RUB"),
            currency="RUB",
            status=ReconciliationStatus.OPEN,
            created_at=now,
        )
        reconciliation_repository.add(item)
        resolved = item.resolve(now + timedelta(minutes=1))
        reconciliation_repository.resolve(resolved)

        assert reconciliation_repository.list_open_for_settlement(
            settlement.settlement_id
        ) == ()

        closed = discrepancy.resolve_discrepancy()
        settlement_repository.save(closed)
        loaded = settlement_repository.get(settlement.settlement_id)
        assert loaded is not None
        assert loaded.status is SettlementStatus.SETTLED

        connection.rollback()
