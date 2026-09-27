from dataclasses import dataclass

import pytest

from shema_platform.application.operator_search import OperatorSearchService
from shema_platform.application.search_planning import (
    RegistryBackedSearchPlanner,
    SearchSourceRegistry,
)
from shema_platform.application.search_run import (
    SearchRunService,
    SearchSourceUnavailable,
)
from shema_platform.domain.search import SearchCriteria, SearchHit


@dataclass
class FakeProvider:
    hits: tuple[SearchHit, ...] = ()
    error: Exception | None = None

    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        if self.error:
            raise self.error
        return self.hits


def hit(candidate_ref: str, *, source_ref: str = "source:item") -> SearchHit:
    return SearchHit(
        candidate_ref=candidate_ref,
        name=f"Company {candidate_ref}",
        region="Moscow",
        industries=frozenset({"logistics"}),
        source_ref=source_ref,
    )


def registry() -> SearchSourceRegistry:
    import json
    from pathlib import Path

    contract = json.loads(
        (
            Path(__file__).parents[1]
            / "architecture"
            / "intelligence_source_registry_contract.json"
        ).read_text(encoding="utf-8")
    )
    return SearchSourceRegistry.from_contract(contract)


def criteria() -> SearchCriteria:
    return SearchCriteria(
        region="Moscow",
        industries=frozenset({"logistics"}),
        limit=50,
    )


def service(*providers: tuple[str, FakeProvider]) -> OperatorSearchService:
    registry_obj = registry()
    planner = RegistryBackedSearchPlanner(registry_obj)
    adapters = {source_id: provider for source_id, provider in providers}
    return OperatorSearchService(
        planner,
        SearchRunService(),
        adapters,
        default_source_ids=tuple(adapters),
    )


def test_operator_search_composes_registry_plan_and_execution() -> None:
    result = service(
        ("fns_transparent_business", FakeProvider((hit("one", source_ref="one"),))),
    ).execute(criteria())

    assert result.plan.plan_version == "search-plan:v1"
    assert result.run.completeness.value == "COMPLETE"
    assert [item.candidate_ref for item in result.run.hits] == ["one"]
    assert result.plan.sources[0].reliability == "authoritative"


def test_operator_search_exposes_unavailable_source_as_incomplete_state() -> None:
    result = service(
        ("fns_transparent_business", FakeProvider(error=SearchSourceUnavailable("offline"))),
    ).execute(criteria())

    assert result.run.completeness.value == "SOURCE_UNAVAILABLE"
    assert result.run.attempts[0].error_code == "SearchSourceUnavailable"


def test_operator_search_rejects_missing_adapter_before_execution() -> None:
    with pytest.raises(ValueError, match="adapter not configured"):
        service().execute(
            criteria(),
            source_ids=("fns_transparent_business",),
        )


def test_operator_search_uses_explicit_source_ids_over_defaults() -> None:
    provider = FakeProvider((hit("one"),))
    other = FakeProvider((hit("two"),))
    result = service(
        ("fns_transparent_business", provider),
        ("primary_company_site", other),
    ).execute(
        criteria(),
        source_ids=("primary_company_site",),
    )

    assert result.plan.source_ids == ("primary_company_site",)
    assert [item.candidate_ref for item in result.run.hits] == ["two"]
