from __future__ import annotations

# ruff: noqa: I001

import json
from pathlib import Path

import pytest

import shema_platform.application.search_planning as search_planning
import shema_platform.application.search_run as search_run
import shema_platform.domain.search as domain_search


ROOT = Path(__file__).parents[1]


def contract() -> dict:
    return json.loads((
        ROOT / "architecture" / "intelligence_source_registry_contract.json"
    ).read_text(encoding="utf-8"))


def criteria() -> domain_search.SearchCriteria:
    return domain_search.SearchCriteria(
        region="Moscow",
        industries=frozenset({"logistics"}),
        limit=50,
    )


def test_registry_planner_accepts_declared_sources_only() -> None:
    planner = search_planning.RegistryBackedSearchPlanner(
        search_planning.SearchSourceRegistry.from_contract(contract())
    )
    plan = planner.plan(
        criteria(),
        ("fns_transparent_business", "primary_company_site"),
    )

    assert plan.plan_version == "search-plan:v1"
    assert plan.source_ids == ("fns_transparent_business", "primary_company_site")
    assert plan.sources[0].reliability == "authoritative"
    assert plan.sources[1].reliability == "primary"
    assert plan.lawful_access_required is True


def test_registry_planner_preserves_explicit_source_order_without_ranking() -> None:
    planner = search_planning.RegistryBackedSearchPlanner(
        search_planning.SearchSourceRegistry.from_contract(contract())
    )
    plan = planner.plan(
        criteria(),
        ("open_web_signal", "fns_transparent_business"),
    )

    assert plan.source_ids == ("open_web_signal", "fns_transparent_business")
    assert [source.source_class for source in plan.sources] == [
        "open_web_signal",
        "official_registry",
    ]


def test_registry_rejects_unknown_source() -> None:
    registry = search_planning.SearchSourceRegistry.from_contract(contract())
    with pytest.raises(ValueError, match="unknown search source"):
        registry.resolve(("does_not_exist",))


def test_registry_rejects_duplicate_source_ids() -> None:
    registry = search_planning.SearchSourceRegistry.from_contract(contract())
    with pytest.raises(ValueError, match="unique"):
        registry.resolve(("fns_transparent_business", "fns_transparent_business"))


def test_registry_requires_at_least_one_source_for_a_plan() -> None:
    registry = search_planning.SearchSourceRegistry.from_contract(contract())
    with pytest.raises(ValueError, match="at least one source_id"):
        registry.resolve(())


def test_registry_keeps_search_budget_separate_from_source_reliability() -> None:
    planner = search_planning.RegistryBackedSearchPlanner(search_planning.SearchSourceRegistry.from_contract(contract()))
    plan = planner.plan(
        criteria(),
        ("fns_transparent_business",),
        budget=search_run.SearchBudget(max_sources=1, max_candidates=25),
    )

    assert plan.budget.max_sources == 1
    assert plan.budget.max_candidates == 25
    assert plan.sources[0].reliability == "authoritative"


def test_registry_contract_cannot_enable_network_automation() -> None:
    payload = contract()
    payload["policy"]["network_execution_enabled"] = True
    with pytest.raises(ValueError, match="network execution disabled"):
        search_planning.SearchSourceRegistry.from_contract(payload)


def test_registry_rejects_provider_entry_with_network_automation() -> None:
    payload = contract()
    payload["sources"][0]["network_automation"] = True
    with pytest.raises(ValueError, match="network automation is disabled"):
        search_planning.SearchSourceRegistry.from_contract(payload)


def test_registry_requires_reliability_to_stay_separate_from_claim_confidence() -> None:
    payload = contract()
    payload["policy"]["source_reliability_separate_from_claim_confidence"] = False
    with pytest.raises(ValueError, match="separate claim confidence"):
        search_planning.SearchSourceRegistry.from_contract(payload)
