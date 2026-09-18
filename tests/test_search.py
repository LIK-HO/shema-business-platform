from dataclasses import dataclass

import pytest

from shema_platform.domain.search import (
    SearchCriteria,
    SearchHit,
    SearchProvider,
    SearchService,
)


@dataclass
class FakeSearchProvider(SearchProvider):
    hits: tuple[SearchHit, ...]

    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        return self.hits


def test_search_filters_wrong_region_industry_invalid_identity_and_duplicates() -> None:
    hits = (
        SearchHit("1", "Company 1", "Moscow", frozenset({"logistics"}), "source:1"),
        SearchHit("1", "Company 1 duplicate", "Moscow", frozenset({"logistics"}), "source:dup"),
        SearchHit("2", "Company 2", "Moscow", frozenset({"manufacturing"}), "source:2"),
        SearchHit("3", "Company 3", "SPB", frozenset({"logistics"}), "source:3"),
        SearchHit("", "Invalid", "Moscow", frozenset({"logistics"}), "source:4"),
        SearchHit("4", "No source", "Moscow", frozenset({"logistics"}), ""),
    )
    service = SearchService(FakeSearchProvider(hits))

    result = service.execute(
        SearchCriteria(
            region=" Moscow ",
            industries=frozenset({"Logistics", "Warehousing"}),
            limit=50,
        )
    )

    assert tuple(hit.identity_id for hit in result) == ("1",)
    assert result[0].name == "Company 1"


def test_search_enforces_canonical_limit() -> None:
    hits = tuple(
        SearchHit(
            identity_id=str(i),
            name=f"Company {i}",
            region="Moscow",
            industries=frozenset({"logistics"}),
            source_ref=f"source:{i}",
        )
        for i in range(60)
    )
    service = SearchService(FakeSearchProvider(hits))

    result = service.execute(
        SearchCriteria(
            region="Moscow",
            industries=frozenset({"logistics", "warehousing"}),
            limit=50,
        )
    )

    assert len(result) == 50


@pytest.mark.parametrize("limit", [0, 501])
def test_search_rejects_invalid_limit(limit: int) -> None:
    with pytest.raises(ValueError):
        SearchCriteria(
            region="Moscow",
            industries=frozenset({"logistics"}),
            limit=limit,
        )


def test_search_rejects_blank_criteria() -> None:
    with pytest.raises(ValueError):
        SearchCriteria(region=" ", industries=frozenset({"logistics"}))
    with pytest.raises(ValueError):
        SearchCriteria(region="Moscow", industries=frozenset({" ", ""}))
