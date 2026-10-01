from unittest.mock import Mock

from shema_platform.experience.api import APIApplication, RequestContext
from shema_platform.experience.api_models import (
    DiagnosticsResponse,
    SearchResponse,
)
from shema_platform.experience.search_composition import SearchAugmentedAPIApplication


def context() -> RequestContext:
    return RequestContext(
        correlation_id="corr-search-runtime",
        actor_id="operator-1",
        trust_level=2,
        idempotency_key=None,
    )


def test_search_augmented_application_routes_search_to_search_capability() -> None:
    base = Mock(spec=APIApplication)
    search = Mock(spec=APIApplication)
    search.search.return_value = SearchResponse(
        results=[],
        correlationId="corr-search-runtime",
    )
    composed = SearchAugmentedAPIApplication(base, search)

    result = composed.search(Mock(), context())

    assert result.correlation_id == "corr-search-runtime"
    search.search.assert_called_once()
    base.search.assert_not_called()


def test_search_augmented_application_keeps_non_search_calls_on_base() -> None:
    base = Mock(spec=APIApplication)
    search = Mock(spec=APIApplication)
    base.get_diagnostics.return_value = DiagnosticsResponse(healthy=True, checks=[])
    composed = SearchAugmentedAPIApplication(base, search)

    result = composed.get_diagnostics(context())

    assert result.healthy is True
    base.get_diagnostics.assert_called_once()
    search.get_diagnostics.assert_not_called()
