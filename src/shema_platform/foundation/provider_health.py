from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime


@dataclass(frozen=True, slots=True)
class ProviderHealth:
    provider_id: str
    enabled: bool
    configured: bool
    reachable: bool | None
    last_checked_at: datetime | None
    last_error_code: str | None

    @property
    def ready(self) -> bool:
        return (
            not self.enabled
            or (
                self.configured
                and self.reachable is True
            )
        )


class ProviderHealthRegistry:
    """In-memory operational provider health state; never stores secrets or payloads."""

    def __init__(self) -> None:
        self._states: dict[str, ProviderHealth] = {}

    def register(
        self,
        provider_id: str,
        *,
        enabled: bool,
        configured: bool,
    ) -> ProviderHealth:
        state = ProviderHealth(
            provider_id=provider_id,
            enabled=enabled,
            configured=configured,
            reachable=None,
            last_checked_at=None,
            last_error_code=None,
        )
        self._states[provider_id] = state
        return state

    def mark_reachable(
        self,
        provider_id: str,
        *,
        checked_at: datetime | None = None,
    ) -> ProviderHealth:
        current = self._require(provider_id)
        state = ProviderHealth(
            provider_id=current.provider_id,
            enabled=current.enabled,
            configured=current.configured,
            reachable=True,
            last_checked_at=checked_at or datetime.now(UTC),
            last_error_code=None,
        )
        self._states[provider_id] = state
        return state

    def mark_unreachable(
        self,
        provider_id: str,
        *,
        error_code: str,
        checked_at: datetime | None = None,
    ) -> ProviderHealth:
        if not error_code.strip():
            raise ValueError("error_code is required")
        current = self._require(provider_id)
        state = ProviderHealth(
            provider_id=current.provider_id,
            enabled=current.enabled,
            configured=current.configured,
            reachable=False,
            last_checked_at=checked_at or datetime.now(UTC),
            last_error_code=error_code[:128],
        )
        self._states[provider_id] = state
        return state

    def snapshot(self) -> tuple[ProviderHealth, ...]:
        return tuple(
            self._states[provider_id]
            for provider_id in sorted(self._states)
        )

    def ready(self) -> bool:
        return all(state.ready for state in self._states.values())

    def _require(self, provider_id: str) -> ProviderHealth:
        try:
            return self._states[provider_id]
        except KeyError as exc:
            raise KeyError(
                f"provider health is not registered: {provider_id}"
            ) from exc
