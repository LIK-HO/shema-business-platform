from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class SelectionLevel(StrEnum):
    CANDIDATE = "candidate"
    IDENTIFIED = "identified"
    VERIFIED = "verified"


@dataclass(frozen=True, slots=True)
class SearchCriteria:
    region: str
    industries: frozenset[str]
    limit: int = 50
    selection_level: SelectionLevel = SelectionLevel.CANDIDATE

    def __post_init__(self) -> None:
        if not self.region.strip():
            raise ValueError("region is required")
        if not self.industries:
            raise ValueError("at least one industry is required")
        if not 1 <= self.limit <= 500:
            raise ValueError("limit must be between 1 and 500")


@dataclass(frozen=True, slots=True)
class SearchHit:
    identity_id: str
    name: str
    region: str
    industries: frozenset[str]
    source_ref: str


class SearchProvider:
    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        raise NotImplementedError


class SearchService:
    """Canonical search contract; providers remain replaceable adapters."""

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    def execute(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        hits = self._provider.search(criteria)
        return hits[:criteria.limit]
