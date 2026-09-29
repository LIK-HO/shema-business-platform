from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.application.counterparty_check import (
    CounterpartyIdentifierType,
    CounterpartyObservation,
    SourceReliability,
)
from shema_platform.application.counterparty_monitoring import (
    ChangeSeverity,
    CounterpartyMonitoringService,
    detect_counterparty_changes,
    snapshot_payload_hash,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.errors import AuthorizationError, IntegrityViolation
from shema_platform.foundation.idempotency import IdempotencyRecord


NOW = datetime(2026, 9, 29, 12, tzinfo=UTC)
PERMISSIONS = frozenset(
    {
        Permission.COUNTERPARTY_MONITOR_MANAGE,
        Permission.COUNTERPARTY_FAVORITE_MANAGE,
    }
)


class Idempotency:
    def __init__(self):
        self.records = {}

    def reserve(self, key, request_hash, result_ref):
        current = self.records.get(key)
        if current is not None:
            return current
        current = IdempotencyRecord(key, request_hash, result_ref)
        self.records[key] = current
        return current

    def complete(self, key, request_hash, result_ref):
        current = self.records[key]
        if current.request_hash != request_hash:
            raise AssertionError("request hash mismatch")
        self.records[key] = IdempotencyRecord(key, request_hash, result_ref)
        return self.records[key]

    def get(self, key):
        return self.records.get(key)


class Audits:
    def __init__(self):
        self.records = []

    def append(self, record):
        self.records.append(record)


class Outbox:
    def __init__(self):
        self.events = {}

    def append(self, event):
        existing = self.events.get(event.event_id)
        if existing is not None and existing != event:
            raise AssertionError("event collision")
        self.events[event.event_id] = event
        return event


class MonitoringRepo:
    def __init__(self):
        self.monitors = {}
        self.favorites = {}
        self.snapshots = {}
        self.changes = []
        self.uow = None

    def add_monitor(self, monitor):
        key = (monitor.actor_id, monitor.identifier_type, monitor.identifier)
        existing = next(
            (
                item
                for item in self.monitors.values()
                if (item.actor_id, item.identifier_type, item.identifier) == key
            ),
            None,
        )
        if existing is not None:
            return
        self.monitors[monitor.monitor_id] = monitor

    def get_monitor(self, monitor_id):
        return self.monitors.get(monitor_id)

    def get_monitor_for_actor(self, monitor_id, actor_id):
        item = self.monitors.get(monitor_id)
        return item if item is not None and item.actor_id == actor_id else None

    def list_monitors(self, actor_id):
        return tuple(item for item in self.monitors.values() if item.actor_id == actor_id)

    def add_favorite(self, favorite):
        key = (favorite.actor_id, favorite.identifier_type, favorite.identifier)
        existing = next(
            (
                item
                for item in self.favorites.values()
                if (item.actor_id, item.identifier_type, item.identifier) == key
            ),
            None,
        )
        if existing is None:
            self.favorites[favorite.favorite_id] = favorite

    def get_favorite(self, favorite_id):
        return self.favorites.get(favorite_id)

    def list_favorites(self, actor_id):
        return tuple(item for item in self.favorites.values() if item.actor_id == actor_id)

    def get_latest_snapshot(self, monitor_id):
        items = [item for item in self.snapshots.values() if item.monitor_id == monitor_id]
        return max(items, key=lambda item: (item.observed_at, item.snapshot_id), default=None)

    def add_snapshot(self, snapshot):
        existing = next(
            (
                item
                for item in self.snapshots.values()
                if (
                    item.monitor_id,
                    item.observed_at,
                    item.payload_hash,
                )
                == (
                    snapshot.monitor_id,
                    snapshot.observed_at,
                    snapshot.payload_hash,
                )
            ),
            None,
        )
        if existing is not None:
            return existing
        self.snapshots[snapshot.snapshot_id] = snapshot
        return snapshot

    def set_last_snapshot(self, monitor_id, *, snapshot_id, checked_at, next_check_at):
        item = self.monitors[monitor_id]
        from dataclasses import replace

        self.monitors[monitor_id] = replace(
            item,
            last_snapshot_id=snapshot_id,
            last_checked_at=checked_at,
            next_check_at=next_check_at,
            updated_at=checked_at,
        )

    def add_change_event(self, event):
        self.changes.append(event)


class UOW:
    def __init__(self, repo):
        self.monitoring = repo
        self.idempotency = Idempotency()
        self.audits = Audits()
        self.outbox = Outbox()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


def make_service(repo):
    return CounterpartyMonitoringService(lambda: UOW(repo))


def observation(
    *,
    name='ООО "Пример"',
    status='ACTIVE',
    observed_at=NOW,
    expires_at=None,
):
    return CounterpartyObservation(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        canonical_name=name,
        tax_id="7707083893",
        registration_id="1027700132195",
        legal_status=status,
        source_ref="https://pb.nalog.ru/",
        source_reliability=SourceReliability.AUTHORITATIVE,
        claim_confidence=1.0,
        observed_at=observed_at,
        expires_at=expires_at or (observed_at + timedelta(days=1)),
    )


def test_invalid_identifier_is_rejected_before_persistence():
    service = make_service(MonitoringRepo())

    with pytest.raises(ValueError, match="invalid INN checksum"):
        service.save_monitoring(
            identifier_type=CounterpartyIdentifierType.INN,
            identifier="7707083894",
            actor_id="operator-1",
            permissions=PERMISSIONS,
            idempotency_key="monitor-invalid-1",
            correlation_id="corr-invalid",
            now=NOW,
        )


def test_monitor_is_idempotent_and_actor_scoped():
    repo = MonitoringRepo()
    service = make_service(repo)

    first = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-1",
        correlation_id="corr-1",
        now=NOW,
    )
    second = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-2",
        correlation_id="corr-2",
        now=NOW,
    )
    third = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-2",
        permissions=PERMISSIONS,
        idempotency_key="monitor-3",
        correlation_id="corr-3",
        now=NOW,
    )

    assert second.monitor_id == first.monitor_id
    assert third.monitor_id != first.monitor_id
    assert len(service.list_monitors("operator-1", PERMISSIONS)) == 1
    assert len(service.list_monitors("operator-2", PERMISSIONS)) == 1

    with pytest.raises(AuthorizationError):
        service.list_monitors(
            "operator-1",
            frozenset({Permission.COUNTERPARTY_FAVORITE_MANAGE}),
        )


