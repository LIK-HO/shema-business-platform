import pytest

from shema_platform.adapters.communication.max import MaxAdapter
from shema_platform.application.communication import CommunicationGateway
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.foundation.errors import QuarantineRequired


def ready_action(channel: str = "max") -> CommercialAction:
    return CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="chat:42",
        channel=channel,
        evidence_refs=("evidence:1",),
    ).mark_ready()


def test_gateway_sends_only_ready_commercial_action() -> None:
    gateway = CommunicationGateway(MaxAdapter())
    result = gateway.send(
        ready_action(),
        body="Здравствуйте",
        idempotency_key="action-1:send",
    )

    assert result.accepted
    assert result.channel == "max"
    assert result.action_id == "action-1"
    assert result.external_message_id == "max:action-1:send"


def test_gateway_rejects_draft_action_before_adapter_call() -> None:
    gateway = CommunicationGateway(MaxAdapter())
    action = CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="chat:42",
        channel="max",
        evidence_refs=("evidence:1",),
    )

    assert action.status is CommercialActionStatus.DRAFT
    with pytest.raises(
        QuarantineRequired,
        match="must be ready before external send",
    ):
        gateway.send(
            action,
            body="Здравствуйте",
            idempotency_key="action-1:send",
        )


def test_max_outbound_send_is_idempotent() -> None:
    adapter = MaxAdapter()
    action = ready_action()
    first = adapter.send(
        __import__(
            "shema_platform.application.communication",
            fromlist=["CommunicationSendRequest"],
        ).CommunicationSendRequest(
            action_id=action.action_id,
            channel=action.channel,
            contact_ref=action.contact_ref,
            body="Здравствуйте",
            idempotency_key="action-1:send",
        )
    )
    second = adapter.send(
        __import__(
            "shema_platform.application.communication",
            fromlist=["CommunicationSendRequest"],
        ).CommunicationSendRequest(
            action_id=action.action_id,
            channel=action.channel,
            contact_ref=action.contact_ref,
            body="Здравствуйте",
            idempotency_key="action-1:send",
        )
    )

    assert second == first


def test_max_rejects_idempotency_key_reuse_with_changed_request() -> None:
    from shema_platform.application.communication import CommunicationSendRequest

    adapter = MaxAdapter()
    request = CommunicationSendRequest(
        action_id="action-1",
        channel="max",
        contact_ref="chat:42",
        body="Здравствуйте",
        idempotency_key="action-1:send",
    )
    adapter.send(request)

    with pytest.raises(ValueError, match="different request"):
        adapter.send(
            CommunicationSendRequest(
                action_id="action-1",
                channel="max",
                contact_ref="chat:42",
                body="Изменённый текст",
                idempotency_key="action-1:send",
            )
        )


def test_gateway_rejects_wrong_channel_before_adapter_call() -> None:
    gateway = CommunicationGateway(MaxAdapter())

    with pytest.raises(ValueError, match="does not match adapter"):
        gateway.send(
            ready_action(channel="telegram"),
            body="Здравствуйте",
            idempotency_key="action-1:send",
        )
