import pytest

from shema_platform.adapters.communication.max import MaxAdapter
from shema_platform.application.communication import (
    CommunicationGateway,
    CommunicationSendRequest,
)


def request(body: str = "Здравствуйте") -> CommunicationSendRequest:
    return CommunicationSendRequest(
        action_id="action-1",
        channel="max",
        contact_ref="chat:42",
        body=body,
        idempotency_key="action-1:send",
    )


def test_gateway_sends_via_max_adapter() -> None:
    gateway = CommunicationGateway(MaxAdapter())
    result = gateway.send(request())

    assert result.accepted
    assert result.channel == "max"
    assert result.action_id == "action-1"
    assert result.external_message_id == "max:action-1:send"


def test_max_outbound_send_is_idempotent() -> None:
    adapter = MaxAdapter()
    first = adapter.send(request())
    second = adapter.send(request())

    assert second == first


def test_max_rejects_idempotency_key_reuse_with_changed_request() -> None:
    adapter = MaxAdapter()
    adapter.send(request())

    with pytest.raises(ValueError, match="different request"):
        adapter.send(request("Изменённый текст"))


def test_gateway_rejects_wrong_channel() -> None:
    gateway = CommunicationGateway(MaxAdapter())
    with pytest.raises(ValueError, match="does not match adapter"):
        gateway.send(
            CommunicationSendRequest(
                action_id="action-1",
                channel="telegram",
                contact_ref="chat:42",
                body="Здравствуйте",
                idempotency_key="action-1:send",
            )
        )
