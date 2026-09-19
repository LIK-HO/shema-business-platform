from __future__ import annotations

import json
from uuid import uuid4

from shema_platform.application.ai import AIRun
from shema_platform.application.ports import (
    AIRunRepository,
    AuditRepository,
    CommercialActionRepository,
    EconomicEntryRepository,
    EvidenceRepository,
    IdentityRepository,
    IdempotencyRepository,
    OrderRepository,
    OutboxRepository,
    QuarantineRepository,
    SearchCandidateRepository,
)
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.search import SearchHit
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.errors import IdempotencyConflict, IntegrityViolation
from shema_platform.foundation.evidence import Evidence
from shema_platform.foundation.idempotency import IdempotencyRecord
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus
from shema_platform.platform.postgres import DBConnection


class PostgresIdentityRepository(IdentityRepository):
    """Thin persistence adapter; it performs no identity resolution."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def find_by_tax_id(self, tax_id: str) -> Identity | None:
        cursor = self._connection.execute(
            """
            select identity_id, canonical_name, state, tax_id, registration_id
            from identity
            where tax_id = %s
            """,
            (tax_id.strip(),),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        identity_id, canonical_name, state, stored_tax_id, registration_id = row
        return Identity(
            identity_id=str(identity_id),
            canonical_name=str(canonical_name),
            state=IdentityState(str(state)),
            tax_id=str(stored_tax_id) if stored_tax_id is not None else None,
            registration_id=str(registration_id) if registration_id is not None else None,
        )

    def add(self, identity: Identity) -> None:
        self._connection.execute(
            """
            insert into identity (
                identity_id,
                canonical_name,
                state,
                tax_id,
                registration_id
            )
            values (%s, %s, %s, %s, %s)
            """,
            (
                identity.identity_id,
                identity.canonical_name,
                identity.state.value,
                identity.tax_id,
                identity.registration_id,
            ),
        )


class PostgresSearchCandidateRepository(SearchCandidateRepository):
    """Persists source observations without promoting them to Identity."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, candidate: SearchHit) -> None:
        raw_payload = {
            "industries": sorted(candidate.industries),
            "selection_level": candidate.selection_level.value,
        }
        self._connection.execute(
            """
            insert into search_candidate (
                candidate_id,
                candidate_ref,
                name,
                region,
                selection_level,
                source_ref,
                tax_id,
                registration_id,
                contact_refs,
                raw_payload,
                observed_at,
                captured_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s)
            """,
            (
                str(uuid4()),
                candidate.candidate_ref,
                candidate.name,
                candidate.region,
                candidate.selection_level.value,
                candidate.source_ref,
                candidate.tax_id,
                candidate.registration_id,
                json.dumps(candidate.contact_refs, ensure_ascii=False),
                json.dumps(raw_payload, ensure_ascii=False, sort_keys=True),
                candidate.observed_at,
                candidate.captured_at,
            ),
        )


class PostgresQuarantineRepository(QuarantineRepository):
    """Persists quarantine facts without resolving or mutating business truth."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str,
        payload: dict[str, object],
    ) -> None:
        self._connection.execute(
            """
            insert into quarantine_record (
                quarantine_id,
                object_type,
                object_ref,
                reason_code,
                payload
            )
            values (%s, %s, %s, %s, %s::jsonb)
            """,
            (
                str(uuid4()),
                object_type,
                object_ref,
                reason_code,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
            ),
        )


class PostgresEvidenceRepository(EvidenceRepository):
    """Persists evidence provenance; evidence semantics remain in the foundation."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, evidence: Evidence) -> None:
        self._connection.execute(
            """
            insert into evidence (
                evidence_id,
                subject_ref,
                claim,
                source_ref,
                truth_class,
                trust_level,
                confidence,
                provenance,
                observed_at,
                captured_at,
                expires_at,
                lifecycle
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s
            )
            """,
            (
                evidence.evidence_id,
                evidence.subject_ref,
                evidence.claim,
                evidence.source_ref,
                evidence.truth_class.value,
                evidence.trust_level.value,
                evidence.confidence,
                json.dumps(dict(evidence.provenance), ensure_ascii=False, sort_keys=True),
                evidence.observed_at,
                evidence.captured_at,
                evidence.expires_at,
                evidence.lifecycle.value,
            ),
        )


