import pytest

from shema_platform.foundation.provider_budget import (
    ProviderBudget,
    ProviderBudgetExceeded,
    ProviderCallBudget,
)


def test_budget_reserves_before_external_call() -> None:
    budget = ProviderCallBudget(
        ProviderBudget(max_calls=2, max_requests_per_second=1.0)
    )

    budget.reserve()
    budget.reserve()

    assert budget.calls_used == 2
    assert budget.calls_remaining == 0

    with pytest.raises(ProviderBudgetExceeded):
        budget.reserve()


def test_budget_rejects_invalid_limits() -> None:
    with pytest.raises(ValueError):
        ProviderBudget(max_calls=-1, max_requests_per_second=1.0)
    with pytest.raises(ValueError):
        ProviderBudget(max_calls=1, max_requests_per_second=0)


def test_opencorporates_does_not_perform_io_after_budget_exhaustion() -> None:
    from shema_platform.adapters.intelligence.opencorporates import (
        OpenCorporatesConfiguration,
        OpenCorporatesProvider,
    )

    calls: list[dict[str, str]] = []

    def requester(url, params, timeout_seconds):
        calls.append(params)
        return 200, b'{"ignored":true}'

    provider = OpenCorporatesProvider(
        OpenCorporatesConfiguration(
            api_token="runtime-secret",
            timeout_seconds=1,
            max_requests_per_second=1000,
        ),
        requester=requester,
    )
    budget = ProviderCallBudget(
        ProviderBudget(max_calls=1, max_requests_per_second=1.0)
    )

    provider.check(call_budget=budget)
    with pytest.raises(ProviderBudgetExceeded):
        provider.check(call_budget=budget)

    assert len(calls) == 1
