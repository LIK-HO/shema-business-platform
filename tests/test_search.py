from dataclasses import dataclass

from shema_platform.domain.search import (
    SearchCriteria,
    SearchHit,
    SearchProvider,
    SearchService,
    SelectionLevel,
)


@dataclass
class FakeSearchProvider(SearchProvider):
    hits: tuple[SearchHit, ...]

    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        assert criteria.region == "Moscow"
        assert criteria.selection_level is SelectionLevel.CANDIDATE
        return self.hits


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
