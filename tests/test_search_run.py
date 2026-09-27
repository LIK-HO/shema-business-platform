import json
from dataclasses import dataclass
from pathlib import Path

import pytest

from shema_platform.application.search_run import (
    SearchBudget,
    SearchCompleteness,
    SearchQualityMetrics,
    SearchRunService,
    SearchSource,
    SearchSourceStatus,
    SearchSourceUnavailable,
    evaluate_search_quality,
)
from shema_platform.domain.search import SearchCriteria, SearchHit


@dataclass
class FakeProvider:
    hits: tuple[SearchHit, ...] = ()
    error: Exception | None = None
    calls: int = 0

    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        self.calls += 1
        if self.error:
            raise self.error
        return self.hits


def hit(candidate_ref: str, *, source_ref: str = "source:item", tax_id: str | None = None) -> SearchHit:
    return SearchHit(
        candidate_ref=candidate_ref,
        name=f"Company {candidate_ref}",
        region="Moscow",
        industries=frozenset({"logistics"}),
        source_ref=source_ref,
        tax_id=tax_id,
    )


def criteria() -> SearchCriteria:
    return SearchCriteria(region="Moscow", industries=frozenset({"logistics"}), limit=50)


def test_contract_disables_network_and_ranking_authority() -> None:
    path = Path(__file__).parents[1] / "architecture" / "search_run_contract.json"
    payload = json.loads(path.read_text())
    assert payload["network_execution_enabled"] is False
    assert payload["ranking_authority"] is False
    assert "SOURCE_UNAVAILABLE" in payload["completeness_states"]
    assert "BUDGET_LIMITED" in payload["completeness_states"]


def test_empty_sources_are_explicitly_not_searched() -> None:
    result = SearchRunService().execute(criteria(), ())
    assert result.completeness is SearchCompleteness.NOT_SEARCHED
    assert result.hits == ()
    assert result.attempts == ()


def test_zero_results_are_distinct_from_not_searched() -> None:
    provider = FakeProvider()
    result = SearchRunService().execute(criteria(), (SearchSource("source:empty", provider),))
    assert result.completeness is SearchCompleteness.SEARCHED_NOT_FOUND
    assert result.attempts[0].status is SearchSourceStatus.SEARCHED_NOT_FOUND
    assert provider.calls == 1


def test_unavailable_source_remains_visible_and_does_not_become_not_found() -> None:
    provider = FakeProvider(error=SearchSourceUnavailable("offline"))
    result = SearchRunService().execute(criteria(), (SearchSource("source:offline", provider),))
    assert result.completeness is SearchCompleteness.SOURCE_UNAVAILABLE
    assert result.attempts[0].status is SearchSourceStatus.SOURCE_UNAVAILABLE
    assert result.attempts[0].error_code == "SearchSourceUnavailable"


def test_source_budget_prevents_unbounded_provider_calls() -> None:
    first = FakeProvider(hits=(hit("candidate-1"),))
    second = FakeProvider(hits=(hit("candidate-2"),))
    third = FakeProvider(hits=(hit("candidate-3"),))
    result = SearchRunService().execute(
        criteria(),
        (SearchSource("source:1", first), SearchSource("source:2", second), SearchSource("source:3", third)),
        budget=SearchBudget(max_sources=2, max_candidates=50),
    )
    assert result.completeness is SearchCompleteness.BUDGET_LIMITED
    assert first.calls == 1
    assert second.calls == 1
    assert third.calls == 0
    assert result.attempts[-1].status is SearchSourceStatus.BUDGET_LIMITED


def test_candidate_budget_is_explicit_and_caps_calls() -> None:
    first = FakeProvider(hits=tuple(hit(str(i)) for i in range(5)))
    second = FakeProvider(hits=(hit("later"),))
    result = SearchRunService().execute(
        criteria(),
        (SearchSource("source:1", first), SearchSource("source:2", second)),
        budget=SearchBudget(max_sources=5, max_candidates=5),
    )
    assert result.completeness is SearchCompleteness.BUDGET_LIMITED
    assert first.calls == 1
    assert second.calls == 0
    assert result.attempts[1].status is SearchSourceStatus.BUDGET_LIMITED


def test_source_order_is_preserved_without_ranking() -> None:
    first = FakeProvider(hits=(hit("first"),))
    second = FakeProvider(hits=(hit("second"),))
    result = SearchRunService().execute(criteria(), (SearchSource("source:first", first), SearchSource("source:second", second)))
    assert [item.candidate_ref for item in result.hits] == ["first", "second"]
    assert result.plan.source_refs == ("source:first", "source:second")


def test_deduplication_keeps_first_source_without_global_score() -> None:
    first = FakeProvider(hits=(hit("first", tax_id="7700000000"),))
    second = FakeProvider(hits=(hit("second", tax_id="7700000000"),))
    result = SearchRunService().execute(criteria(), (SearchSource("source:first", first), SearchSource("source:second", second)))
    assert [item.candidate_ref for item in result.hits] == ["first"]


def test_explicit_operator_selection_level_can_filter_results() -> None:
    verified_criteria = SearchCriteria(
        region="Moscow",
        industries=frozenset({"logistics"}),
        limit=50,
        selection_level="verified",
    )
    provider = FakeProvider(
        hits=(
            SearchHit("candidate", "Candidate", "Moscow", frozenset({"logistics"}), "source:candidate"),
            SearchHit("verified", "Verified", "Moscow", frozenset({"logistics"}), "source:verified", selection_level="verified"),
        )
    )
    result = SearchRunService().execute(verified_criteria, (SearchSource("source:search", provider),))
    assert [item.candidate_ref for item in result.hits] == ["verified"]


def test_duplicate_source_refs_are_rejected() -> None:
    provider = FakeProvider()
    with pytest.raises(ValueError, match="source_refs must be unique"):
        SearchRunService().execute(
            criteria(),
            (SearchSource("source:duplicate", provider), SearchSource("source:duplicate", provider)),
        )


@pytest.mark.parametrize(
    ("expected", "actual", "precision", "recall"),
    [
        (("a", "b"), (hit("a"), hit("b"), hit("c")), 2 / 3, 1.0),
        (("a", "b"), (hit("a"),), 1.0, 0.5),
        (("a",), (), 0.0, 0.0),
        ((), (), 1.0, 1.0),
    ],
)
def test_search_quality_metrics(expected, actual, precision, recall) -> None:
    metrics = evaluate_search_quality(
        expected, actual, planned_source_count=4, searched_source_count=3
    )
    assert isinstance(metrics, SearchQualityMetrics)
    assert metrics.precision == pytest.approx(precision)
    assert metrics.recall == pytest.approx(recall)
    assert metrics.source_coverage == pytest.approx(0.75)
