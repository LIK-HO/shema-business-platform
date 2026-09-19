from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.foundation.errors import QuarantineRequired


@dataclass(frozen=True, slots=True)
class CommunicationSendRequest:
    action_id: str
    channel: str
    contact_ref: str
    body: str
    idempotency_key: str


@dataclass(frozen=True, slots=True)
class CommunicationSendResult:
    action_id: str
    channel: str
    external_message_id: str
    accepted: bool


class CommunicationAdapter(Protocol):
    channel: str

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult: ...


class CommunicationGateway:
    """External-effect boundary. Only a READY commercial action may reach an adapter."""

    def __init__(self, adapter: CommunicationAdapter) -> None:
        self._adapter = adapter

    def send(
        self,
        action: CommercialAction,
        *,
        body: str,
        idempotency_key: str,
    ) -> CommunicationSendResult:
        if not action.action_id.strip():
            raise ValueError("action_id is required")
        if not body.strip():
            raise ValueError("body is required")
        if not idempotency_key.strip():
            raise ValueError("idempotency_key is required")

        action.validate_for_external_send()

        if action.channel != self._adapter.channel:
            raise ValueError("request channel does not match adapter")

        request = CommunicationSendRequest(
            action_id=action.action_id,
            channel=action.channel,
            contact_ref=action.contact_ref,
            body=body,
            idempotency_key=idempotency_key,
        )
        result = self._adapter.send(request)

        if result.action_id != action.action_id:
            raise ValueError("adapter returned mismatched action_id")
        if result.channel != action.channel:
            raise ValueError("adapter returned mismatched channel")
        if not result.accepted:
            raise QuarantineRequired("external communication was not accepted")

        return result
