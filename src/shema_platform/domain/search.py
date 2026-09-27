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
    source_refs: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.captured_at < self.observed_at:
            raise ValueError("captured_at cannot precede observed_at")
        primary_source = self.source_ref.strip()
        normalized_sources = tuple(
            dict.fromkeys(
                source
                for source in (ref.strip() for ref in self.source_refs)
                if source
            )
        )
        if not normalized_sources:
            normalized_sources = (primary_source,)
        elif primary_source and primary_source not in normalized_sources:
            normalized_sources = (primary_source, *normalized_sources)
        object.__setattr__(self, "source_refs", normalized_sources)


class SearchProvider:
    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        raise NotImplementedError


class SearchService:
    """Canonical search contract; providers remain replaceable adapters."""

    def __init__(self, provider: SearchProvider) -> None:
        self._provider = provider

    @staticmethod
    def _conflicting_identity_fields(
        existing: SearchHit,
        candidate: SearchHit,
    ) -> bool:
        return bool(
            existing.tax_id
            and candidate.tax_id
            and existing.tax_id != candidate.tax_id
        ) or bool(
            existing.registration_id
            and candidate.registration_id
            and existing.registration_id != candidate.registration_id
        )

    @classmethod
    def _merge_index(cls, accepted: list[SearchHit], candidate: SearchHit) -> int | None:
        candidate_has_identifier = bool(candidate.tax_id or candidate.registration_id)
        matches: list[int] = []

        for index, existing in enumerate(accepted):
            if cls._conflicting_identity_fields(existing, candidate):
                continue

            identifier_match = bool(
                (candidate.tax_id and existing.tax_id == candidate.tax_id)
                or (
                    candidate.registration_id
                    and existing.registration_id == candidate.registration_id
                )
            )
            source_local_match = (
                not candidate_has_identifier
                and not (existing.tax_id or existing.registration_id)
                and existing.source_ref == candidate.source_ref
                and existing.candidate_ref == candidate.candidate_ref
            )

            if identifier_match or source_local_match:
                matches.append(index)

        return matches[0] if len(matches) == 1 else None

    @staticmethod
    def _merged_hit(existing: SearchHit, candidate: SearchHit) -> SearchHit:
        source_refs = tuple(
            dict.fromkeys((*existing.source_refs, *candidate.source_refs))
        )
        contact_refs = tuple(
            dict.fromkeys((*existing.contact_refs, *candidate.contact_refs))
        )
        return SearchHit(
            candidate_ref=existing.candidate_ref,
            name=existing.name,
            region=existing.region,
            industries=frozenset((*existing.industries, *candidate.industries)),
            source_ref=existing.source_ref,
            tax_id=existing.tax_id or candidate.tax_id,
            registration_id=existing.registration_id or candidate.registration_id,
            contact_refs=contact_refs,
            selection_level=existing.selection_level,
            observed_at=existing.observed_at,
            captured_at=existing.captured_at,
            source_refs=source_refs,
        )

    def execute(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        hits = self._provider.search(criteria)
        accepted: list[SearchHit] = []

        for hit in hits:
            candidate_ref = hit.candidate_ref.strip()
            name = hit.name.strip()
            region = hit.region.strip()
            source_ref = hit.source_ref.strip()
            tax_id = hit.tax_id.strip() if hit.tax_id else None
            registration_id = (
                hit.registration_id.strip() if hit.registration_id else None
            )
            industries = frozenset(
                item.strip().lower() for item in hit.industries if item.strip()
            )
            contact_refs = tuple(ref.strip() for ref in hit.contact_refs if ref.strip())
            source_refs = tuple(
                dict.fromkeys(
                    source
                    for source in (
                        ref.strip() for ref in (*hit.source_refs, source_ref)
                    )
                    if source
                )
            )

            if not candidate_ref or not name or not source_ref:
                continue
            if region != criteria.region:
                continue
            if not industries.intersection(criteria.industries):
                continue
            if hit.selection_level.rank() < criteria.selection_level.rank():
                continue

            normalized = SearchHit(
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
                source_refs=source_refs,
            )
            merge_index = self._merge_index(accepted, normalized)

            if merge_index is None:
                accepted.append(normalized)
            else:
                accepted[merge_index] = self._merged_hit(
                    accepted[merge_index],
                    normalized,
                )

            if len(accepted) >= criteria.limit:
                break

        return tuple(accepted)
