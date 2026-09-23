from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from threading import Lock
import time

from shema_platform.application.research import (
    ProviderCapability,
    ResearchBudget,
)


@dataclass(frozen=True, slots=True)
class ProviderCallDecision:
    allowed: bool
    stop_operation: bool
    reason: str | None = None


class ProviderRateLimiter:
    """Process-local provider rate guard shared by research operations."""

    def __init__(self, clock: Callable[[], float] = time.monotonic) -> None:
        self._clock = clock
        self._last_called_at: dict[str, float] = {}
        self._lock = Lock()

    def allow(self, provider_id: str, max_requests_per_second: float) -> bool:
        interval = 1.0 / max_requests_per_second
        now = self._clock()
        with self._lock:
            previous = self._last_called_at.get(provider_id)
            if previous is not None and now - previous < interval:
                return False
            self._last_called_at[provider_id] = now
            return True


class ProviderResourceGuard:
    """Fail-before-I/O guard for intelligence provider resource consumption."""

    def __init__(self, rate_limiter: ProviderRateLimiter | None = None) -> None:
        self._rate_limiter = rate_limiter or ProviderRateLimiter()

    def authorize(
        self,
        capability: ProviderCapability,
        budget: ResearchBudget,
        *,
        remaining_calls: int,
        remaining_sources: int,
        remaining_tokens: int,
        remaining_cost: float,
        remaining_time: float,
        requested_sources: int,
    ) -> ProviderCallDecision:
        if remaining_calls <= 0:
            return ProviderCallDecision(
                allowed=False,
                stop_operation=True,
                reason="provider_call_budget_exhausted",
            )
        if remaining_sources <= 0 or requested_sources <= 0:
            return ProviderCallDecision(
                allowed=False,
                stop_operation=True,
                reason="source_budget_exhausted",
            )
        if capability.cost_per_call > remaining_cost:
            return ProviderCallDecision(
                allowed=False,
                stop_operation=False,
                reason="provider_cost_limit",
            )
        if capability.estimated_tokens_per_call > remaining_tokens:
            return ProviderCallDecision(
                allowed=False,
                stop_operation=False,
                reason="provider_token_limit",
            )
        if capability.estimated_latency_seconds > remaining_time:
            return ProviderCallDecision(
                allowed=False,
                stop_operation=False,
                reason="provider_time_limit",
            )
        if requested_sources > remaining_sources:
            return ProviderCallDecision(
                allowed=False,
                stop_operation=False,
                reason="requested_source_limit",
            )

        if not self._rate_limiter.allow(
            capability.provider_id,
            capability.max_requests_per_second,
        ):
            return ProviderCallDecision(
                allowed=False,
                stop_operation=False,
                reason="provider_rate_limit",
            )

        return ProviderCallDecision(
            allowed=True,
            stop_operation=False,
        )
