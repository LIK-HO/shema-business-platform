from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from .errors import IntegrityViolation


@dataclass(frozen=True, slots=True)
class ProviderActivationState:
    provider_id: str
    enabled: bool
    configuration_version: str | None = None
    activation_version: str | None = None
    activated_by: str | None = None
    activated_at: datetime | None = None
    max_cost: float | None = None
    max_duration_seconds: float | None = None
    rollback_by: str | None = None
    rollback_at: datetime | None = None
    rollback_reason: str | None = None
    rollback_from_configuration_version: str | None = None


class ProviderActivationStateStore(Protocol):
    def get(self, provider_id: str) -> ProviderActivationState | None: ...

    def activate(self, state: ProviderActivationState) -> None: ...

    def rollback(
        self,
        *,
        provider_id: str,
        rolled_back_by: str,
        rolled_back_at: datetime,
        reason: str,
        expected_activation_version: str,
        expected_activated_at: datetime,
    ) -> None: ...


class InMemoryProviderActivationStateStore:
    """Deterministic test-only store implementing the shared-state contract."""

    def __init__(self) -> None:
        self._items: dict[str, ProviderActivationState] = {}

    def get(self, provider_id: str) -> ProviderActivationState | None:
        return self._items.get(provider_id)

    def activate(self, state: ProviderActivationState) -> None:
        existing = self._items.get(state.provider_id)
        if existing is not None and existing.enabled:
            raise RuntimeError("provider activation already enabled")
        self._items[state.provider_id] = state

    def rollback(
        self,
        *,
        provider_id: str,
        rolled_back_by: str,
        rolled_back_at: datetime,
        reason: str,
        expected_activation_version: str,
        expected_activated_at: datetime,
    ) -> None:
        current = self._items.get(provider_id)
        if current is None:
            raise IntegrityViolation("provider activation rollback has no state")
        if (
            not current.enabled
            or current.activation_version != expected_activation_version
            or current.activated_at != expected_activated_at
        ):
            raise IntegrityViolation(
                "provider activation rollback lost its compare-and-set target"
            )
        self._items[provider_id] = ProviderActivationState(
            provider_id=provider_id,
            enabled=False,
            configuration_version=current.configuration_version,
            activation_version=current.activation_version,
            activated_by=current.activated_by,
            activated_at=current.activated_at,
            max_cost=current.max_cost,
            max_duration_seconds=current.max_duration_seconds,
            rollback_by=rolled_back_by,
            rollback_at=rolled_back_at,
            rollback_reason=reason[:256],
            rollback_from_configuration_version=current.configuration_version,
        )
