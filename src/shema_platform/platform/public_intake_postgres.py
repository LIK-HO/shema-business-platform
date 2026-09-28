from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime, timedelta

from shema_platform.application.public_intake import (
    CounterpartyPreflightSnapshot,
    IdentityMatch,
    IntakeStatus,
    PreflightDecision,
    PublicIntakePayload,
    PublicIntakeRateLimited,
    PublicIntakeRecord,
)
from shema_platform.foundation.errors import IdempotencyConflict, IntegrityViolation
from shema_platform.platform.postgres import DBConnection


class PublicIntakeOutboxEvent:
    def __init__(
        self,
        *,
        event_id: str,
        request_id: str,
        event_type: str,
        payload: dict[str, object],
        occurred_at: datetime,
        notify_operator: bool,
    ) -> None:
        self.event_id = event_id
        self.request_id = request_id
        self.event_type = event_type
        self.payload = payload
        self.occurred_at = occurred_at
        self.notify_operator = notify_operator


class PostgresPublicIntakeRepository:
    """Transactional repository for the isolated public-intake database."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory
        self._connection: DBConnection | None = None

    def __enter__(self) -> PostgresPublicIntakeRepository:
        if self._connection is not None:
            raise RuntimeError("public intake repository is already active")
        self._connection = self._connection_factory()
        return self

    @property
    def connection(self) -> DBConnection:
        if self._connection is None:
            raise RuntimeError("public intake repository is not active")
        return self._connection

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        connection = self._connection
        self._connection = None
        if connection is None:
            return False
        try:
            if exc_type is None:
                connection.commit()
            else:
                connection.rollback()
        finally:
            connection.close()
        return False

    def get_by_request_id(self, request_id: str) -> PublicIntakeRecord | None:
        row = self.connection.execute(
            "select idempotency_key from intake_request where request_id = %s",
            (request_id,),
        ).fetchone()
        if row is None:
            return None
        return self.get_by_idempotency_key(str(row[0]))

    def get_by_idempotency_key(self, key: str) -> PublicIntakeRecord | None:
        row = self.connection.execute(
            """
            select
                request_id,
                correlation_id,
                idempotency_key,
                request_hash,
                status,
                service_type,
                location,
                preferred_date_or_period,
                work_or_cargo_description,
                contact_name,
                contact_channel,
                approximate_volume_or_weight,
                access_or_lifting_constraints,
                company_name,
                inn,
                ogrn_or_ogrnip,
                comments,
                utm_source,
                utm_medium,
                utm_campaign,
                referrer,
                entry_surface,
                preflight_snapshot_id,
                created_at,
                projected_at
            from intake_request
            where idempotency_key = %s
            """,
            (key,),
        ).fetchone()
        if row is None:
            return None

        snapshot = self._get_snapshot(str(row[22]))
        if snapshot is None:
            raise IntegrityViolation(
                "intake request references missing preflight snapshot"
            )

        return PublicIntakeRecord(
            request_id=str(row[0]),
            correlation_id=str(row[1]),
            idempotency_key=str(row[2]),
            request_hash=str(row[3]),
            status=IntakeStatus(str(row[4])),
            payload=PublicIntakePayload(
                service_type=str(row[5]),
                location=str(row[6]),
                preferred_date_or_period=str(row[7]),
                work_or_cargo_description=str(row[8]),
                contact_name=str(row[9]),
                contact_channel=str(row[10]),
                approximate_volume_or_weight=(
                    str(row[11]) if row[11] is not None else None
                ),
                access_or_lifting_constraints=(
                    str(row[12]) if row[12] is not None else None
                ),
                company_name=str(row[13]) if row[13] is not None else None,
                inn=str(row[14]) if row[14] is not None else None,
                ogrn_or_ogrnip=str(row[15]) if row[15] is not None else None,
                comments=str(row[16]) if row[16] is not None else None,
                utm_source=str(row[17]) if row[17] is not None else None,
                utm_medium=str(row[18]) if row[18] is not None else None,
                utm_campaign=str(row[19]) if row[19] is not None else None,
                referrer=str(row[20]) if row[20] is not None else None,
                entry_surface=str(row[21]),
            ),
            preflight=snapshot,
            created_at=row[23],
            projected_at=row[24],
        )

    def add(self, record: PublicIntakeRecord) -> None:
        self.connection.execute(
            """
            insert into intake_request (
                request_id,
                correlation_id,
                idempotency_key,
                request_hash,
                status,
                service_type,
                location,
                preferred_date_or_period,
                work_or_cargo_description,
                contact_name,
                contact_channel,
                approximate_volume_or_weight,
                access_or_lifting_constraints,
                company_name,
                inn,
                ogrn_or_ogrnip,
                comments,
                utm_source,
                utm_medium,
                utm_campaign,
                referrer,
                entry_surface,
                preflight_snapshot_id,
                preflight_decision,
                created_at
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
            )
            on conflict (idempotency_key) do nothing
            """,
            (
                record.request_id,
                record.correlation_id,
                record.idempotency_key,
                record.request_hash,
                record.status.value,
                record.payload.service_type,
                record.payload.location,
                record.payload.preferred_date_or_period,
                record.payload.work_or_cargo_description,
                record.payload.contact_name,
                record.payload.contact_channel,
                record.payload.approximate_volume_or_weight,
                record.payload.access_or_lifting_constraints,
                record.payload.company_name,
                record.payload.inn,
                record.payload.ogrn_or_ogrnip,
                record.payload.comments,
                record.payload.utm_source,
                record.payload.utm_medium,
                record.payload.utm_campaign,
                record.payload.referrer,
                record.payload.entry_surface,
                record.preflight.snapshot_id,
                record.preflight.decision.value,
                record.created_at,
            ),
        )
        existing = self.get_by_idempotency_key(record.idempotency_key)
        if existing is None:
            raise IntegrityViolation("public intake request disappeared after insert")
        if existing.request_hash != record.request_hash:
            raise IdempotencyConflict("idempotency key reused with different payload")

    def append_outbox(
        self,
        *,
        event_id: str,
        request_id: str,
        event_type: str,
        payload: dict[str, object],
        occurred_at: datetime,
        notify_operator: bool,
    ) -> None:
        encoded = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        self.connection.execute(
            """
            insert into intake_outbox_event (
                event_id,
                request_id,
                event_type,
                payload,
                occurred_at,
                notify_operator
            )
            values (%s, %s, %s, %s::jsonb, %s, %s)
            on conflict (event_id) do nothing
            """,
            (
                event_id,
                request_id,
                event_type,
                encoded,
                occurred_at,
                notify_operator,
            ),
        )

    def claim_pending(
        self,
        worker_id: str,
        *,
        lease_seconds: int,
        now: datetime,
        limit: int = 100,
    ) -> tuple[PublicIntakeOutboxEvent, ...]:
        if not worker_id.strip():
            raise ValueError("worker_id is required")
        if lease_seconds <= 0:
            raise ValueError("lease_seconds must be positive")
        if limit < 1:
            raise ValueError("limit must be positive")
        lease_until = now + timedelta(seconds=lease_seconds)
        rows = self.connection.execute(
            """
            with claimed as (
                select event_id
                from intake_outbox_event
                where published_at is null
                  and (
                      delivery_lease_until is null
                      or delivery_lease_until <= %s
                  )
                order by occurred_at, event_id
                for update skip locked
                limit %s
            )
            update intake_outbox_event as event
            set delivery_worker_id = %s,
                delivery_lease_until = %s,
                delivery_attempt = delivery_attempt + 1
            from claimed
            where event.event_id = claimed.event_id
            returning
                event.event_id,
                event.request_id,
                event.event_type,
                event.payload,
                event.occurred_at,
                event.notify_operator
            """,
            (now, limit, worker_id, lease_until),
        ).fetchall()
        return tuple(
            PublicIntakeOutboxEvent(
                event_id=str(row[0]),
                request_id=str(row[1]),
                event_type=str(row[2]),
                payload=dict(row[3]),
                occurred_at=row[4],
                notify_operator=bool(row[5]),
            )
            for row in rows
        )

    def mark_outbox_published(
        self,
        event_id: str,
        *,
        worker_id: str,
        now: datetime,
    ) -> None:
        updated = self.connection.execute(
            """
            update intake_outbox_event
            set published_at = %s,
                delivery_worker_id = null,
                delivery_lease_until = null
            where event_id = %s
              and published_at is null
              and delivery_worker_id = %s
            returning event_id
            """,
            (now, event_id, worker_id),
        ).fetchone()
        if updated is None:
            raise IntegrityViolation("intake outbox publication rejected")

    def mark_projected(self, request_id: str, *, now: datetime) -> None:
        updated = self.connection.execute(
            """
            update intake_request
            set projected_at = coalesce(projected_at, %s)
            where request_id = %s
            returning request_id
            """,
            (now, request_id),
        ).fetchone()
        if updated is None:
            raise IntegrityViolation("intake request projection marker missing")

    def consume_budget(
        self,
        *,
        public_client_key: str,
        budget: str,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> None:
        if limit < 1:
            raise ValueError("limit must be positive")
        epoch = int(now.timestamp())
        window_start = datetime.fromtimestamp(
            epoch - (epoch % window_seconds),
            tz=UTC,
        )
        key_hash = hashlib.sha256(
            public_client_key.strip().encode("utf-8")
        ).hexdigest()

        row = self.connection.execute(
            """
            insert into intake_rate_limit (
                public_client_key_hash,
                budget,
                window_started_at,
                used_count
            )
            values (%s, %s, %s, 1)
            on conflict (
                public_client_key_hash,
                budget,
                window_started_at
            ) do update
            set used_count = intake_rate_limit.used_count + 1
            where intake_rate_limit.used_count < %s
            returning used_count
            """,
            (key_hash, budget, window_start, limit),
        ).fetchone()
        if row is None:
            raise PublicIntakeRateLimited(
                f"{budget} rate limit exceeded",
                budget=budget,
            )

    def get_preflight_cache(
        self,
        cache_key: str,
        *,
        now: datetime,
    ) -> CounterpartyPreflightSnapshot | None:
        row = self.connection.execute(
            """
            select
                snapshot_id,
                identifier_type,
                normalized_identifier,
                decision,
                identity_match,
                canonical_name,
                legal_status,
                source_ref,
                provider_id,
                observed_at,
                expires_at,
                flags,
                error_code
            from intake_preflight_snapshot
            where cache_key = %s
              and expires_at > %s
            order by captured_at desc
            limit 1
            """,
            (cache_key, now),
        ).fetchone()
        return self._snapshot_from_row(row) if row else None

    def save_preflight_cache(
        self,
        cache_key: str,
        snapshot: CounterpartyPreflightSnapshot,
    ) -> None:
        self.connection.execute(
            """
            insert into intake_preflight_snapshot (
                snapshot_id,
                cache_key,
                request_id,
                identifier_type,
                normalized_identifier,
                decision,
                identity_match,
                canonical_name,
                legal_status,
                source_ref,
                provider_id,
                observed_at,
                expires_at,
                flags,
                error_code
            )
            values (
                %s, %s, null, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
            )
            on conflict (cache_key) where cache_key is not null
            do update set
                snapshot_id = excluded.snapshot_id,
                identifier_type = excluded.identifier_type,
                normalized_identifier = excluded.normalized_identifier,
                decision = excluded.decision,
                identity_match = excluded.identity_match,
                canonical_name = excluded.canonical_name,
                legal_status = excluded.legal_status,
                source_ref = excluded.source_ref,
                provider_id = excluded.provider_id,
                observed_at = excluded.observed_at,
                expires_at = excluded.expires_at,
                flags = excluded.flags,
                error_code = excluded.error_code,
                captured_at = now()
            """,
            (
                snapshot.snapshot_id,
                cache_key,
                snapshot.identifier_type,
                snapshot.normalized_identifier,
                snapshot.decision.value,
                snapshot.identity_match.value,
                snapshot.canonical_name,
                snapshot.legal_status,
                snapshot.source_ref,
                snapshot.provider_id,
                snapshot.observed_at,
                snapshot.expires_at,
                json.dumps(snapshot.flags, ensure_ascii=False),
                snapshot.error_code,
            ),
        )

    def save_preflight_snapshot(
        self,
        snapshot: CounterpartyPreflightSnapshot,
        *,
        request_id: str,
    ) -> None:
        self.connection.execute(
            """
            insert into intake_preflight_snapshot (
                snapshot_id,
                request_id,
                identifier_type,
                normalized_identifier,
                decision,
                identity_match,
                canonical_name,
                legal_status,
                source_ref,
                provider_id,
                observed_at,
                expires_at,
                flags,
                error_code
            )
            values (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s
            )
            on conflict (snapshot_id) do nothing
            """,
            (
                snapshot.snapshot_id,
                request_id,
                snapshot.identifier_type,
                snapshot.normalized_identifier,
                snapshot.decision.value,
                snapshot.identity_match.value,
                snapshot.canonical_name,
                snapshot.legal_status,
                snapshot.source_ref,
                snapshot.provider_id,
                snapshot.observed_at,
                snapshot.expires_at,
                json.dumps(snapshot.flags, ensure_ascii=False),
                snapshot.error_code,
            ),
        )

    def _get_snapshot(self, snapshot_id: str) -> CounterpartyPreflightSnapshot | None:
        row = self.connection.execute(
            """
            select
                snapshot_id,
                identifier_type,
                normalized_identifier,
                decision,
                identity_match,
                canonical_name,
                legal_status,
                source_ref,
                provider_id,
                observed_at,
                expires_at,
                flags,
                error_code
            from intake_preflight_snapshot
            where snapshot_id = %s
            """,
            (snapshot_id,),
        ).fetchone()
        return self._snapshot_from_row(row) if row else None

    @staticmethod
    def _snapshot_from_row(row) -> CounterpartyPreflightSnapshot:
        return CounterpartyPreflightSnapshot(
            snapshot_id=str(row[0]),
            identifier_type=str(row[1]) if row[1] is not None else None,
            normalized_identifier=(
                str(row[2]) if row[2] is not None else None
            ),
            decision=PreflightDecision(str(row[3])),
            identity_match=IdentityMatch(str(row[4])),
            canonical_name=str(row[5]) if row[5] is not None else None,
            legal_status=str(row[6]) if row[6] is not None else None,
            source_ref=str(row[7]) if row[7] is not None else None,
            provider_id=str(row[8]) if row[8] is not None else None,
            observed_at=row[9],
            expires_at=row[10],
            flags=tuple(row[11] or ()),
            error_code=str(row[12]) if row[12] is not None else None,
        )


class PostgresPublicRequestProjection:
    """Projects accepted business context into canonical Shema PostgreSQL."""

    def __init__(
        self,
        unit_of_work_factory,
        *,
        clock=lambda: datetime.now(UTC),
    ):
        self._unit_of_work_factory = unit_of_work_factory
        self._clock = clock

    def project(self, record: PublicIntakeRecord) -> None:
        now = self._clock()
        with self._unit_of_work_factory() as uow:
            connection = getattr(uow, "connection", None)
            if connection is None:
                raise RuntimeError(
                    "canonical unit of work exposes no database connection"
                )

            connection.execute(
                """
                insert into public_request_context (
                    request_id,
                    correlation_id,
                    status,
                    service_type,
                    location,
                    preferred_date_or_period,
                    work_or_cargo_description,
                    contact_name,
                    contact_channel,
                    company_name,
                    inn,
                    ogrn_or_ogrnip,
                    preflight_snapshot_id,
                    preflight_decision,
                    preflight_identity_match,
                    source_attribution,
                    created_at,
                    projected_at,
                    updated_at
                )
                values (
                    %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s,
                    %s::jsonb, %s, %s, %s
                )
                on conflict (request_id) do update set
                    preflight_snapshot_id = excluded.preflight_snapshot_id,
                    preflight_decision = excluded.preflight_decision,
                    preflight_identity_match = excluded.preflight_identity_match,
                    projected_at = excluded.projected_at,
                    updated_at = excluded.updated_at
                """,
                (
                    record.request_id,
                    record.correlation_id,
                    record.status.value,
                    record.payload.service_type,
                    record.payload.location,
                    record.payload.preferred_date_or_period,
                    record.payload.work_or_cargo_description,
                    record.payload.contact_name,
                    record.payload.contact_channel,
                    record.payload.company_name,
                    record.payload.inn,
                    record.payload.ogrn_or_ogrnip,
                    record.preflight.snapshot_id,
                    record.preflight.decision.value,
                    record.preflight.identity_match.value,
                    json.dumps(
                        {
                            "utm_source": record.payload.utm_source,
                            "utm_medium": record.payload.utm_medium,
                            "utm_campaign": record.payload.utm_campaign,
                            "referrer": record.payload.referrer,
                            "entry_surface": record.payload.entry_surface,
                        },
                        ensure_ascii=False,
                        sort_keys=True,
                    ),
                    record.created_at,
                    now,
                    now,
                ),
            )

            if record.status is IntakeStatus.QUARANTINED_SPAM:
                return

            self._project_notification(
                connection,
                record,
                event_id=f"public-intake:{record.request_id}",
                event_type="new_client_request",
                severity="INFO",
                payload={
                    "request_id": record.request_id,
                    "service_type": record.payload.service_type,
                    "location": record.payload.location,
                    "preflight_decision": record.preflight.decision.value,
                    "preflight_snapshot_id": record.preflight.snapshot_id,
                },
                created_at=now,
            )

            if "PROVIDER_UNAVAILABLE" in record.preflight.flags:
                self._project_notification(
                    connection,
                    record,
                    event_id=f"public-intake:{record.request_id}:provider",
                    event_type="provider_unavailable",
                    severity="ATTENTION",
                    payload={
                        "request_id": record.request_id,
                        "preflight_snapshot_id": record.preflight.snapshot_id,
                    },
                    created_at=now,
                )
            elif record.preflight.decision is record.preflight.decision.ATTENTION:
                self._project_notification(
                    connection,
                    record,
                    event_id=f"public-intake:{record.request_id}:attention",
                    event_type="counterparty_attention",
                    severity="ATTENTION",
                    payload={
                        "request_id": record.request_id,
                        "preflight_snapshot_id": record.preflight.snapshot_id,
                        "flags": list(record.preflight.flags),
                    },
                    created_at=now,
                )
            elif record.preflight.decision is record.preflight.decision.BLOCKING_FACT:
                self._project_notification(
                    connection,
                    record,
                    event_id=f"public-intake:{record.request_id}:blocking",
                    event_type="counterparty_blocking_fact",
                    severity="HIGH",
                    payload={
                        "request_id": record.request_id,
                        "preflight_snapshot_id": record.preflight.snapshot_id,
                        "flags": list(record.preflight.flags),
                    },
                    created_at=now,
                )

    @staticmethod
    def _project_notification(
        connection: DBConnection,
        record: PublicIntakeRecord,
        *,
        event_id: str,
        event_type: str,
        severity: str,
        payload: dict[str, object],
        created_at: datetime,
    ) -> None:
        connection.execute(
            """
            insert into operator_notification (
                event_id,
                request_id,
                event_type,
                severity,
                payload,
                created_at
            )
            values (%s, %s, %s, %s, %s::jsonb, %s)
            on conflict (event_id) do nothing
            """,
            (
                event_id,
                record.request_id,
                event_type,
                severity,
                json.dumps(payload, ensure_ascii=False, sort_keys=True),
                created_at,
            ),
        )


class PostgresOperatorNotificationReader:
    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def list_unread(self, *, limit: int = 50):
        with self._connection_factory() as connection:
            rows = connection.execute(
                """
                select event_id, request_id, event_type, severity, payload, created_at
                from operator_notification
                where read_at is null
                order by created_at desc, event_id desc
                limit %s
                """,
                (limit,),
            ).fetchall()
        return tuple(
            {
                "eventId": str(row[0]),
                "requestId": str(row[1]),
                "eventType": str(row[2]),
                "severity": str(row[3]),
                "payload": dict(row[4]),
                "createdAt": row[5].isoformat(),
            }
            for row in rows
        )


class PublicRequestUnavailable(RuntimeError):
    pass


class PublicIntakeOutboxDispatcher:
    """Replay-safe bridge from the isolated intake outbox into Shema."""

    def __init__(
        self,
        intake_repository_factory,
        projector,
        *,
        clock=lambda: datetime.now(UTC),
    ):
        self._intake_repository_factory = intake_repository_factory
        self._projector = projector
        self._clock = clock

    def dispatch_pending(self, *, limit: int = 100) -> int:
        projected = 0
        with self._intake_repository_factory() as repository:
            events = repository.pending_outbox(limit=limit)

        for event in events:
            if not event.notify_operator:
                with self._intake_repository_factory() as repository:
                    repository.mark_outbox_published(
                        event.event_id,
                        now=self._clock(),
                    )
                continue

            with self._intake_repository_factory() as repository:
                record = repository.get_by_request_id(event.request_id)
            if record is None:
                raise IntegrityViolation(
                    "intake outbox event references missing request"
                )

            self._projector.project(record)
            with self._intake_repository_factory() as repository:
                repository.mark_projected(
                    record.request_id,
                    now=self._clock(),
                )
                repository.mark_outbox_published(
                    event.event_id,
                    now=self._clock(),
                )
            projected += 1

        return projected
