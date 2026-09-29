from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


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
    ) -> None: ...
