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
        normalized_region = self.region.strip()
        normalized_industries = frozenset(
            item.strip().lower() for item in self.industries if item.strip()
        )
        object.__setattr__(self, "region", normalized_region)
        object.__setattr__(self, "industries", normalized_industries)

        if not normalized_region:
            raise ValueError("region is required")
        if not normalized_industries:
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
        seen: set[str] = set()
        accepted: list[SearchHit] = []

        for hit in hits:
            identity_id = hit.identity_id.strip()
            name = hit.name.strip()
            region = hit.region.strip()
            source_ref = hit.source_ref.strip()
            industries = frozenset(
                item.strip().lower() for item in hit.industries if item.strip()
            )

            if not identity_id or not name or not source_ref:
                continue
            if region != criteria.region:
                continue
            if not industries.intersection(criteria.industries):
                continue
            if identity_id in seen:
                continue

            seen.add(identity_id)
            accepted.append(
                SearchHit(
                    identity_id=identity_id,
                    name=name,
                    region=region,
                    industries=industries,
                    source_ref=source_ref,
                )
            )
            if len(accepted) >= criteria.limit:
                break

        return tuple(accepted)
