import json
from pathlib import Path

from fastapi.testclient import TestClient

from shema_platform.application.operator_search import OperatorSearchService
from shema_platform.application.search_planning import (
    RegistryBackedSearchPlanner,
    SearchSourceRegistry,
)
from shema_platform.application.search_run import SearchRunService
from shema_platform.domain.search import SearchHit, SelectionLevel
from shema_platform.experience.api import create_app
from shema_platform.experience.search_application import SearchOnlyAPIApplication
from shema_platform.foundation.authentication import AuthenticatedActor, AuthenticationPort


class FakeAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        assert authorization == "Bearer test-token"
        return AuthenticatedActor("operator-1", trust_level=2)


class FakeProvider:
    def search(self, criteria):
        return (
            SearchHit(
                "candidate-1",
                "Company 1",
                criteria.region,
                frozenset(criteria.industries),
                "fns_transparent_business",
                "7700000000",
                selection_level=SelectionLevel.CANDIDATE,
            ),
        )


def application() -> SearchOnlyAPIApplication:
    contract = json.loads(
        (
            Path(__file__).parents[1]
            / "architecture"
            / "intelligence_source_registry_contract.json"
        ).read_text()    )
    planner = RegistryBackedSearchPlanner(SearchSourceRegistry.from_contract(contract))
    service = OperatorSearchService(
        planner,
        SearchRunService(),
        {"fns_transparent_business": FakeProvider()},
        default_source_ids=("fns_transparent_business",),
    )
    return SearchOnlyAPIApplication(service)


def test_search_only_api_application_returns_completeness_and_source_provenance() -> None:
    response = TestClient(create_app(application(), FakeAuthenticator())).post(
        "/v1/search",
        headers={"Authorization": "Bearer test-token", "X-Correlation-Id": "corr-search"},
        json={
            "region": "Moscow",
            "industries": ["logistics"],
            "sourceIds": ["fns_transparent_business"],
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["completeness"] == "COMPLETE"
    assert body["planVersion"] == "search-plan:v1"
    assert body["sourceAttempts"][0]["sourceId"] == "fns_transparent_business"
    assert body["sourceAttempts"][0]["reliability"] == "authoritative"
    assert body["results"][0]["candidateRef"] == "candidate-1"
    assert body["results"][0]["sourceRefs"] == ["fns_transparent_business"]
    assert response.headers["X-Correlation-Id"] == "corr-search"


def test_search_only_api_application_preserves_backward_compatible_defaults() -> None:
    response = TestClient(create_app(application(), FakeAuthenticator())).post(
        "/v1/search",
        headers={"Authorization": "Bearer test-token"},
        json={"region": "Moscow", "industries": ["logistics"]},
    )

    assert response.status_code == 200
    assert response.json()["completeness"] == "COMPLETE"
