from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class JobState(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRYABLE_FAILURE = "retryable_failure"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int = 5
    initial_delay_seconds: float = 1.0
    max_delay_seconds: float = 60.0

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay_seconds <= 0:
            raise ValueError("initial_delay_seconds must be > 0")
        if self.max_delay_seconds <= 0:
            raise ValueError("max_delay_seconds must be > 0")

    def delay_for(self, attempt: int) -> float:
        if attempt < 1:
            raise ValueError("attempt must be >= 1")
        return min(self.initial_delay_seconds * (2 ** (attempt - 1)), self.max_delay_seconds)

    def is_retryable(self, attempt: int) -> bool:
        return attempt < self.max_attempts