def test_snapshot_hash_is_integrity_bound_and_change_detection_is_deterministic():
    repo = MonitoringRepo()
    service = make_service(repo)
    monitor = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-snapshot",
        correlation_id="corr-snapshot",
        now=NOW,
    )

    first = service.record_observation(
        monitor_id=monitor.monitor_id,
        actor_id="operator-1",
        permissions=PERMISSIONS,
        observation=observation(),
        correlation_id="corr-observe-1",
        now=NOW,
    )
    changed = service.record_observation(
        monitor_id=monitor.monitor_id,
        actor_id="operator-1",
        permissions=PERMISSIONS,
        observation=observation(
            name='ООО "Новое"',
            observed_at=NOW + timedelta(days=1),
            expires_at=NOW + timedelta(days=2),
        ),
        correlation_id="corr-observe-2",
        now=NOW + timedelta(days=1),
    )

    changed_parameters, severity = detect_counterparty_changes(first, changed)
    assert changed_parameters == {
        "canonical_name": {"before": 'ООО "Пример"', "after": 'ООО "Новое"'}
    }
    assert severity is ChangeSeverity.ATTENTION
    assert len(repo.changes) == 1

    assert snapshot_payload_hash(first.payload) == first.payload_hash
    with pytest.raises(IntegrityViolation):
        type(first)(
            snapshot_id=first.snapshot_id,
            monitor_id=first.monitor_id,
            observed_at=first.observed_at,
            source_ref=first.source_ref,
            source_version=first.source_version,
            payload={**first.payload, "canonical_name": "tampered"},
            payload_hash=first.payload_hash,
        )


def test_favorite_is_personal_and_idempotent():
    repo = MonitoringRepo()
    service = make_service(repo)

    first = service.save_favorite(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="favorite-1",
        correlation_id="corr-fav-1",
        now=NOW,
    )
    second = service.save_favorite(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="favorite-2",
        correlation_id="corr-fav-2",
        now=NOW,
    )
    other = service.save_favorite(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-2",
        permissions=PERMISSIONS,
        idempotency_key="favorite-3",
        correlation_id="corr-fav-3",
        now=NOW,
    )

    assert first.favorite_id == second.favorite_id
    assert other.favorite_id != first.favorite_id
    assert len(service.list_favorites("operator-1", PERMISSIONS)) == 1
    assert len(service.list_favorites("operator-2", PERMISSIONS)) == 1


def test_critical_status_change_gets_critical_severity():
    repo = MonitoringRepo()
    service = make_service(repo)
    monitor = service.save_monitoring(
        identifier_type=CounterpartyIdentifierType.INN,
        identifier="7707083893",
        actor_id="operator-1",
        permissions=PERMISSIONS,
        idempotency_key="monitor-critical",
        correlation_id="corr-critical",
        now=NOW,
    )

    first = service.record_observation(
        monitor_id=monitor.monitor_id,
        actor_id="operator-1",
        permissions=PERMISSIONS,
        observation=observation(),
        correlation_id="corr-critical-1",
        now=NOW,
    )
    second = service.record_observation(
        monitor_id=monitor.monitor_id,
        actor_id="operator-1",
        permissions=PERMISSIONS,
        observation=observation(
            status="LIQUIDATED",
            observed_at=NOW + timedelta(days=1),
            expires_at=NOW + timedelta(days=2),
        ),
        correlation_id="corr-critical-2",
        now=NOW + timedelta(days=1),
    )
    _, severity = detect_counterparty_changes(first, second)
    assert severity is ChangeSeverity.CRITICAL
