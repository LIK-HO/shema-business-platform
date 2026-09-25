import pytest

from shema_platform.application.communication import CommunicationGateway
from shema_platform.domain.commercial_action import (
    CommercialAction,
    CommercialActionStatus,
)
from shema_platform.foundation.errors import QuarantineRequired
from shema_platform.adapters.communication.max import MaxMockAdapter
from shema_platform.adapters.communication.safety import (
    ExternalEffectSafety,
    SafeCommunicationAdapter,
)


def ready_action() -> CommercialAction:
    return CommercialAction(
        action_id="action:p41:1",
        identity_id="identity:p41:1",
        contact_ref="contact:p41:1",
        channel="max",
        evidence_refs=("evidence:p41:1",),
        status=CommercialActionStatus.READY,
    )


def safe_max_gateway() -> CommunicationGateway:
    safety = ExternalEffectSafety(
        provider="max",
        supports_idempotency=True,
        supports_reconciliation=False,
        evidence_ref="test:max:deterministic-idempotency:v1",
    )
    return CommunicationGateway(
        SafeCommunicationAdapter(
            MaxMockAdapter(),
            safety,
        )
    )


def test_same_idempotency_key_replay_returns_same_external_identity() -> None:
    gateway = safe_max_gateway()
    action = ready_action()

    first = gateway.send(
        action,
        body="P41 deterministic message",
        idempotency_key="action:p41:1",
    )
    second = gateway.send(
        action,
        body="P41 deterministic message",
        idempotency_key="action:p41:1",
    )

    assert first.accepted is True
    assert second.accepted is True
    assert first.external_message_id == second.external_message_id


def test_idempotency_key_reuse_with_different_payload_fails_closed() -> None:
    gateway = safe_max_gateway()
    action = ready_action()

    gateway.send(
        action,
        body="original body",
        idempotency_key="action:p41:1",
    )

    with pytest.raises(
        ValueError,
        match="idempotency key reused with different request",
    ):
        gateway.send(
            action,
            body="tampered body",
            idempotency_key="action:p41:1",
        )


def test_different_actions_have_distinct_external_identities() -> None:
    gateway = safe_max_gateway()

    first = gateway.send(
        ready_action(),
        body="message 1",
        idempotency_key="action:p41:1",
    )
    second = gateway.send(
        CommercialAction(
            action_id="action:p41:2",
            identity_id="identity:p41:1",
            contact_ref="contact:p41:1",
            channel="max",
            evidence_refs=("evidence:p41:1",),
            status=CommercialActionStatus.READY,
        ),
        body="message 2",
        idempotency_key="action:p41:2",
    )

    assert first.external_message_id != second.external_message_id


def test_unsafe_external_effect_capability_is_blocked() -> None:
    safety = ExternalEffectSafety(
        provider="max",
        supports_idempotency=False,
        supports_reconciliation=False,
        evidence_ref="test:max:unproven",
    )

    with pytest.raises(
        QuarantineRequired,
        match="not certified for crash-safe retry",
    ):
        SafeCommunicationAdapter(MaxMockAdapter(), safety)


def test_replay_does_not_create_a_second_adapter_result() -> None:
    adapter = MaxMockAdapter()
    safety = ExternalEffectSafety(
        provider="max",
        supports_idempotency=True,
        supports_reconciliation=False,
        evidence_ref="test:max:deterministic-idempotency:v1",
    )
    gateway = CommunicationGateway(
        SafeCommunicationAdapter(adapter, safety)
    )
    action = ready_action()

    results = [
        gateway.send(
            action,
            body="same message",
            idempotency_key="action:p41:1",
        )
        for _ in range(5)
    ]

    assert len({result.external_message_id for result in results}) == 1
