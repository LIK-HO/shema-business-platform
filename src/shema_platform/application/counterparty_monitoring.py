from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Protocol
from uuid import uuid4

from shema_platform.application.counterparty_check import (
    CounterpartyIdentifierType,
    CounterpartyObservation,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import IdempotencyConflict, IntegrityViolation
from shema_platform.foundation.outbox import OutboxEvent


class MonitoringStatus(StrEnum):
    ACTIVE = "active"
    PAUSED = "paused"


class ChangeSeverity(StrEnum):
    INFO = "INFO"
    ATTENTION = "ATTENTION"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass(frozen=True, slots=True)
class CounterpartyMonitor:
    monitor_id: str
    actor_id: str
    identifier_type: CounterpartyIdentifierType
    identifier: str
    status: MonitoringStatus
    frequency_seconds: int
    next_check_at: datetime
    last_checked_at: datetime | None = None
    last_snapshot_id: str | None = None
    last_error_code: str | None = None
    last_error_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None

    def __post_init__(self) -> None:
        if not self.monitor_id.strip() or not self.actor_id.strip():
            raise ValueError("monitor_id and actor_id are required")
        if not self.identifier.isdigit():
            raise ValueError("counterparty identifier must contain digits only")
        if self.frequency_seconds <= 0:
            raise ValueError("frequency_seconds must be positive")
        if self.next_check_at.tzinfo is None:
            raise ValueError("next_check_at must be timezone-aware")


@dataclass(frozen=True, slots=True)
class CounterpartyFavorite:
    favorite_id: str
    actor_id: str
    identifier_type: CounterpartyIdentifierType
    identifier: str
    created_at: datetime

    def __post_init__(self) -> None:
        if not self.favorite_id.strip() or not self.actor_id.strip():
            raise ValueError("favorite_id and actor_id are required")
        if not self.identifier.isdigit():
            raise ValueError("counterparty identifier must contain digits only")


@dataclass(frozen=True, slots=True)
class CounterpartySnapshot:
    snapshot_id: str
    monitor_id: str
    observed_at: datetime
    source_ref: str
    source_version: str
    payload: dict[str, str]
    payload_hash: str

    def __post_init__(self) -> None:
        if not self.snapshot_id.strip() or not self.monitor_id.strip():
            raise ValueError("snapshot identifiers are required")
        if self.observed_at.tzinfo is None:
            raise ValueError("observed_at must be timezone-aware")
        if not self.source_ref.strip() or not self.source_version.strip():
            raise ValueError("snapshot provenance is required")
        expected = snapshot_payload_hash(self.payload)
        if expected != self.payload_hash:
            raise IntegrityViolation("counterparty snapshot payload hash mismatch")


@dataclass(frozen=True, slots=True)
class CounterpartyChangeEvent:
    change_id: str
    monitor_id: str
    before_snapshot_id: str
    after_snapshot_id: str
    changed_parameters: dict[str, dict[str, str]]
    severity: ChangeSeverity
    source_ref: str
    freshness: str
    correlation_id: str
    notification_id: str
    detected_at: datetime


class CounterpartyMonitoringRepository(Protocol):
    def add_monitor(self, monitor: CounterpartyMonitor) -> None: ...
    def get_monitor(self, monitor_id: str) -> CounterpartyMonitor | None: ...
    def get_monitor_for_actor(
        self,
        monitor_id: str,
        actor_id: str,
    ) -> CounterpartyMonitor | None: ...
    def list_monitors(self, actor_id: str) -> tuple[CounterpartyMonitor, ...]: ...
    def add_favorite(self, favorite: CounterpartyFavorite) -> None: ...
    def get_favorite(self, favorite_id: str) -> CounterpartyFavorite | None: ...
    def list_favorites(self, actor_id: str) -> tuple[CounterpartyFavorite, ...]: ...
    def get_latest_snapshot(self, monitor_id: str) -> CounterpartySnapshot | None: ...
    def add_snapshot(self, snapshot: CounterpartySnapshot) -> CounterpartySnapshot: ...
    def set_last_snapshot(
        self,
        monitor_id: str,
        *,
        snapshot_id: str,
        checked_at: datetime,
        next_check_at: datetime,
    ) -> None: ...
    def add_change_event(self, event: CounterpartyChangeEvent) -> None: ...


def validate_counterparty_identifier(
    identifier_type: CounterpartyIdentifierType,
    identifier: str,
) -> str:
    normalized = "".join(ch for ch in identifier if ch.isdigit())
    if normalized != identifier.strip():
        raise ValueError("counterparty identifier must contain digits only")

    if identifier_type is CounterpartyIdentifierType.INN:
        if len(normalized) == 10:
            weights = (2, 4, 10, 3, 5, 9, 4, 6, 8)
            checksum = (
                sum(
                    int(d) * w
                    for d, w in zip(normalized[:-1], weights, strict=True)
                )
                % 11
                % 10
            )
            if checksum != int(normalized[-1]):
                raise ValueError("invalid INN checksum")
        elif len(normalized) == 12:
            weights_1 = (7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0)
            weights_2 = (3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8, 0)
            c1 = sum(int(d) * w for d, w in zip(normalized[:-2], weights_1, strict=True)) % 11 % 10
            c2 = sum(int(d) * w for d, w in zip(normalized[:-1], weights_2, strict=True)) % 11 % 10
            if (c1, c2) != (int(normalized[-2]), int(normalized[-1])):
                raise ValueError("invalid INN checksum")
        else:
            raise ValueError("invalid INN length")
    elif identifier_type is CounterpartyIdentifierType.OGRN:
        if len(normalized) != 13 or (int(normalized[:-1]) % 11) % 10 != int(normalized[-1]):
            raise ValueError("invalid OGRN")
    elif identifier_type is CounterpartyIdentifierType.OGRNIP:
        if len(normalized) != 15 or (int(normalized[:-1]) % 13) % 10 != int(normalized[-1]):
            raise ValueError("invalid OGRNIP")

    return normalized


def snapshot_payload_hash(payload: dict[str, str]) -> str:
    encoded = json.dumps(
        dict(sorted(payload.items())),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def snapshot_from_observation(
    monitor: CounterpartyMonitor,
    observation: CounterpartyObservation,
    *,
    now: datetime,
    source_version: str = "authoritative-counterparty:v1",
) -> CounterpartySnapshot:
    if observation.identifier_type is not monitor.identifier_type:
        raise IntegrityViolation("monitor identifier type does not match observation")
    if observation.identifier.strip() != monitor.identifier:
        raise IntegrityViolation("monitor identifier does not match observation")
    payload = {
        "canonical_name": observation.canonical_name,
        "tax_id": observation.tax_id or "",
        "registration_id": observation.registration_id or "",
        "legal_status": observation.legal_status or "",
    }
    payload_hash = snapshot_payload_hash(payload)
    snapshot_id = hashlib.sha256(
        f"{monitor.monitor_id}|{observation.observed_at.isoformat()}|{payload_hash}".encode()
    ).hexdigest()
    return CounterpartySnapshot(
        snapshot_id=f"cps:{snapshot_id}",
        monitor_id=monitor.monitor_id,
        observed_at=observation.observed_at,
        source_ref=observation.source_ref,
        source_version=source_version,
        payload=payload,
        payload_hash=payload_hash,
    )


def detect_counterparty_changes(
    before: CounterpartySnapshot,
    after: CounterpartySnapshot,
) -> tuple[dict[str, dict[str, str]], ChangeSeverity]:
    if before.monitor_id != after.monitor_id:
        raise IntegrityViolation("snapshot monitor mismatch")
    changed: dict[str, dict[str, str]] = {}
    for field in sorted(set(before.payload) & set(after.payload)):
        if before.payload[field] != after.payload[field]:
            changed[field] = {
                "before": before.payload[field],
                "after": after.payload[field],
            }
    if not changed:
        return {}, ChangeSeverity.INFO

    if "legal_status" in changed and changed["legal_status"]["after"].lower() in {
        "liquidated",
        "terminated",
        "not_registered",
    }:
        severity = ChangeSeverity.CRITICAL
    elif any(field in changed for field in ("tax_id", "registration_id")):
        severity = ChangeSeverity.HIGH
    elif any(field in changed for field in ("legal_status", "canonical_name")):
        severity = ChangeSeverity.ATTENTION
    else:
        severity = ChangeSeverity.INFO
    return changed, severity


class CounterpartyMonitoringService:
    """Durable monitoring/favorites control over the canonical counterparty boundary."""

    def __init__(self, unit_of_work_factory) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    @staticmethod
    def _authorize(
        actor_id: str,
        permissions: frozenset[Permission],
        permission: Permission,
    ) -> None:
        RBACAuthorizer(
            (AuthorizationSubject(actor_id=actor_id, permissions=permissions),)
        ).require(actor_id, permission)

    @staticmethod
    def _idempotency_hash(*parts: str) -> str:
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()

    def save_monitoring(
        self,
        *,
        identifier_type: CounterpartyIdentifierType,
        identifier: str,
        actor_id: str,
        permissions: frozenset[Permission],
        idempotency_key: str,
        correlation_id: str,
        now: datetime,
    ) -> CounterpartyMonitor:
        self._authorize(actor_id, permissions, Permission.COUNTERPARTY_MONITOR_MANAGE)
        normalized = validate_counterparty_identifier(identifier_type, identifier)
        request_hash = self._idempotency_hash(
            "counterparty.monitor", actor_id, identifier_type.value, normalized
        )
        monitor_id = str(uuid4())
        pending_ref = f"pending:{monitor_id}"
        idem_key = f"counterparty.monitor:{actor_id}:{idempotency_key}"
        with self._unit_of_work_factory() as uow:
            reservation = uow.idempotency.reserve(idem_key, request_hash, pending_ref)
            if reservation.result_ref != pending_ref:
                if reservation.result_ref.startswith("pending:"):
                    raise IdempotencyConflict(
                        "counterparty monitoring request is already in progress"
                    )
                stored = uow.monitoring.get_monitor(reservation.result_ref)
                if stored is None:
                    raise IntegrityViolation(
                        "completed monitoring reservation references missing monitor"
                    )
                return stored
            for item in uow.monitoring.list_monitors(actor_id):
                if item.identifier_type is identifier_type and item.identifier == normalized:
                    uow.idempotency.complete(idem_key, request_hash, item.monitor_id)
                    return item

            current = now.astimezone(UTC)
            monitor = CounterpartyMonitor(
                monitor_id=monitor_id,
                actor_id=actor_id,
                identifier_type=identifier_type,
                identifier=normalized,
                status=MonitoringStatus.ACTIVE,
                frequency_seconds=86400,
                next_check_at=current,
                created_at=current,
                updated_at=current,
            )
            uow.monitoring.add_monitor(monitor)
            uow.idempotency.complete(idem_key, request_hash, monitor.monitor_id)
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid4()),
                    actor_id=actor_id,
                    action="counterparty.monitor.created",
                    resource_type="counterparty_monitor",
                    resource_id=monitor.monitor_id,
                    outcome="success",
                    occurred_at=current,
                    metadata={
                        "identifier_type": identifier_type.value,
                        "identifier": normalized,
                        "frequency_seconds": 86400,
                    },
                    correlation_id=correlation_id,
                )
            )
            uow.outbox.append(
                OutboxEvent(
                    event_id=f"counterparty-monitor:{monitor.monitor_id}",
                    event_type="counterparty.monitor.created",
                    aggregate_type="counterparty_monitor",
                    aggregate_id=monitor.monitor_id,
                    payload={
                        "monitor_id": monitor.monitor_id,
                        "actor_id": actor_id,
                        "identifier_type": identifier_type.value,
                        "identifier": normalized,
                    },
                    occurred_at=current,
                )
            )
            return monitor

    def save_favorite(
        self,
        *,
        identifier_type: CounterpartyIdentifierType,
        identifier: str,
        actor_id: str,
        permissions: frozenset[Permission],
        idempotency_key: str,
        correlation_id: str,
        now: datetime,
    ) -> CounterpartyFavorite:
        self._authorize(actor_id, permissions, Permission.COUNTERPARTY_FAVORITE_MANAGE)
        normalized = identifier.strip()
        request_hash = self._idempotency_hash(
            "counterparty.favorite", actor_id, identifier_type.value, normalized
        )
        favorite_id = str(uuid4())
        pending_ref = f"pending:{favorite_id}"
        idem_key = f"counterparty.favorite:{actor_id}:{idempotency_key}"
        with self._unit_of_work_factory() as uow:
            reservation = uow.idempotency.reserve(idem_key, request_hash, pending_ref)
            if reservation.result_ref != pending_ref:
                if reservation.result_ref.startswith("pending:"):
                    raise IdempotencyConflict(
                        "counterparty favorite request is already in progress"
                    )
                stored = uow.monitoring.get_favorite(reservation.result_ref)
                if stored is None:
                    raise IntegrityViolation(
                        "completed favorite reservation references missing favorite"
                    )
                return stored
            for item in uow.monitoring.list_favorites(actor_id):
                if item.identifier_type is identifier_type and item.identifier == normalized:
                    uow.idempotency.complete(idem_key, request_hash, item.favorite_id)
                    return item

            current = now.astimezone(UTC)
            favorite = CounterpartyFavorite(
                favorite_id=favorite_id,
                actor_id=actor_id,
                identifier_type=identifier_type,
                identifier=normalized,
                created_at=current,
            )
            uow.monitoring.add_favorite(favorite)
            uow.idempotency.complete(idem_key, request_hash, favorite.favorite_id)
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid4()),
                    actor_id=actor_id,
                    action="counterparty.favorite.created",
                    resource_type="counterparty_favorite",
                    resource_id=favorite.favorite_id,
                    outcome="success",
                    occurred_at=current,
                    metadata={
                        "identifier_type": identifier_type.value,
                        "identifier": normalized,
                    },
                    correlation_id=correlation_id,
                )
            )
            uow.outbox.append(
                OutboxEvent(
                    event_id=f"counterparty-favorite:{favorite.favorite_id}",
                    event_type="counterparty.favorite.created",
                    aggregate_type="counterparty_favorite",
                    aggregate_id=favorite.favorite_id,
                    payload={
                        "favorite_id": favorite.favorite_id,
                        "actor_id": actor_id,
                        "identifier_type": identifier_type.value,
                        "identifier": normalized,
                    },
                    occurred_at=current,
                )
            )
            return favorite

    def list_monitors(
        self,
        actor_id: str,
        permissions: frozenset[Permission],
    ) -> tuple[CounterpartyMonitor, ...]:
        self._authorize(actor_id, permissions, Permission.COUNTERPARTY_MONITOR_MANAGE)
        with self._unit_of_work_factory() as uow:
            return uow.monitoring.list_monitors(actor_id)

    def list_favorites(
        self,
        actor_id: str,
        permissions: frozenset[Permission],
    ) -> tuple[CounterpartyFavorite, ...]:
        self._authorize(actor_id, permissions, Permission.COUNTERPARTY_FAVORITE_MANAGE)
        with self._unit_of_work_factory() as uow:
            return uow.monitoring.list_favorites(actor_id)

    def record_observation(
        self,
        *,
        monitor_id: str,
        actor_id: str,
        permissions: frozenset[Permission],
        observation: CounterpartyObservation,
        correlation_id: str,
        now: datetime,
    ) -> CounterpartySnapshot:
        self._authorize(actor_id, permissions, Permission.COUNTERPARTY_MONITOR_MANAGE)
        with self._unit_of_work_factory() as uow:
            monitor = uow.monitoring.get_monitor_for_actor(monitor_id, actor_id)
            if monitor is None:
                raise IntegrityViolation("monitor is missing or outside actor scope")
            snapshot = snapshot_from_observation(monitor, observation, now=now)
            previous = uow.monitoring.get_latest_snapshot(monitor_id)
            stored = uow.monitoring.add_snapshot(snapshot)
            current = now.astimezone(UTC)
            uow.monitoring.set_last_snapshot(
                monitor_id,
                snapshot_id=stored.snapshot_id,
                checked_at=current,
                next_check_at=current + timedelta(seconds=monitor.frequency_seconds),
            )
            if previous is not None:
                changed, severity = detect_counterparty_changes(previous, stored)
                if changed:
                    change_id = str(uuid4())
                    notification_id = (
                        f"counterparty-change:{monitor_id}:"
                        f"{previous.snapshot_id}:{stored.snapshot_id}"
                    )
                    event = CounterpartyChangeEvent(
                        change_id=change_id,
                        monitor_id=monitor_id,
                        before_snapshot_id=previous.snapshot_id,
                        after_snapshot_id=stored.snapshot_id,
                        changed_parameters=changed,
                        severity=severity,
                        source_ref=stored.source_ref,
                        freshness=(
                            "FRESH"
                            if current <= observation.expires_at
                            else "EXPIRED"
                        ),
                        correlation_id=correlation_id,
                        notification_id=notification_id,
                        detected_at=current,
                    )
                    uow.monitoring.add_change_event(event)
                    uow.outbox.append(
                        OutboxEvent(
                            event_id=notification_id,
                            event_type="counterparty.change.detected",
                            aggregate_type="counterparty_monitor",
                            aggregate_id=monitor_id,
                            payload={
                                "monitor_id": monitor_id,
                                "change_id": change_id,
                                "before_snapshot_id": previous.snapshot_id,
                                "after_snapshot_id": stored.snapshot_id,
                                "changed_parameters": changed,
                                "severity": severity.value,
                                "source_ref": stored.source_ref,
                                "freshness": event.freshness,
                                "notification_id": notification_id,
                            },
                            occurred_at=current,
                        )
                    )
                    uow.audits.append(
                        AuditRecord(
                            audit_id=str(uuid4()),
                            actor_id=actor_id,
                            action="counterparty.monitor.changed",
                            resource_type="counterparty_monitor",
                            resource_id=monitor_id,
                            outcome="change_detected",
                            occurred_at=current,
                            metadata={
                                "changed_parameters": changed,
                                "severity": severity.value,
                                "before_snapshot_id": previous.snapshot_id,
                                "after_snapshot_id": stored.snapshot_id,
                            },
                            correlation_id=correlation_id,
                        )
                    )
            return stored
