from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum


class SelectionLevel(StrEnum):
    CANDIDATE = "candidate"
    IDENTIFIED = "identified"
    VERIFIED = "verified"

    def rank(self) -> int:
        return {
            SelectionLevel.CANDIDATE: 1,
            SelectionLevel.IDENTIFIED: 2,
            SelectionLevel.VERIFIED: 3,
        }[self]


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
    candidate_ref: str
    name: str
    region: str
    industries: frozenset[str]
    source_ref: str
    tax_id: str | None = None
    registration_id: str | None = None
    contact_refs: tuple[str, ...] = ()
    selection_level: SelectionLevel = SelectionLevel.CANDIDATE
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    captured_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def __post_init__(self) -> None:
        if self.captured_at < self.observed_at:
            raise ValueError("captured_at cannot precede observed_at")


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
            candidate_ref = hit.candidate_ref.strip()
            name = hit.name.strip()
            region = hit.region.strip()
            source_ref = hit.source_ref.strip()
            tax_id = hit.tax_id.strip() if hit.tax_id else None
            registration_id = hit.registration_id.strip() if hit.registration_id else None
            industries = frozenset(
                item.strip().lower() for item in hit.industries if item.strip()
            )
            contact_refs = tuple(ref.strip() for ref in hit.contact_refs if ref.strip())

            if not candidate_ref or not name or not source_ref:
                continue
            if region != criteria.region:
                continue
            if not industries.intersection(criteria.industries):
                continue
            if hit.selection_level.rank() < criteria.selection_level.rank():
                continue

            dedupe_key = tax_id or candidate_ref
            if dedupe_key in seen:
                continue

            seen.add(dedupe_key)
            accepted.append(
                SearchHit(
                    candidate_ref=candidate_ref,
                    name=name,
                    region=region,
                    industries=industries,
                    source_ref=source_ref,
                    tax_id=tax_id,
                    registration_id=registration_id,
                    contact_refs=contact_refs,
                    selection_level=hit.selection_level,
                    observed_at=hit.observed_at,
                    captured_at=hit.captured_at,
                )
            )
            if len(accepted) >= criteria.limit:
                break

        return tuple(accepted)
