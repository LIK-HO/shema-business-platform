from datetime import datetime, timezone

import pytest

from shema_platform.application.commands import Actor, CommercialActionCommand, CommandService
from shema_platform.domain.identity import Identity, IdentityState, Resolution
from shema_platform.foundation.errors import IdempotencyConflict, IntegrityViolation, QuarantineRequired
from shema_platform.foundation.evidence import Evidence, TruthClass, TrustLevel
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.outbox import OutboxEvent, OutboxStatus, OutboxStore
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.recovery import RetryPolicy


def verified_identity() -> Identity:
    return Identity("1", "ООО Альфа", IdentityState.VERIFIED, tax_id="7700000000")


def test_verified_identity_can_resolve_merge() -> None:
    left = verified_identity()
    right = Identity("2", "ООО Альфа", IdentityState.CANDIDATE, tax_id="7700000000")
    assert left.resolve_with(right) is Resolution.MERGE


def test_missing_identity_key_data_requires_quarantine() -> None:
    left = verified_identity()
    right = Identity("2", "Альфа", IdentityState.CANDIDATE)
    assert left.resolve_with(right) is Resolution.QUARANTINE


def test_unverified_identity_cannot_execute_critical_action() -> None:
    service = CommandService(PolicyEngine(), IdempotencyStore())
    command = CommercialActionCommand(
        command_id="cmd-1",
        actor=Actor("operator-1", trust_level=2),
        identity=Identity("1", "ООО Альфа", IdentityState.CANDIDATE, tax_id="7700000000"),
        evidence_level=2,
        request_hash="hash-1",
    )
    with pytest.raises(QuarantineRequired):
        service.execute(command)


def test_verified_identity_can_execute_critical_action() -> None:
    service = CommandService(PolicyEngine(), IdempotencyStore())
    command = CommercialActionCommand(
        command_id="cmd-1",
        actor=Actor("operator-1", trust_level=2),
        identity=verified_identity(),
        evidence_level=2,
        request_hash="hash-1",
    )
    assert service.execute(command) == "1"


def test_idempotency_rejects_changed_request() -> None:
    store = IdempotencyStore()
    store.reserve("k1", "h1", "result-1")
    with pytest.raises(IdempotencyConflict):
        store.reserve("k1", "h2", "result-2")


def test_evidence_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        Evidence(
            evidence_id="e1",
            subject_ref="identity:1",
            claim="Claim",
            source_ref="source:1",
            observed_at=datetime.now(timezone.utc),
            captured_at=datetime.now(timezone.utc),
            truth_class=TruthClass.FACT,
            trust_level=TrustLevel.T2_VERIFIED,
            confidence=1.5,
        )


def test_outbox_is_idempotent_and_pending_until_published() -> None:
    store = OutboxStore()
    event = OutboxEvent(
        event_id="evt-1",
        event_type="identity.verified",
        aggregate_type="identity",
        aggregate_id="1",
        payload={"state": "verified"},
        occurred_at=datetime.now(timezone.utc),
    )
    assert store.append(event) == event
    assert store.append(event) == event
    assert len(store.pending()) == 1
    assert store.mark_published("evt-1").status is OutboxStatus.PUBLISHED
    assert store.pending() == ()


def test_outbox_rejects_event_id_collision() -> None:
    store = OutboxStore()
    now = datetime.now(timezone.utc)
    store.append(
        OutboxEvent("evt-1", "identity.verified", "identity", "1", {"state": "verified"}, now)
    )
    with pytest.raises(IntegrityViolation):
        store.append(
            OutboxEvent("evt-1", "identity.changed", "identity", "1", {"state": "active"}, now)
        )


def test_retry_policy_is_bounded() -> None:
    policy = RetryPolicy(max_attempts=5, initial_delay_seconds=1, max_delay_seconds=4)
    assert policy.delay_for(1) == 1
    assert policy.delay_for(5) == 4
    assert policy.is_retryable(4)
    assert not policy.is_retryable(5)
