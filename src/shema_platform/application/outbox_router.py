from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shema_platform.foundation.errors import PermanentJobError
from shema_platform.foundation.outbox import OutboxEvent


class OutboxEventHandler(Protocol):
    def handle(self, event: OutboxEvent) -> object: ...


@dataclass(frozen=True, slots=True)
class OutboxHandlerRouter:
    """Routes immutable outbox events to explicit application side-effect handlers."""

    handlers: dict[str, OutboxEventHandler]

    def __post_init__(self) -> None:
        normalized = dict(self.handlers)
        if any(not event_type.strip() for event_type in normalized):
            raise ValueError("outbox handler event type cannot be blank")
        object.__setattr__(self, "handlers", normalized)

    def publish(self, event: OutboxEvent) -> object:
        handler = self.handlers.get(event.event_type)
        if handler is None:
            raise PermanentJobError(
                f"no outbox handler registered for event type: {event.event_type}"
            )
        return handler.handle(event)