class PostgresAuditRepository(AuditRepository):
    """Append-only audit persistence; there is intentionally no update method."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def append(self, record: AuditRecord) -> None:
        self._connection.execute(
            """
            insert into audit_log (
                audit_id,
                actor_id,
                action,
                resource_type,
                resource_id,
                outcome,
                occurred_at,
                metadata,
                correlation_id,
                configuration_version
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s, %s)
            """,
            (
                record.audit_id,
                record.actor_id,
                record.action,
                record.resource_type,
                record.resource_id,
                record.outcome,
                record.occurred_at,
                json.dumps(dict(record.metadata), ensure_ascii=False, sort_keys=True, default=str),
                record.correlation_id,
                record.configuration_version,
            ),
        )


class PostgresIdempotencyRepository(IdempotencyRepository):
    """Race-safe idempotency reservation backed by a unique PostgreSQL key."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def reserve(self, key: str, request_hash: str, result_ref: str) -> IdempotencyRecord:
        cursor = self._connection.execute(
            """
            insert into idempotency_key (key, request_hash, result_ref)
            values (%s, %s, %s)
            on conflict (key) do nothing
            returning key, request_hash, result_ref
            """,
            (key, request_hash, result_ref),
        )
        row = cursor.fetchone()

        if row is None:
            existing = self.get(key)
            if existing is None:
                raise IntegrityViolation("idempotency reservation disappeared")
            if existing.request_hash != request_hash:
                raise IdempotencyConflict(
                    "idempotency key reused with different request"
                )
            return existing

        return IdempotencyRecord(
            key=str(row[0]),
            request_hash=str(row[1]),
            result_ref=str(row[2]),
        )

    def get(self, key: str) -> IdempotencyRecord | None:
        cursor = self._connection.execute(
            """
            select key, request_hash, result_ref
            from idempotency_key
            where key = %s
            """,
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return IdempotencyRecord(
            key=str(row[0]),
            request_hash=str(row[1]),
            result_ref=str(row[2]),
        )


class PostgresOutboxRepository(OutboxRepository):
    """Transactional outbox adapter sharing the caller's database transaction."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def append(self, event: OutboxEvent) -> OutboxEvent:
        cursor = self._connection.execute(
            """
            insert into outbox_event (
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload,
                occurred_at
            )
            values (%s, %s, %s, %s, %s::jsonb, %s)
            on conflict (event_id) do nothing
            returning (
                event_id, event_type, aggregate_type, aggregate_id,
                payload, occurred_at, published_at
            )
            """,
            (
                event.event_id,
                event.event_type,
                event.aggregate_type,
                event.aggregate_id,
                json.dumps(event.payload, ensure_ascii=False, sort_keys=True),
                event.occurred_at,
            ),
        )
        row = cursor.fetchone()

        if row is not None:
            return self._to_event(row)

        existing = self._get(event.event_id)
        if existing is None:
            raise IntegrityViolation("outbox event disappeared")
        if (
            existing.event_type != event.event_type
            or existing.aggregate_type != event.aggregate_type
            or existing.aggregate_id != event.aggregate_id
            or existing.payload != event.payload
            or existing.occurred_at != event.occurred_at
        ):
            raise IntegrityViolation(
                "outbox event_id collision with different event"
            )
        return existing

    def pending(self) -> tuple[OutboxEvent, ...]:
        cursor = self._connection.execute(
            """
            select (
                event_id, event_type, aggregate_type, aggregate_id,
                payload, occurred_at, published_at
            )
            from outbox_event
            where published_at is null
            order by occurred_at, event_id
            """
        )
        return tuple(self._to_event(row) for row in cursor.fetchall())

    def mark_published(self, event_id: str) -> OutboxEvent:
        cursor = self._connection.execute(
            """
            update outbox_event
            set published_at = coalesce(published_at, now())
            where event_id = %s
            returning
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload,
                occurred_at,
                published_at
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown outbox event: {event_id}")
        return self._to_event(row)

    def _get(self, event_id: str) -> OutboxEvent | None:
        cursor = self._connection.execute(
            """
            select
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload,
                occurred_at,
                published_at
            from outbox_event
            where event_id = %s
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        return None if row is None else self._to_event(row)

    @staticmethod
    def _to_event(row: tuple[object, ...]) -> OutboxEvent:
        event_id, event_type, aggregate_type, aggregate_id, payload, occurred_at, published_at = row
        return OutboxEvent(
            event_id=str(event_id),
            event_type=str(event_type),
            aggregate_type=str(aggregate_type),
            aggregate_id=str(aggregate_id),
            payload=dict(payload),
            occurred_at=occurred_at,
            status=(
                OutboxStatus.PUBLISHED
                if published_at is not None
                else OutboxStatus.PENDING
            ),
        )


class PostgresCommercialActionRepository(CommercialActionRepository):
    """Durable commercial action state; no external calls occur here."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, action: CommercialAction) -> None:
        self._connection.execute(
            """
            insert into commercial_action (
                action_id, identity_id, contact_ref, channel, evidence_refs, status
            )
            values (%s, %s, %s, %s, %s::jsonb, %s)
            """,
            (
                action.action_id,
                action.identity_id,
                action.contact_ref,
                action.channel,
                json.dumps(action.evidence_refs, ensure_ascii=False),
                action.status.value,
            ),
        )

    def get(self, action_id: str) -> CommercialAction | None:
        cursor = self._connection.execute(
            """
            select action_id, identity_id, contact_ref, channel, evidence_refs, status
            from commercial_action
            where action_id = %s
            """,
            (action_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        action_id_value, identity_id, contact_ref, channel, evidence_refs, status = row
        return CommercialAction(
            action_id=str(action_id_value),
            identity_id=str(identity_id),
            contact_ref=str(contact_ref),
            channel=str(channel),
            evidence_refs=tuple(str(ref) for ref in evidence_refs),
            status=CommercialActionStatus(str(status)),
        )

    def save(self, action: CommercialAction) -> None:
        cursor = self._connection.execute(
            """
            update commercial_action
            set identity_id = %s,
                contact_ref = %s,
                channel = %s,
                evidence_refs = %s::jsonb,
                status = %s,
                updated_at = now()
            where action_id = %s
            returning action_id
            """,
            (
                action.identity_id,
                action.contact_ref,
                action.channel,
                json.dumps(action.evidence_refs, ensure_ascii=False),
                action.status.value,
                action.action_id,
            ),
        )
        if cursor.fetchone() is None:
            raise KeyError(f"unknown commercial action: {action.action_id}")


class PostgresOrderRepository(OrderRepository):
    """Durable order headers and lines with explicit source-action lineage."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, order: Order) -> None:
        self._connection.execute(
            """
            insert into order_header (order_id, identity_id, source_action_id, status)
            values (%s, %s, %s, %s)
            """,
            (
                order.order_id,
                order.identity_id,
                order.source_action_id,
                order.status.value,
            ),
        )
        self._insert_lines(order)

    def get(self, order_id: str) -> Order | None:
        cursor = self._connection.execute(
            """
            select order_id, identity_id, source_action_id, status
            from order_header
            where order_id = %s
            """,
            (order_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        line_cursor = self._connection.execute(
            """
            select line_id, description, quantity, unit_price, currency
            from order_line
            where order_id = %s
            order by line_id
            """,
            (order_id,),
        )
        lines = tuple(
            OrderLine(
                line_id=str(line_id),
                description=str(description),
                quantity=quantity,
                unit_price=Money(unit_price, str(currency)),
            )
            for line_id, description, quantity, unit_price, currency in line_cursor.fetchall()
        )
        return Order(
            order_id=str(row[0]),
            identity_id=str(row[1]),
            source_action_id=str(row[2]),
            lines=lines,
            status=OrderStatus(str(row[3])),
        )

    def save(self, order: Order) -> None:
        cursor = self._connection.execute(
            """
            update order_header
            set identity_id = %s,
                source_action_id = %s,
                status = %s,
                updated_at = now()
            where order_id = %s
            returning order_id
            """,
            (
                order.identity_id,
                order.source_action_id,
                order.status.value,
                order.order_id,
            ),
        )
        if cursor.fetchone() is None:
            raise KeyError(f"unknown order: {order.order_id}")

        self._connection.execute(
            "delete from order_line where order_id = %s",
            (order.order_id,),
        )
        self._insert_lines(order)

    def _insert_lines(self, order: Order) -> None:
        for line in order.lines:
            self._connection.execute(
                """
                insert into order_line (
                    line_id, order_id, description, quantity, unit_price, currency
                )
                values (%s, %s, %s, %s, %s, %s)
                """,
                (
                    line.line_id,
                    order.order_id,
                    line.description,
                    line.quantity,
                    line.unit_price.amount,
                    line.unit_price.currency,
                ),
            )


class PostgresEconomicEntryRepository(EconomicEntryRepository):
    """Append-only economic lineage adapter."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, entry: EconomicEntry) -> None:
        self._connection.execute(
            """
            insert into economic_entry (
                entry_id, entity_ref, kind, amount, currency, source_ref, occurred_at
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            """,
            (
                entry.entry_id,
                entry.entity_ref,
                entry.kind.value,
                entry.amount.amount,
                entry.amount.currency,
                entry.source_ref,
                entry.occurred_at,
            ),
        )

    def list_for_entity(self, entity_ref: str) -> tuple[EconomicEntry, ...]:
        cursor = self._connection.execute(
            """
            select entry_id, entity_ref, kind, amount, currency, source_ref, occurred_at
            from economic_entry
            where entity_ref = %s
            order by occurred_at, entry_id
            """,
            (entity_ref,),
        )
        return tuple(
            EconomicEntry(
                entry_id=str(entry_id),
                entity_ref=str(stored_entity_ref),
                kind=EconomicKind(str(kind)),
                amount=Money(amount, str(currency)),
                source_ref=str(source_ref),
                occurred_at=occurred_at,
            )
            for (
                entry_id,
                stored_entity_ref,
                kind,
                amount,
                currency,
                source_ref,
                occurred_at,
            ) in cursor.fetchall()
        )


class PostgresAIRunRepository(AIRunRepository):
    """Persists validated AI execution lineage and usage metrics."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, run: AIRun) -> None:
        self._connection.execute(
            """
            insert into ai_run (
                run_id,
                task_id,
                provider_id,
                model,
                model_version,
                prompt_version,
                input_refs,
                evidence_refs,
                output,
                tokens,
                cost,
                duration_seconds
            )
            values (
                %s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s, %s, %s
            )
            """,
            (
                run.run_id,
                run.task_id,
                run.provider_id,
                run.model,
                run.model_version,
                run.prompt_version,
                json.dumps(run.input_refs, ensure_ascii=False),
                json.dumps(run.evidence_refs, ensure_ascii=False),
                run.output,
                run.tokens,
                run.cost,
                run.duration_seconds,
            ),
        )

    def get(self, run_id: str) -> AIRun | None:
        cursor = self._connection.execute(
            """
            select
                run_id,
                task_id,
                provider_id,
                model,
                model_version,
                prompt_version,
                input_refs,
                evidence_refs,
                output,
                tokens,
                cost,
                duration_seconds
            from ai_run
            where run_id = %s
            """,
            (run_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None

        (
            run_id_value,
            task_id,
            provider_id,
            model,
            model_version,
            prompt_version,
            input_refs,
            evidence_refs,
            output,
            tokens,
            cost,
            duration_seconds,
        ) = row
        return AIRun(
            run_id=str(run_id_value),
            task_id=str(task_id),
            provider_id=str(provider_id),
            model=str(model),
            model_version=str(model_version),
            prompt_version=str(prompt_version),
            input_refs=tuple(str(ref) for ref in input_refs),
            evidence_refs=tuple(str(ref) for ref in evidence_refs),
            output=str(output),
            tokens=int(tokens),
            cost=float(cost),
            duration_seconds=float(duration_seconds),
        )
