from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ProviderBudget:
    max_calls: int
    max_requests_per_second: float

    def __post_init__(self) -> None:
        if self.max_calls < 0:
            raise ValueError("max_calls must be non-negative")
        if self.max_requests_per_second <= 0:
            raise ValueError("max_requests_per_second must be positive")


class ProviderBudgetExceeded(RuntimeError):
    """Raised before external I/O when the explicit provider budget is exhausted."""


class ProviderCallBudget:
    """Process-local, operation-scoped external-call budget."""

    def __init__(self, budget: ProviderBudget) -> None:
        self._budget = budget
        self._calls = 0

    @property
    def calls_used(self) -> int:
        return self._calls

    @property
    def calls_remaining(self) -> int:
        return self._budget.max_calls - self._calls

    def reserve(self) -> None:
        if self._calls >= self._budget.max_calls:
            raise ProviderBudgetExceeded("provider call budget exhausted")
        self._calls += 1
