from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from time import sleep
from typing import Protocol


class CounterpartyLookupProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class CounterpartyLookupProvider(Protocol):
    def lookup(self, query: "CounterpartyLookupQuery") -> "CounterpartyProviderRecord": ...


class CounterpartyLookupIdentifierType(StrEnum):
    INN = "INN"
    OGRN = "OGRN"
    OGRNIP = "OGRNIP"


@dataclass(frozen=True, slots=True)
class CounterpartyLookupQuery:
    identifier_type: CounterpartyLookupIdentifierType
    identifier: str

    def __post_init__(self) -> None:
        normalized = self.identifier.strip()
        if not normalized.isdigit():
            raise ValueError("counterparty identifier must contain digits only")
        expected_lengths = {
            CounterpartyLookupIdentifierType.INN: {10, 12},
            CounterpartyLookupIdentifierType.OGRN: {13},
            CounterpartyLookupIdentifierType.OGRNIP: {15},
        }
        if len(normalized) not in expected_lengths[self.identifier_type]:
            raise ValueError(f"{self.identifier_type.value} has invalid length")
        object.__setattr__(self, "identifier", normalized)


@dataclass(frozen=True, slots=True)
class CounterpartyProviderRecord:
    provider_id: str
    source_ref: str
    canonical_name: str
    tax_id: str | None
    registration_id: str | None
    legal_status: str | None
    observed_at_ms: int | None = None
    provider_type: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.source_ref.startswith("https://"):
            raise ValueError("source_ref must use HTTPS")
        if not self.canonical_name.strip():
            raise ValueError("canonical_name is required")
        if not self.tax_id and not self.registration_id:
            raise ValueError("tax_id or registration_id is required")


@dataclass(frozen=True, slots=True)
class BoundedCounterpartyLookup:
    provider: CounterpartyLookupProvider
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    sleeper: object = sleep

    def __post_init__(self) -> None:
        if self.max_attempts < 1 or self.max_attempts > 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.provider.lookup(query)
            except CounterpartyLookupProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.max_attempts:
                    raise
            except (TimeoutError, ConnectionError) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    raise

            self.sleeper(self.backoff_seconds * (2 ** (attempt - 1)))

        raise RuntimeError("counterparty lookup exhausted retry budget") from last_error
