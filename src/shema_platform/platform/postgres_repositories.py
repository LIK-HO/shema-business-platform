from __future__ import annotations

import json
from datetime import datetime
from uuid import uuid4

from shema_platform.application.ai import AIRun
from shema_platform.application.ports import (
    AIRunRepository,
    AuditRepository,
    CommercialActionRepository,
    EconomicEntryRepository,
    EvidenceRepository,
    IdempotencyRepository,
    IdentityRepository,
    JobRepository,
    OrderRepository,
    OutboxRepository,
    PaymentAttemptRepository,
    PaymentIntentRepository,
    ProviderEventRepository,
    ReconciliationRepository,
    SettlementRepository,
    QuarantineRepository,
    SearchCandidateRepository,
)
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.domain.economics import EconomicEntry, EconomicKind
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.money import Money
from shema_platform.domain.order import Order, OrderLine, OrderStatus
from shema_platform.domain.payment import (
    PaymentAttempt,
    PaymentAttemptStatus,
    PaymentIntent,
    PaymentIntentStatus,
    ProviderEvent,
    ProviderEventStatus,
)
from shema_platform.domain.search import SearchHit
from shema_platform.domain.settlement import (
    ReconciliationItem,
    ReconciliationStatus,
    SettlementRecord,
    SettlementStatus,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.errors import (
    IdempotencyConflict,
    IntegrityViolation,
    QuarantineRequired,
)
from shema_platform.foundation.evidence import Evidence
from shema_platform.foundation.idempotency import IdempotencyRecord
from shema_platform.foundation.jobs import JobExecution, JobLease, JobRecord, JobState
from shema_platform.foundation.outbox import OutboxDelivery, OutboxEvent, OutboxStatus
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

    def complete(
        self,
        key: str,
        request_hash: str,
        result_ref: str,
    ) -> IdempotencyRecord:
        if not result_ref.strip():
            raise ValueError("result_ref is required")
        cursor = self._connection.execute(
            """
            select key, request_hash, result_ref
            from idempotency_key
            where key = %s
            for update
            """,
            (key,),
        )
        row = cursor.fetchone()
        if row is None:
            raise IdempotencyConflict("idempotency completion has no reservation")

        existing = IdempotencyRecord(
            key=str(row[0]),
            request_hash=str(row[1]),
            result_ref=str(row[2]),
        )
        if existing.request_hash != request_hash:
            raise IdempotencyConflict("idempotency key reused with different request")
        if existing.result_ref and not existing.result_ref.startswith("pending:"):
            return existing

        cursor = self._connection.execute(
            """
            update idempotency_key
            set result_ref = %s
            where key = %s
              and request_hash = %s
            returning key, request_hash, result_ref
            """,
            (result_ref, key, request_hash),
        )
        updated = cursor.fetchone()
        if updated is None:
            raise IntegrityViolation("idempotency completion disappeared")
        return IdempotencyRecord(
            key=str(updated[0]),
            request_hash=str(updated[1]),
            result_ref=str(updated[2]),
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
    """Transactional outbox adapter with lease-safe external delivery."""

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
            returning
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload,
                occurred_at,
                published_at
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
            raise IntegrityViolation("outbox event_id collision with different event")
        return existing

    def pending(self) -> tuple[OutboxEvent, ...]:
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
            where published_at is null
            order by occurred_at, event_id
            """
        )
        return tuple(self._to_event(row) for row in cursor.fetchall())

    def claim_pending(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int,
    ) -> tuple[OutboxDelivery, ...]:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if limit < 1:
            raise ValueError("limit must be >= 1")
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        cursor = self._connection.execute(
            """
            with candidates as (
                select event_id
                from outbox_event
                where published_at is null
                  and occurred_at <= %s
                  and (
                      delivery_lease_until is null
                      or delivery_lease_until <= %s
                  )
                order by occurred_at, event_id
                for update skip locked
                limit %s
            )
            update outbox_event as event
            set delivery_attempt = event.delivery_attempt + 1,
                delivery_worker_id = %s,
                delivery_lease_until = %s + (%s * interval '1 second')
            from candidates
            where event.event_id = candidates.event_id
            returning
                event.event_id,
                event.event_type,
                event.aggregate_type,
                event.aggregate_id,
                event.payload,
                event.occurred_at,
                event.published_at,
                event.delivery_attempt,
                event.delivery_worker_id,
                event.delivery_lease_until
            """,
            (now, now, limit, worker_id, now, lease_seconds),
        )
        return tuple(self._to_delivery(row) for row in cursor.fetchall())

    def mark_published(
        self,
        event_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> OutboxEvent:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        cursor = self._connection.execute(
            """
            update outbox_event
            set published_at = %s,
                delivery_worker_id = null,
                delivery_lease_until = null
            where event_id = %s
              and published_at is null
              and delivery_worker_id = %s
              and delivery_lease_until > %s
            returning
                event_id,
                event_type,
                aggregate_type,
                aggregate_id,
                payload,
                occurred_at,
                published_at
            """,
            (now, event_id, worker_id, now),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation(
                "outbox publication rejected: missing or expired delivery lease"
            )
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
        (
            event_id,
            event_type,
            aggregate_type,
            aggregate_id,
            payload,
            occurred_at,
            published_at,
        ) = row
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

    @staticmethod
    def _to_delivery(row: tuple[object, ...]) -> OutboxDelivery:
        (
            event_id,
            event_type,
            aggregate_type,
            aggregate_id,
            payload,
            occurred_at,
            published_at,
            delivery_attempt,
            delivery_worker_id,
            delivery_lease_until,
        ) = row
        if delivery_worker_id is None or delivery_lease_until is None:
            raise IntegrityViolation("outbox delivery lease disappeared")
        return OutboxDelivery(
            event=OutboxEvent(
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
            ),
            attempt=int(delivery_attempt),
            worker_id=str(delivery_worker_id),
            lease_until=delivery_lease_until,
        )


class PostgresJobRepository(JobRepository):
    """Durable worker execution state with lease-safe claiming and completion."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def enqueue(self, record: JobRecord) -> JobRecord:
        cursor = self._connection.execute(
            """
            insert into job_execution (
                job_id, job_type, attempt, state, idempotency_key, payload,
                available_at, worker_id, lease_until, last_error
            )
            values (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            on conflict (job_id) do nothing
            returning
                job_id, job_type, attempt, state, idempotency_key, payload,
                available_at, worker_id, lease_until, last_error
            """,
            (
                record.execution.job_id,
                record.execution.job_type,
                record.execution.attempt,
                record.execution.state.value,
                record.execution.idempotency_key,
                json.dumps(dict(record.payload), ensure_ascii=False, sort_keys=True),
                record.available_at,
                record.execution.lease.worker_id if record.execution.lease else None,
                record.execution.lease.leased_until if record.execution.lease else None,
                record.last_error,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            existing = self.get(record.execution.job_id)
            if existing is None:
                raise IntegrityViolation("job disappeared after enqueue collision")
            if existing != record:
                raise IntegrityViolation("job_id collision with different execution")
            return existing
        return self._to_record(row)

    def get(self, job_id: str) -> JobRecord | None:
        cursor = self._connection.execute(
            """
            select
                job_id, job_type, attempt, state, idempotency_key, payload,
                available_at, worker_id, lease_until, last_error
            from job_execution
            where job_id = %s
            """,
            (job_id,),
        )
        row = cursor.fetchone()
        return None if row is None else self._to_record(row)

    def claim_next(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
    ) -> JobRecord | None:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")

        cursor = self._connection.execute(
            """
            with candidate as (
                select job_id
                from job_execution
                where (
                    state in ('queued', 'retryable_failure')
                    and available_at <= %s
                )
                or (
                    state = 'running'
                    and lease_until is not null
                    and lease_until <= %s
                )
                order by available_at, created_at, job_id
                for update skip locked
                limit 1
            )
            update job_execution as job
            set state = 'running',
                attempt = case
                    when job.state = 'queued' and job.attempt = 1 then job.attempt
                    else job.attempt + 1
                end,
                worker_id = %s,
                lease_until = %s + (%s * interval '1 second'),
                updated_at = %s,
                last_error = null
            from candidate
            where job.job_id = candidate.job_id
            returning
                job.job_id, job.job_type, job.attempt, job.state, job.idempotency_key,
                job.payload, job.available_at, job.worker_id, job.lease_until, job.last_error
            """,
            (now, now, worker_id, now, lease_seconds, now),
        )
        row = cursor.fetchone()
        return None if row is None else self._to_record(row)

    def renew(
        self,
        job_id: str,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
    ) -> JobRecord:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be > 0")
        if now.tzinfo is None:
            raise ValueError("now must be timezone-aware")
        cursor = self._connection.execute(
            """
            update job_execution
            set lease_until = %s + (%s * interval '1 second'),
                updated_at = %s
            where job_id = %s
              and state = 'running'
              and worker_id = %s
              and lease_until > %s
            returning
                job_id, job_type, attempt, state, idempotency_key, payload,
                available_at, worker_id, lease_until, last_error
            """,
            (now, lease_seconds, now, job_id, worker_id, now),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation("job lease renewal rejected: missing or expired lease")
        return self._to_record(row)

    def complete(self, job_id: str, worker_id: str, *, now: datetime) -> JobRecord:
        cursor = self._connection.execute(
            """
            update job_execution
            set state = 'succeeded',
                worker_id = null,
                lease_until = null,
                completed_at = %s,
                updated_at = %s
            where job_id = %s
              and state = 'running'
              and worker_id = %s
              and lease_until > %s
            returning
                job_id, job_type, attempt, state, idempotency_key, payload,
                available_at, worker_id, lease_until, last_error
            """,
            (now, now, job_id, worker_id, now),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation("job completion rejected: missing or expired lease")
        return self._to_record(row)

    def fail(
        self,
        job_id: str,
        worker_id: str,
        *,
        retryable: bool,
        error: str,
        available_at: datetime,
        now: datetime,
    ) -> JobRecord:
        if not error.strip():
            raise ValueError("error is required")
        state = "retryable_failure" if retryable else "failed"
        completed_at = None if retryable else now
        cursor = self._connection.execute(
            """
            update job_execution
            set state = %s,
                worker_id = null,
                lease_until = null,
                last_error = %s,
                available_at = %s,
                completed_at = %s,
                updated_at = %s
            where job_id = %s
              and state = 'running'
              and worker_id = %s
              and lease_until > %s
            returning
                job_id, job_type, attempt, state, idempotency_key, payload,
                available_at, worker_id, lease_until, last_error
            """,
            (
                state,
                error,
                available_at,
                completed_at,
                now,
                job_id,
                worker_id,
                now,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation("job failure rejected: missing or expired lease")
        return self._to_record(row)

    @staticmethod
    def _to_record(row: tuple[object, ...]) -> JobRecord:
        (
            job_id,
            job_type,
            attempt,
            state,
            idempotency_key,
            payload,
            available_at,
            worker_id,
            lease_until,
            last_error,
        ) = row
        lease = None
        if worker_id is not None and lease_until is not None:
            lease = JobLease(
                job_id=str(job_id),
                worker_id=str(worker_id),
                leased_until=lease_until,
            )
        execution = JobExecution(
            job_id=str(job_id),
            job_type=str(job_type),
            attempt=int(attempt),
            state=JobState(str(state)),
            idempotency_key=str(idempotency_key),
            lease=lease,
        )
        return JobRecord(
            execution=execution,
            payload=dict(payload),
            available_at=available_at,
            last_error=str(last_error) if last_error is not None else None,
        )


class PostgresCommercialActionRepository(CommercialActionRepository):
    """Durable commercial action state; no external calls occur here."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, action: CommercialAction) -> None:
        self._connection.execute(
            """
            insert into commercial_action (
                action_id,
                identity_id,
                contact_ref,
                channel,
                evidence_refs,
                status,
                send_attempt,
                send_worker_id,
                send_lease_until
            )
            values (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s)
            """,
            (
                action.action_id,
                action.identity_id,
                action.contact_ref,
                action.channel,
                json.dumps(action.evidence_refs, ensure_ascii=False),
                action.status.value,
                action.send_attempt,
                action.send_worker_id,
                action.send_lease_until,
            ),
        )

    def get(self, action_id: str) -> CommercialAction | None:
        cursor = self._connection.execute(
            """
            select
                action_id,
                identity_id,
                contact_ref,
                channel,
                evidence_refs,
                status,
                send_attempt,
                send_worker_id,
                send_lease_until
            from commercial_action
            where action_id = %s
            """,
            (action_id,),
        )
        row = cursor.fetchone()
        return None if row is None else self._to_action(row)

    def claim_for_send(
        self,
        action_id: str,
        worker_id: str,
        *,
        lease_until: datetime,
        now: datetime,
    ) -> CommercialAction:
        if not worker_id.strip():
            raise ValueError("send worker is required")
        if lease_until.tzinfo is None or now.tzinfo is None:
            raise ValueError("send lease timestamps must be timezone-aware")
        if lease_until <= now:
            raise ValueError("send lease must be in the future")

        current = self.get(action_id)
        if current is None:
            raise KeyError(f"unknown commercial action: {action_id}")
        if current.status not in (
            CommercialActionStatus.READY,
            CommercialActionStatus.SENDING,
        ):
            raise QuarantineRequired(
                "commercial action is not available for external send"
            )
        current.validate_for_send()

        cursor = self._connection.execute(
            """
            update commercial_action
            set status = 'sending',
                send_attempt = send_attempt + 1,
                send_worker_id = %s,
                send_lease_until = %s,
                updated_at = %s
            where action_id = %s
              and (
                  status = 'ready'
                  or (
                      status = 'sending'
                      and send_lease_until is not null
                      and send_lease_until <= %s
                  )
              )
            returning
                action_id,
                identity_id,
                contact_ref,
                channel,
                evidence_refs,
                status,
                send_attempt,
                send_worker_id,
                send_lease_until
            """,
            (
                worker_id,
                lease_until,
                now,
                action_id,
                now,
            ),
        )
        row = cursor.fetchone()
        if row is None:
            current = self.get(action_id)
            if current is not None and current.status is CommercialActionStatus.SENDING:
                raise QuarantineRequired(
                    "commercial action send is already in progress"
                )
            raise QuarantineRequired(
                "commercial action changed during send reservation"
            )
        return self._to_action(row)

    def complete_send(
        self,
        action_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> CommercialAction:
        if not worker_id.strip():
            raise ValueError("send worker is required")
        if now.tzinfo is None:
            raise ValueError("completion time must be timezone-aware")

        cursor = self._connection.execute(
            """
            update commercial_action
            set status = 'sent',
                send_worker_id = null,
                send_lease_until = null,
                updated_at = %s
            where action_id = %s
              and status = 'sending'
              and send_worker_id = %s
              and send_lease_until > %s
            returning
                action_id,
                identity_id,
                contact_ref,
                channel,
                evidence_refs,
                status,
                send_attempt,
                send_worker_id,
                send_lease_until
            """,
            (now, action_id, worker_id, now),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation(
                "commercial action completion rejected: missing or expired send lease"
            )
        return self._to_action(row)

    def save(self, action: CommercialAction) -> None:
        if action.status is CommercialActionStatus.SENT:
            raise IntegrityViolation(
                "commercial action SENT state requires lease-guarded completion"
            )
        cursor = self._connection.execute(
            """
            update commercial_action
            set identity_id = %s,
                contact_ref = %s,
                channel = %s,
                evidence_refs = %s::jsonb,
                status = %s,
                send_attempt = %s,
                send_worker_id = %s,
                send_lease_until = %s,
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
                action.send_attempt,
                action.send_worker_id,
                action.send_lease_until,
                action.action_id,
            ),
        )
        if cursor.fetchone() is None:
            raise KeyError(f"unknown commercial action: {action.action_id}")

    @staticmethod
    def _to_action(row: tuple[object, ...]) -> CommercialAction:
        (
            action_id_value,
            identity_id,
            contact_ref,
            channel,
            evidence_refs,
            status,
            send_attempt,
            send_worker_id,
            send_lease_until,
        ) = row
        return CommercialAction(
            action_id=str(action_id_value),
            identity_id=str(identity_id),
            contact_ref=str(contact_ref),
            channel=str(channel),
            evidence_refs=tuple(str(ref) for ref in evidence_refs),
            status=CommercialActionStatus(str(status)),
            send_attempt=int(send_attempt),
            send_worker_id=str(send_worker_id) if send_worker_id is not None else None,
            send_lease_until=send_lease_until,
        )


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
            select order_id, identity_id, source_action_id, status
            from order_header
            where order_id = %s
            for update
            """,
            (order.order_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown order: {order.order_id}")

        line_cursor = self._connection.execute(
            """
            select line_id, description, quantity, unit_price, currency
            from order_line
            where order_id = %s
            order by line_id
            """,
            (order.order_id,),
        )
        current = Order(
            order_id=str(row[0]),
            identity_id=str(row[1]),
            source_action_id=str(row[2]),
            lines=tuple(
                OrderLine(
                    line_id=str(line_id),
                    description=str(description),
                    quantity=quantity,
                    unit_price=Money(unit_price, str(currency)),
                )
                for line_id, description, quantity, unit_price, currency
                in line_cursor.fetchall()
            ),
            status=OrderStatus(str(row[3])),
        )

        if (
            current.identity_id != order.identity_id
            or current.source_action_id != order.source_action_id
        ):
            raise IntegrityViolation(
                "order identity and source action lineage are immutable"
            )

        if current.status is order.status:
            if current.status is not OrderStatus.DRAFT and current.lines != order.lines:
                raise IntegrityViolation(
                    "order lines are immutable after draft state"
                )
        else:
            try:
                expected = {
                    OrderStatus.CONFIRMED: current.confirm,
                    OrderStatus.IN_PROGRESS: current.start,
                    OrderStatus.COMPLETED: current.complete,
                    OrderStatus.CANCELLED: current.cancel,
                    OrderStatus.FAILED: current.fail,
                }.get(order.status)
                if expected is None or expected() != order:
                    raise IntegrityViolation(
                        "order status transition is not permitted by domain"
                    )
            except ValueError as exc:
                raise IntegrityViolation(
                    f"order status transition rejected: {exc}"
                ) from exc

        self._connection.execute(
            """
            update order_header
            set identity_id = %s,
                source_action_id = %s,
                status = %s,
                updated_at = now()
            where order_id = %s
            """,
            (
                order.identity_id,
                order.source_action_id,
                order.status.value,
                order.order_id,
            ),
        )

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


class PostgresPaymentIntentRepository(PaymentIntentRepository):
    """Durable payment intent state with order lineage and explicit lifecycle."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, payment: PaymentIntent) -> None:
        self._connection.execute(
            """
            insert into payment_intent (
                payment_id, order_id, amount, currency, idempotency_key, status
            )
            values (%s, %s, %s, %s, %s, %s)
            """,
            (
                payment.payment_id,
                payment.order_id,
                payment.amount.amount,
                payment.amount.currency,
                payment.idempotency_key,
                payment.status.value,
            ),
        )

    def get(self, payment_id: str) -> PaymentIntent | None:
        cursor = self._connection.execute(
            """
            select payment_id, order_id, amount, currency, idempotency_key, status
            from payment_intent
            where payment_id = %s
            """,
            (payment_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._to_payment(row)

    def save(self, payment: PaymentIntent) -> None:
        cursor = self._connection.execute(
            """
            select payment_id, order_id, amount, currency, idempotency_key, status
            from payment_intent
            where payment_id = %s
            for update
            """,
            (payment.payment_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown payment: {payment.payment_id}")

        current = self._to_payment(row)
        if (
            current.order_id != payment.order_id
            or current.amount != payment.amount
            or current.idempotency_key != payment.idempotency_key
        ):
            raise IntegrityViolation("payment intent identity and amount are immutable")

        if current.status is not payment.status:
            try:
                expected = {
                    PaymentIntentStatus.PENDING: current.begin,
                    PaymentIntentStatus.PROCESSING: current.mark_processing,
                    PaymentIntentStatus.SUCCEEDED: current.succeed,
                    PaymentIntentStatus.FAILED: current.fail,
                    PaymentIntentStatus.CANCELLED: current.cancel,
                }.get(payment.status)
                if expected is None or expected() != payment:
                    raise IntegrityViolation(
                        "payment intent status transition is not permitted by domain"
                    )
            except ValueError as exc:
                raise IntegrityViolation(
                    f"payment intent status transition rejected: {exc}"
                ) from exc

        self._connection.execute(
            """
            update payment_intent
            set status = %s, updated_at = now()
            where payment_id = %s
            """,
            (payment.status.value, payment.payment_id),
        )

    @staticmethod
    def _to_payment(row: tuple[object, ...]) -> PaymentIntent:
        payment_id, order_id, amount, currency, idempotency_key, status = row
        return PaymentIntent(
            payment_id=str(payment_id),
            order_id=str(order_id),
            amount=Money(amount, str(currency)),
            idempotency_key=str(idempotency_key),
            status=PaymentIntentStatus(str(status)),
        )


class PostgresPaymentAttemptRepository(PaymentAttemptRepository):
    """Lease-guarded persistence for provider payment attempts."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, attempt: PaymentAttempt) -> None:
        self._connection.execute(
            """
            insert into payment_attempt (
                attempt_id,
                payment_id,
                attempt_number,
                external_idempotency_key,
                status,
                provider_ref,
                send_worker_id,
                send_lease_until
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                attempt.attempt_id,
                attempt.payment_id,
                attempt.attempt_number,
                attempt.external_idempotency_key,
                attempt.status.value,
                attempt.provider_ref,
                attempt.worker_id,
                attempt.lease_until,
            ),
        )

    def get(self, attempt_id: str) -> PaymentAttempt | None:
        cursor = self._connection.execute(
            """
            select
                attempt_id,
                payment_id,
                attempt_number,
                external_idempotency_key,
                status,
                provider_ref,
                send_worker_id,
                send_lease_until
            from payment_attempt
            where attempt_id = %s
            """,
            (attempt_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._to_attempt(row)

    def find_by_provider_ref(self, provider_ref: str) -> PaymentAttempt | None:
        cursor = self._connection.execute(
            """
            select
                attempt_id,
                payment_id,
                attempt_number,
                external_idempotency_key,
                status,
                provider_ref,
                send_worker_id,
                send_lease_until
            from payment_attempt
            where provider_ref = %s
            order by attempt_number desc
            limit 1
            """,
            (provider_ref,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._to_attempt(row)

    def claim_for_send(
        self,
        attempt_id: str,
        worker_id: str,
        *,
        lease_until: datetime,
        now: datetime,
    ) -> PaymentAttempt:
        if not worker_id.strip():
            raise ValueError("payment worker is required")
        if lease_until.tzinfo is None or now.tzinfo is None:
            raise ValueError("payment lease times must be timezone-aware")
        cursor = self._connection.execute(
            """
            update payment_attempt
            set status = 'sending',
                send_worker_id = %s,
                send_lease_until = %s,
                updated_at = %s
            where attempt_id = %s
              and (
                  status = 'ready'
                  or (status = 'sending' and send_lease_until is not null and send_lease_until <= %s)
              )
            returning
                attempt_id,
                payment_id,
                attempt_number,
                external_idempotency_key,
                status,
                provider_ref,
                send_worker_id,
                send_lease_until
            """,
            (worker_id, lease_until, now, attempt_id, now),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation("payment attempt is not ready for send")
        return self._to_attempt(row)

    def complete(
        self,
        attempt_id: str,
        worker_id: str,
        *,
        status: PaymentAttemptStatus,
        provider_ref: str | None,
        now: datetime,
    ) -> PaymentAttempt:
        if status not in {
            PaymentAttemptStatus.PENDING,
            PaymentAttemptStatus.SUCCEEDED,
            PaymentAttemptStatus.FAILED,
        }:
            raise ValueError("invalid payment attempt completion state")
        if not worker_id.strip():
            raise ValueError("payment worker is required")
        if now.tzinfo is None:
            raise ValueError("completion time must be timezone-aware")
        cursor = self._connection.execute(
            """
            update payment_attempt
            set status = %s,
                provider_ref = coalesce(%s, provider_ref),
                send_worker_id = null,
                send_lease_until = null,
                updated_at = %s
            where attempt_id = %s
              and status = 'sending'
              and send_worker_id = %s
              and send_lease_until > %s
            returning
                attempt_id,
                payment_id,
                attempt_number,
                external_idempotency_key,
                status,
                provider_ref,
                send_worker_id,
                send_lease_until
            """,
            (status.value, provider_ref, now, attempt_id, worker_id, now),
        )
        row = cursor.fetchone()
        if row is None:
            raise IntegrityViolation(
                "payment attempt completion rejected: missing or expired lease"
            )
        return self._to_attempt(row)

    def apply_provider_result(
        self,
        attempt_id: str,
        *,
        status: PaymentAttemptStatus,
        provider_ref: str | None,
    ) -> PaymentAttempt:
        if status not in {
            PaymentAttemptStatus.PENDING,
            PaymentAttemptStatus.SUCCEEDED,
            PaymentAttemptStatus.FAILED,
        }:
            raise ValueError("invalid provider result state")

        cursor = self._connection.execute(
            """
            update payment_attempt
            set status = %s,
                provider_ref = coalesce(%s, provider_ref),
                send_worker_id = null,
                send_lease_until = null,
                updated_at = now()
            where attempt_id = %s
              and status not in ('succeeded', 'failed', 'expired')
            returning
                attempt_id,
                payment_id,
                attempt_number,
                external_idempotency_key,
                status,
                provider_ref,
                send_worker_id,
                send_lease_until
            """,
            (status.value, provider_ref, attempt_id),
        )
        row = cursor.fetchone()
        if row is not None:
            return self._to_attempt(row)

        existing = self.get(attempt_id)
        if existing is None:
            raise KeyError(f"unknown payment attempt: {attempt_id}")
        if existing.status is status:
            return existing
        if existing.status in {
            PaymentAttemptStatus.SUCCEEDED,
            PaymentAttemptStatus.FAILED,
            PaymentAttemptStatus.EXPIRED,
        }:
            return existing
        raise IntegrityViolation("provider result could not be applied")

    @staticmethod
    def _to_attempt(row: tuple[object, ...]) -> PaymentAttempt:
        (
            attempt_id,
            payment_id,
            attempt_number,
            external_idempotency_key,
            status,
            provider_ref,
            worker_id,
            lease_until,
        ) = row
        return PaymentAttempt(
            attempt_id=str(attempt_id),
            payment_id=str(payment_id),
            attempt_number=int(attempt_number),
            external_idempotency_key=str(external_idempotency_key),
            status=PaymentAttemptStatus(str(status)),
            provider_ref=str(provider_ref) if provider_ref is not None else None,
            worker_id=str(worker_id) if worker_id is not None else None,
            lease_until=lease_until,
        )


class PostgresProviderEventRepository(ProviderEventRepository):
    """Idempotent persistence for verified provider event facts."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, event: ProviderEvent) -> None:
        cursor = self._connection.execute(
            """
            insert into provider_event (
                event_id,
                provider_ref,
                event_type,
                signature_verified,
                payload_hash,
                received_at,
                status
            )
            values (%s, %s, %s, %s, %s, %s, %s)
            on conflict (event_id) do nothing
            returning
                event_id,
                provider_ref,
                event_type,
                signature_verified,
                payload_hash,
                received_at,
                status
            """,
            (
                event.event_id,
                event.provider_ref,
                event.event_type,
                event.signature_verified,
                event.payload_hash,
                event.received_at,
                event.status.value,
            ),
        )
        row = cursor.fetchone()
        if row is not None:
            return
        existing = self.get(event.event_id)
        if existing is None:
            raise IntegrityViolation("provider event disappeared after conflict")
        if (
            existing.provider_ref != event.provider_ref
            or existing.event_type != event.event_type
            or existing.payload_hash != event.payload_hash
        ):
            raise IntegrityViolation("provider event collision with different payload")
        if existing.signature_verified != event.signature_verified:
            raise IntegrityViolation("provider event verification state conflict")

    def get(self, event_id: str) -> ProviderEvent | None:
        cursor = self._connection.execute(
            """
            select
                event_id,
                provider_ref,
                event_type,
                signature_verified,
                payload_hash,
                received_at,
                status
            from provider_event
            where event_id = %s
            """,
            (event_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._to_event(row)

    def mark_processed(
        self,
        event_id: str,
        *,
        status: ProviderEventStatus,
        processed_at: datetime,
    ) -> ProviderEvent:
        if status not in {
            ProviderEventStatus.PROCESSED,
            ProviderEventStatus.IGNORED,
        }:
            raise ValueError("provider event may only be processed or ignored")
        if processed_at.tzinfo is None:
            raise ValueError("processed_at must be timezone-aware")
        cursor = self._connection.execute(
            """
            update provider_event
            set status = %s,
                processed_at = %s
            where event_id = %s
              and status = 'received'
            returning
                event_id,
                provider_ref,
                event_type,
                signature_verified,
                payload_hash,
                received_at,
                status
            """,
            (status.value, processed_at, event_id),
        )
        row = cursor.fetchone()
        if row is not None:
            return self._to_event(row)
        existing = self.get(event_id)
        if existing is None:
            raise KeyError(f"unknown provider event: {event_id}")
        if existing.status is status:
            return existing
        raise IntegrityViolation("provider event has already been finalized")

    @staticmethod
    def _to_event(row: tuple[object, ...]) -> ProviderEvent:
        (
            event_id,
            provider_ref,
            event_type,
            signature_verified,
            payload_hash,
            received_at,
            status,
        ) = row
        return ProviderEvent(
            event_id=str(event_id),
            provider_ref=str(provider_ref),
            event_type=str(event_type),
            signature_verified=bool(signature_verified),
            payload_hash=str(payload_hash),
            received_at=received_at,
            status=ProviderEventStatus(str(status)),
        )


class PostgresSettlementRepository(SettlementRepository):
    """Durable provider settlement facts with explicit lifecycle."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, settlement: SettlementRecord) -> None:
        self._connection.execute(
            """
            insert into settlement_record (
                settlement_id,
                provider_settlement_ref,
                statement_hash,
                gross_amount,
                fees,
                net_amount,
                currency,
                settled_at,
                status
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                settlement.settlement_id,
                settlement.provider_settlement_ref,
                settlement.statement_hash,
                settlement.gross.amount,
                settlement.fees.amount,
                settlement.net.amount,
                settlement.gross.currency,
                settlement.settled_at,
                settlement.status.value,
            ),
        )

    def get(self, settlement_id: str) -> SettlementRecord | None:
        cursor = self._connection.execute(
            """
            select
                settlement_id,
                provider_settlement_ref,
                statement_hash,
                gross_amount,
                fees,
                net_amount,
                currency,
                settled_at,
                status
            from settlement_record
            where settlement_id = %s
            """,
            (settlement_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._to_settlement(row)

    def save(self, settlement: SettlementRecord) -> None:
        cursor = self._connection.execute(
            """
            select
                settlement_id,
                provider_settlement_ref,
                statement_hash,
                gross_amount,
                fees,
                net_amount,
                currency,
                settled_at,
                status
            from settlement_record
            where settlement_id = %s
            for update
            """,
            (settlement.settlement_id,),
        )
        row = cursor.fetchone()
        if row is None:
            raise KeyError(f"unknown settlement: {settlement.settlement_id}")
        current = self._to_settlement(row)

        if (
            current.provider_settlement_ref != settlement.provider_settlement_ref
            or current.statement_hash != settlement.statement_hash
            or current.gross != settlement.gross
            or current.fees != settlement.fees
            or current.net != settlement.net
            or current.settled_at != settlement.settled_at
        ):
            raise IntegrityViolation("settlement facts are immutable")

        if current.status is not settlement.status:
            try:
                expected = {
                    SettlementStatus.RECONCILING: current.begin_reconciliation,
                    SettlementStatus.SETTLED: (
                        current.settle
                        if current.status is SettlementStatus.RECONCILING
                        else current.resolve_discrepancy
                    ),
                    SettlementStatus.DISCREPANCY: current.mark_discrepancy,
                }.get(settlement.status)
                if expected is None or expected() != settlement:
                    raise IntegrityViolation(
                        "settlement status transition is not permitted"
                    )
            except ValueError as exc:
                raise IntegrityViolation(
                    f"settlement status transition rejected: {exc}"
                ) from exc

        self._connection.execute(
            """
            update settlement_record
            set status = %s
            where settlement_id = %s
            """,
            (settlement.status.value, settlement.settlement_id),
        )

    def add_line(self, line: SettlementLine) -> None:
        self._connection.execute(
            """
            insert into settlement_line (
                line_id,
                settlement_id,
                provider_ref,
                amount,
                currency,
                statement_ref
            )
            values (%s, %s, %s, %s, %s, %s)
            """,
            (
                line.line_id,
                line.settlement_id,
                line.provider_ref,
                line.amount.amount,
                line.amount.currency,
                line.statement_ref,
            ),
        )

    def list_lines(self, settlement_id: str) -> tuple[SettlementLine, ...]:
        cursor = self._connection.execute(
            """
            select line_id, settlement_id, provider_ref, amount, currency, statement_ref
            from settlement_line
            where settlement_id = %s
            order by line_id
            """,
            (settlement_id,),
        )
        return tuple(
            SettlementLine(
                line_id=str(line_id),
                settlement_id=str(stored_settlement_id),
                provider_ref=str(provider_ref),
                amount=Money(amount, str(currency)),
                statement_ref=str(statement_ref),
            )
            for (
                line_id,
                stored_settlement_id,
                provider_ref,
                amount,
                currency,
                statement_ref,
            ) in cursor.fetchall()
        )


    @staticmethod
    def _to_settlement(row: tuple[object, ...]) -> SettlementRecord:
        (
            settlement_id,
            provider_settlement_ref,
            statement_hash,
            gross_amount,
            fees,
            net_amount,
            currency,
            settled_at,
            status,
        ) = row
        return SettlementRecord(
            settlement_id=str(settlement_id),
            provider_settlement_ref=str(provider_settlement_ref),
            statement_hash=str(statement_hash),
            gross=Money(gross_amount, str(currency)),
            fees=Money(fees, str(currency)),
            net=Money(net_amount, str(currency)),
            settled_at=settled_at,
            status=SettlementStatus(str(status)),
        )


class PostgresReconciliationRepository(ReconciliationRepository):
    """Durable discrepancy/review state for settlement reconciliation."""

    def __init__(self, connection: DBConnection) -> None:
        self._connection = connection

    def add(self, item: ReconciliationItem) -> None:
        self._connection.execute(
            """
            insert into reconciliation_item (
                reconciliation_id,
                settlement_id,
                reason_code,
                expected_amount,
                observed_amount,
                currency,
                status,
                created_at,
                resolved_at
            )
            values (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                item.reconciliation_id,
                item.settlement_id,
                item.reason_code,
                item.expected_amount.amount if item.expected_amount else None,
                item.observed_amount.amount if item.observed_amount else None,
                item.currency,
                item.status.value,
                item.created_at,
                item.resolved_at,
            ),
        )

    def get(self, reconciliation_id: str) -> ReconciliationItem | None:
        cursor = self._connection.execute(
            """
            select
                reconciliation_id,
                settlement_id,
                reason_code,
                expected_amount,
                observed_amount,
                currency,
                status,
                created_at,
                resolved_at
            from reconciliation_item
            where reconciliation_id = %s
            """,
            (reconciliation_id,),
        )
        row = cursor.fetchone()
        if row is None:
            return None
        return self._to_item(row)

    def resolve(self, item: ReconciliationItem) -> ReconciliationItem:
        if item.status is not ReconciliationStatus.RESOLVED:
            raise ValueError("only resolved reconciliation items can be persisted")
        if item.resolved_at is None:
            raise ValueError("resolved item requires resolved_at")
        cursor = self._connection.execute(
            """
            update reconciliation_item
            set status = 'resolved',
                resolved_at = %s
            where reconciliation_id = %s
              and status = 'open'
            returning
                reconciliation_id,
                settlement_id,
                reason_code,
                expected_amount,
                observed_amount,
                currency,
                status,
                created_at,
                resolved_at
            """,
            (item.resolved_at, item.reconciliation_id),
        )
        row = cursor.fetchone()
        if row is not None:
            return self._to_item(row)
        existing = self.get(item.reconciliation_id)
        if existing is None:
            raise KeyError(
                f"unknown reconciliation item: {item.reconciliation_id}"
            )
        if existing == item:
            return existing
        raise IntegrityViolation("reconciliation item was already finalized")

    @staticmethod
    def _to_item(row: tuple[object, ...]) -> ReconciliationItem:
        (
            reconciliation_id,
            settlement_id,
            reason_code,
            expected_amount,
            observed_amount,
            currency,
            status,
            created_at,
            resolved_at,
        ) = row
        return ReconciliationItem(
            reconciliation_id=str(reconciliation_id),
            settlement_id=str(settlement_id),
            reason_code=str(reason_code),
            expected_amount=(
                Money(expected_amount, str(currency))
                if expected_amount is not None
                else None
            ),
            observed_amount=(
                Money(observed_amount, str(currency))
                if observed_amount is not None
                else None
            ),
            currency=str(currency),
            status=ReconciliationStatus(str(status)),
            created_at=created_at,
            resolved_at=resolved_at,
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
