from __future__ import annotations

from collections.abc import Callable, Mapping, Protocol
from dataclasses import dataclass, field
from datetime import UTC, datetime
from decimal import Decimal
from enum import StrEnum
from hashlib import sha256


class ProcurementProviderError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ProcurementLaw(StrEnum):
    FZ44 = "44fz"
    FZ223 = "223fz"
    PPRF615 = "pprf615"


class ProcurementCollection(StrEnum):
    PURCHASES = "purchases"
    PLANS = "plans"


@dataclass(frozen=True, slots=True)
class ProcurementQuery:
    law: ProcurementLaw
    collection: ProcurementCollection
    limit: int = 50
    skip: int = 0
    reg_number: str | None = None
    sort: str | None = None
    provider_filters: tuple[tuple[str, str], ...] = ()

    def __post_init__(self) -> None:
        if not 1 <= self.limit <= 1000:
            raise ValueError("limit must be between 1 and 1000")
        if self.skip < 0:
            raise ValueError("skip cannot be negative")
        if self.reg_number is not None and not self.reg_number.strip():
            raise ValueError("reg_number cannot be blank")
        normalized = tuple(
            sorted(
                (key.strip(), value.strip())
                for key, value in self.provider_filters
                if key.strip() and value.strip()
            )
        )
        if len({key for key, _ in normalized}) != len(normalized):
            raise ValueError("provider_filters keys must be unique")
        object.__setattr__(self, "reg_number", self.reg_number.strip() if self.reg_number else None)
        object.__setattr__(self, "sort", self.sort.strip() if self.sort else None)
        object.__setattr__(self, "provider_filters", normalized)


@dataclass(frozen=True, slots=True)
class ProcurementOpportunity:
    provider_id: str
    source_ref: str
    external_id: str
    law: ProcurementLaw
    collection: ProcurementCollection
    title: str
    customer_name: str | None
    customer_tax_id: str | None
    max_price: Decimal | None
    published_at: datetime | None
    deadline_at: datetime | None
    stage: str | None
    source_url: str | None = None

    def __post_init__(self) -> None:
        if not self.provider_id.strip():
            raise ValueError("provider_id is required")
        if not self.source_ref.startswith("https://"):
            raise ValueError("source_ref must use HTTPS")
        if not self.external_id.strip():
            raise ValueError("external_id is required")
        if not self.title.strip():
            raise ValueError("title is required")
        if self.customer_tax_id is not None and not self.customer_tax_id.strip():
            raise ValueError("customer_tax_id cannot be blank")
        if self.source_url is not None and not self.source_url.startswith("https://"):
            raise ValueError("source_url must use HTTPS")

    @property
    def fingerprint(self) -> str:
        payload = "|".join(
            (
                self.external_id,
                self.collection.value,
                self.title,
                self.customer_name or "",
                self.customer_tax_id or "",
                str(self.max_price) if self.max_price is not None else "",
                self.published_at.isoformat() if self.published_at else "",
                self.deadline_at.isoformat() if self.deadline_at else "",
                self.stage or "",
            )
        )
        return sha256(payload.encode("utf-8")).hexdigest()


@dataclass(frozen=True, slots=True)
class ProcurementSearchResult:
    items: tuple[ProcurementOpportunity, ...]
    has_more: bool
    next_skip: int
    observed_at: datetime


class ProcurementProvider(Protocol):
    provider_id: str

    def search(self, query: ProcurementQuery) -> ProcurementSearchResult: ...


@dataclass(frozen=True, slots=True)
class BoundedProcurementSearch:
    provider: ProcurementProvider
    max_attempts: int = 3
    backoff_seconds: float = 0.25
    sleeper: Callable[[float], None] | None = None

    def __post_init__(self) -> None:
        if not 1 <= self.max_attempts <= 3:
            raise ValueError("max_attempts must be between 1 and 3")
        if self.backoff_seconds < 0:
            raise ValueError("backoff_seconds cannot be negative")

    def search(self, query: ProcurementQuery) -> ProcurementSearchResult:
        from time import sleep

        sleeper = self.sleeper or sleep
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                return self.provider.search(query)
            except ProcurementProviderError as exc:
                last_error = exc
                if not exc.retryable or attempt >= self.max_attempts:
                    raise
            except (TimeoutError, ConnectionError) as exc:
                last_error = exc
                if attempt >= self.max_attempts:
                    raise
            sleeper(self.backoff_seconds * (2 ** (attempt - 1)))
        raise RuntimeError("procurement search exhausted retry budget") from last_error


@dataclass(frozen=True, slots=True)
class ProcurementWatchState:
    fingerprints: Mapping[str, str] = field(default_factory=dict)
    cursor: str = "0"

    def with_page(self, result: ProcurementSearchResult) -> ProcurementWatchState:
        updated = dict(self.fingerprints)
        for item in result.items:
            updated[f"{item.provider_id}:{item.external_id}"] = item.fingerprint
        return ProcurementWatchState(
            fingerprints=updated,
            cursor=str(result.next_skip),
        )


@dataclass(frozen=True, slots=True)
class ProcurementWatchResult:
    new_items: tuple[ProcurementOpportunity, ...]
    changed_items: tuple[ProcurementOpportunity, ...]
    state: ProcurementWatchState


class ProcurementMonitor:
    """Cursor-based, idempotent procurement monitoring without canonical-state mutation."""

    def __init__(
        self,
        provider: ProcurementProvider,
        *,
        max_attempts: int = 3,
        sleeper=None,
    ) -> None:
        self._search = BoundedProcurementSearch(
            provider,
            max_attempts=max_attempts,
            sleeper=sleeper,
        )

    def poll(
        self,
        query: ProcurementQuery,
        state: ProcurementWatchState,
    ) -> ProcurementWatchResult:
        result = self._search.search(query)
        new_items: list[ProcurementOpportunity] = []
        changed_items: list[ProcurementOpportunity] = []
        for item in result.items:
            previous = state.fingerprints.get(f"{item.provider_id}:{item.external_id}")
            if previous is None:
                new_items.append(item)
            elif previous != item.fingerprint:
                changed_items.append(item)
        return ProcurementWatchResult(
            new_items=tuple(new_items),
            changed_items=tuple(changed_items),
            state=state.with_page(result),
        )


def parse_datetime(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip().replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)
