from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from hashlib import sha256
from typing import Protocol
from uuid import uuid4

from shema_platform.foundation.errors import IdempotencyConflict


@dataclass(frozen=True, slots=True)
class PublicIdempotencyReservation:
    request_id: str
    state: str


class PreflightDecision(StrEnum):
    NORMAL = "NORMAL"
    ATTENTION = "ATTENTION"
    BLOCKING_FACT = "BLOCKING_FACT"
    UNKNOWN = "UNKNOWN"
    CONFLICTING = "CONFLICTING"


class IdentityMatch(StrEnum):
    MATCH = "MATCH"
    NAME_MISMATCH = "NAME_MISMATCH"
    NOT_CHECKED = "NOT_CHECKED"


class IntakeStatus(StrEnum):
    ACCEPTED = "ACCEPTED"
    QUARANTINED_SPAM = "QUARANTINED_SPAM"


@dataclass(frozen=True, slots=True)
class PublicIntakePayload:
    service_type: str
    location: str
    preferred_date_or_period: str
    work_or_cargo_description: str
    contact_name: str
    contact_channel: str
    approximate_volume_or_weight: str | None = None
    access_or_lifting_constraints: str | None = None
    company_name: str | None = None
    inn: str | None = None
    ogrn_or_ogrnip: str | None = None
    comments: str | None = None
    utm_source: str | None = None
    utm_medium: str | None = None
    utm_campaign: str | None = None
    referrer: str | None = None
    entry_surface: str = "public_web"

    def canonical_json(self) -> str:
        payload = {
            "service_type": self.service_type.strip(),
            "location": self.location.strip(),
            "preferred_date_or_period": self.preferred_date_or_period.strip(),
            "work_or_cargo_description": self.work_or_cargo_description.strip(),
            "contact_name": self.contact_name.strip(),
            "contact_channel": self.contact_channel.strip(),
            "approximate_volume_or_weight": (self.approximate_volume_or_weight or "").strip(),
            "access_or_lifting_constraints": (
                (self.access_or_lifting_constraints or "").strip()
            ),
            "company_name": (self.company_name or "").strip(),
            "inn": (self.inn or "").strip(),
            "ogrn_or_ogrnip": (self.ogrn_or_ogrnip or "").strip(),
            "comments": (self.comments or "").strip(),
            "utm_source": (self.utm_source or "").strip(),
            "utm_medium": (self.utm_medium or "").strip(),
            "utm_campaign": (self.utm_campaign or "").strip(),
            "referrer": (self.referrer or "").strip(),
            "entry_surface": self.entry_surface.strip(),
        }
        return json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

    @property
    def request_hash(self) -> str:
        return sha256(self.canonical_json().encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class CounterpartyPreflightSnapshot:
    snapshot_id: str
    identifier_type: str | None
    normalized_identifier: str | None
    decision: PreflightDecision
    identity_match: IdentityMatch
    canonical_name: str | None
    legal_status: str | None
    source_ref: str | None
    provider_id: str | None
    observed_at: datetime
    expires_at: datetime
    flags: tuple[str, ...] = ()
    error_code: str | None = None


@dataclass(frozen=True, slots=True)
class PublicIntakeRecord:
    request_id: str
    correlation_id: str
    idempotency_key: str
    request_hash: str
    status: IntakeStatus
    payload: PublicIntakePayload
    preflight: CounterpartyPreflightSnapshot
    created_at: datetime
    projected_at: datetime | None = None


@dataclass(frozen=True, slots=True)
class PublicIntakeResult:
    record: PublicIntakeRecord
    projection_status: str
    deduplicated: bool


class PublicIntakeRateLimited(RuntimeError):
    def __init__(self, message: str, *, budget: str) -> None:
        super().__init__(message)
        self.budget = budget


class PublicIntakeSecurityRejected(RuntimeError):
    pass


class PublicIntakeRepository(Protocol):
    def reserve_idempotency(
        self,
        *,
        key: str,
        request_hash: str,
        request_id: str,
        now: datetime,
        lease_seconds: int,
    ) -> PublicIdempotencyReservation: ...

    def complete_idempotency(
        self,
        *,
        key: str,
        request_id: str,
        now: datetime,
    ) -> None: ...

    def get_by_idempotency_key(self, key: str) -> PublicIntakeRecord | None: ...

    def get_preflight_cache(
        self,
        cache_key: str,
        *,
        now: datetime,
    ) -> CounterpartyPreflightSnapshot | None: ...

    def consume_budget(
        self,
        *,
        public_client_key: str,
        budget: str,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> None: ...

    def consume_global_circuit(
        self,
        *,
        limit: int,
        window_seconds: int,
        now: datetime,
    ) -> None: ...

    def ensure_outbox_capacity(self, *, max_pending: int) -> None: ...

    def add(self, record: PublicIntakeRecord) -> None: ...

    def append_outbox(
        self,
        *,
        event_id: str,
        request_id: str,
        event_type: str,
        payload: dict[str, object],
        occurred_at: datetime,
        notify_operator: bool,
    ) -> None: ...

    def save_preflight_cache(
        self,
        cache_key: str,
        snapshot: CounterpartyPreflightSnapshot,
    ) -> None: ...

    def save_preflight_snapshot(
        self,
        snapshot: CounterpartyPreflightSnapshot,
        *,
        request_id: str,
    ) -> None: ...

    def mark_projected(self, request_id: str, *, now: datetime) -> None: ...


class PublicRequestProjector(Protocol):
    def project(self, record: PublicIntakeRecord) -> None: ...


class PublicCounterpartyPreflight(Protocol):
    def run(
        self,
        *,
        payload: PublicIntakePayload,
        request_id: str,
        correlation_id: str,
        public_client_key: str,
        now: datetime,
    ) -> CounterpartyPreflightSnapshot: ...


class PublicIntakeService:
    """Server-authoritative public intake with durable isolated storage.

    The intake commit is the first durable authority. Projection into Shema is
    intentionally separate so a Shema outage cannot delete an already-accepted
    public request.
    """

    def __init__(
        self,
        repository_factory,
        *,
        preflight: PublicCounterpartyPreflight,
        projector: PublicRequestProjector,
        submission_limit: int = 5,
        lookup_limit: int = 20,
        window_seconds: int = 600,
        global_submission_limit: int = 100,
        max_pending_outbox: int = 1000,
        require_bot_challenge: bool = True,
        enforce_edge_proof: bool = True,
        allowed_origins: frozenset[str] = frozenset(),
        clock=lambda: datetime.now(UTC),
    ) -> None:
        if submission_limit < 1 or lookup_limit < 1 or global_submission_limit < 1:
            raise ValueError("rate limits must be positive")
        if max_pending_outbox < 1:
            raise ValueError("max_pending_outbox must be positive")
        if window_seconds < 1:
            raise ValueError("window_seconds must be positive")
        self._repository_factory = repository_factory
        self._preflight = preflight
        self._projector = projector
        self._submission_limit = submission_limit
        self._lookup_limit = lookup_limit
        self._global_submission_limit = global_submission_limit
        self._max_pending_outbox = max_pending_outbox
        self._window_seconds = window_seconds
        if not require_bot_challenge:
            raise ValueError("public intake bot challenge cannot be disabled")
        self._require_bot_challenge = True
        self._enforce_edge_proof = enforce_edge_proof
        self._allowed_origins = frozenset(
            item.rstrip("/") for item in allowed_origins
        )
        self._clock = clock

    def submit(
        self,
        *,
        payload: PublicIntakePayload,
        idempotency_key: str,
        public_client_key: str,
        origin: str | None,
        bot_challenge_passed: bool,
        correlation_id: str,
        honeypot_value: str = "",
    ) -> PublicIntakeResult:
        normalized_idempotency_key = idempotency_key.strip()
        self._validate_edge_proof(
            idempotency_key=normalized_idempotency_key,
            public_client_key=public_client_key,
            origin=origin,
            bot_challenge_passed=bot_challenge_passed,
            honeypot_value=honeypot_value,
        )
        request_id = str(uuid4())
        with self._repository_factory() as repository:
            reservation = repository.reserve_idempotency(
                key=normalized_idempotency_key,
                request_hash=payload.request_hash,
                request_id=request_id,
                now=self._clock(),
                lease_seconds=120,
            )
            if reservation.state == "COMPLETE":
                existing = repository.get_by_idempotency_key(
                    normalized_idempotency_key
                )
                if existing is None:
                    raise IdempotencyConflict(
                        "completed public-intake reservation references missing request"
                    )
                return PublicIntakeResult(
                    record=existing,
                    projection_status=(
                        "PROJECTED"
                        if existing.projected_at
                        else "PENDING_PROJECTION"
                    ),
                    deduplicated=True,
                )
            if reservation.state == "IN_PROGRESS":
                raise IdempotencyConflict(
                    "public intake request with this idempotency key is already in progress"
                )

        return self._submit_reserved(
            payload=payload,
            idempotency_key=normalized_idempotency_key,
            public_client_key=public_client_key,
            origin=origin,
            bot_challenge_passed=bot_challenge_passed,
            correlation_id=correlation_id,
            honeypot_value=honeypot_value,
            request_id=request_id,
        )

    def _submit_reserved(
        self,
        *,
        payload: PublicIntakePayload,
        idempotency_key: str,
        public_client_key: str,
        origin: str | None,
        bot_challenge_passed: bool,
        correlation_id: str,
        honeypot_value: str = "",
        request_id: str,
    ) -> PublicIntakeResult:
        self._validate_edge_proof(
            idempotency_key=idempotency_key,
            public_client_key=public_client_key,
            origin=origin,
            bot_challenge_passed=bot_challenge_passed,
            honeypot_value=honeypot_value,
        )
        now = self._clock()

        with self._repository_factory() as repository:
            repository.consume_global_circuit(
                limit=self._global_submission_limit,
                window_seconds=self._window_seconds,
                now=now,
            )
            repository.ensure_outbox_capacity(
                max_pending=self._max_pending_outbox,
            )
            existing = repository.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                if existing.request_hash != payload.request_hash:
                    raise IdempotencyConflict(
                        "idempotency key reused with different payload"
                    )
                return PublicIntakeResult(
                    record=existing,
                    projection_status=(
                        "PROJECTED"
                        if existing.projected_at
                        else "PENDING_PROJECTION"
                    ),
                    deduplicated=True,
                )

            repository.consume_budget(
                public_client_key=public_client_key,
                budget="submission",
                limit=self._submission_limit,
                window_seconds=self._window_seconds,
                now=now,
            )

        preflight = self._preflight.run(
            payload=payload,
            request_id=request_id,
            correlation_id=correlation_id,
            public_client_key=public_client_key,
            now=now,
        )
        event_id = str(uuid4())
        notify_operator = not bool(honeypot_value.strip())
        status = (
            IntakeStatus.ACCEPTED
            if notify_operator
            else IntakeStatus.QUARANTINED_SPAM
        )
        record = PublicIntakeRecord(
            request_id=request_id,
            correlation_id=correlation_id,
            idempotency_key=idempotency_key,
            request_hash=payload.request_hash,
            status=status,
            payload=payload,
            preflight=preflight,
            created_at=now,
        )

        with self._repository_factory() as repository:
            existing = repository.get_by_idempotency_key(idempotency_key)
            if existing is not None:
                if existing.request_hash != payload.request_hash:
                    raise IdempotencyConflict(
                        "idempotency key reused with different payload"
                    )
                return PublicIntakeResult(
                    record=existing,
                    projection_status=(
                        "PROJECTED"
                        if existing.projected_at
                        else "PENDING_PROJECTION"
                    ),
                    deduplicated=True,
                )

            repository.ensure_outbox_capacity(
                max_pending=self._max_pending_outbox,
            )
            repository.save_preflight_snapshot(
                preflight,
                request_id=request_id,
            )
            repository.add(record)
            repository.append_outbox(
                event_id=event_id,
                request_id=request_id,
                event_type=(
                    "new_client_request"
                    if notify_operator
                    else "spam_or_abuse_quarantined"
                ),
                payload={
                    "request_id": request_id,
                    "correlation_id": correlation_id,
                    "status": status.value,
                    "preflight_snapshot_id": preflight.snapshot_id,
                    "preflight_decision": preflight.decision.value,
                    "entry_surface": payload.entry_surface,
                },
                occurred_at=now,
                notify_operator=notify_operator,
            )
            repository.complete_idempotency(
                key=idempotency_key,
                request_id=request_id,
                now=self._clock(),
            )
            if notify_operator and preflight.decision is PreflightDecision.ATTENTION:
                repository.append_outbox(
                    event_id=f"{event_id}:attention",
                    request_id=request_id,
                    event_type="counterparty_attention",
                    payload={
                        "request_id": request_id,
                        "preflight_snapshot_id": preflight.snapshot_id,
                    },
                    occurred_at=now,
                    notify_operator=True,
                )
            elif notify_operator and preflight.decision is PreflightDecision.BLOCKING_FACT:
                repository.append_outbox(
                    event_id=f"{event_id}:blocking",
                    request_id=request_id,
                    event_type="counterparty_blocking_fact",
                    payload={
                        "request_id": request_id,
                        "preflight_snapshot_id": preflight.snapshot_id,
                    },
                    occurred_at=now,
                    notify_operator=True,
                )
            elif notify_operator and "PROVIDER_UNAVAILABLE" in preflight.flags:
                repository.append_outbox(
                    event_id=f"{event_id}:provider",
                    request_id=request_id,
                    event_type="provider_unavailable",
                    payload={
                        "request_id": request_id,
                        "preflight_snapshot_id": preflight.snapshot_id,
                    },
                    occurred_at=now,
                    notify_operator=True,
                )

        projection_status = "PENDING_PROJECTION"
        try:
            self._projector.project(record)
            with self._repository_factory() as repository:
                repository.mark_projected(request_id, now=self._clock())
            projection_status = "PROJECTED"
        except Exception:
            projection_status = "PENDING_PROJECTION"

        return PublicIntakeResult(
            record=record,
            projection_status=projection_status,
            deduplicated=False,
        )

    def _validate_edge_proof(
        self,
        *,
        idempotency_key: str,
        public_client_key: str,
        origin: str | None,
        bot_challenge_passed: bool,
        honeypot_value: str,
    ) -> None:
        if not 8 <= len(idempotency_key.strip()) <= 128:
            raise PublicIntakeSecurityRejected(
                "Idempotency-Key must be 8-128 characters"
            )
        if not 8 <= len(public_client_key.strip()) <= 128:
            raise PublicIntakeSecurityRejected(
                "public client key must be 8-128 characters"
            )
        if self._enforce_edge_proof:
            if not self._allowed_origins:
                raise PublicIntakeSecurityRejected(
                    "public origin allowlist is not configured"
                )
            normalized_origin = (origin or "").rstrip("/")
            if normalized_origin not in self._allowed_origins:
                raise PublicIntakeSecurityRejected("origin is not allowed")
            if not bot_challenge_passed:
                raise PublicIntakeSecurityRejected("bot challenge is required")
