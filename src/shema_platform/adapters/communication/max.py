from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from shema_platform.application.communication import (
    CommunicationSendRequest,
    CommunicationSendResult,
)


class MaxEventKind(StrEnum):
    MESSAGE = "message"
    CALLBACK = "callback"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MaxWebhookEvent:
    event_id: str
    api_version: str
    kind: MaxEventKind
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class CanonicalCommunicationEvent:
    event_id: str
    channel: str
    kind: str
    external_version: str
    payload: dict[str, Any]


@dataclass(frozen=True, slots=True)
class MaxSendReceipt:
    idempotency_key: str
    request_fingerprint: str
    external_message_id: str


class MaxAdapter:
    """Boundary for MAX inbound normalization and outbound communication."""

    channel = "max"

    def __init__(self) -> None:
        self._sent: dict[str, MaxSendReceipt] = {}

    def normalize(self, event: MaxWebhookEvent) -> CanonicalCommunicationEvent:
        if not event.event_id:
            raise ValueError("MAX event_id is required")
        if not event.api_version:
            raise ValueError("MAX api_version is required")
        return CanonicalCommunicationEvent(
            event_id=event.event_id,
            channel=self.channel,
            kind=event.kind.value,
            external_version=event.api_version,
            payload=dict(event.payload),
        )

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        if request.channel != self.channel:
            raise ValueError("request channel does not match MAX")

        fingerprint = "|".join(
            (
                request.action_id,
                request.channel,
                request.contact_ref,
                request.body,
            )
        )
        existing = self._sent.get(request.idempotency_key)

        if existing is not None:
            if existing.request_fingerprint != fingerprint:
                raise ValueError("MAX idempotency key reused with different request")
            return CommunicationSendResult(
                action_id=request.action_id,
                channel=self.channel,
                external_message_id=existing.external_message_id,
                accepted=True,
            )

        external_message_id = f"max:{request.idempotency_key}"
        self._sent[request.idempotency_key] = MaxSendReceipt(
            idempotency_key=request.idempotency_key,
            request_fingerprint=fingerprint,
            external_message_id=external_message_id,
        )
        return CommunicationSendResult(
            action_id=request.action_id,
            channel=self.channel,
            external_message_id=external_message_id,
            accepted=True,
        )
