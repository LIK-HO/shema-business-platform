from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


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
    """External-effect boundary. Network work never belongs in the core transaction."""

    def __init__(self, adapter: CommunicationAdapter) -> None:
        self._adapter = adapter

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        if request.channel != self._adapter.channel:
            raise ValueError("request channel does not match adapter")
        if not request.action_id.strip():
            raise ValueError("action_id is required")
        if not request.contact_ref.strip():
            raise ValueError("contact_ref is required")
        if not request.body.strip():
            raise ValueError("body is required")
        if not request.idempotency_key.strip():
            raise ValueError("idempotency_key is required")

        result = self._adapter.send(request)
        if result.action_id != request.action_id:
            raise ValueError("adapter returned mismatched action_id")
        if result.channel != request.channel:
            raise ValueError("adapter returned mismatched channel")
        return result
