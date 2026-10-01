import json
from pathlib import Path

from fastapi.testclient import TestClient

from shema_platform.experience.api import create_app
from shema_platform.foundation.recovery import RetryPolicy

ROOT = Path(__file__).parents[1]


def test_capacity_overload_contract_is_bounded() -> None:
    contract = json.loads(
        (ROOT / "architecture" / "capacity_overload_contract.json").read_text(
            encoding="utf-8"
        )
    )
    assert contract["version"] == "1.5-capacity-overload-baseline"
    assert contract["policy"]["no_new_kernel_semantics"] is True
    assert (
        contract["controls"]["concurrent_critical_commands"]["baseline_concurrency"]
        == 8
    )
    assert contract["controls"]["retry_storm"]["max_attempts"] == 5
    assert contract["controls"]["retry_storm"]["maximum_delay_seconds"] == 60
    assert contract["controls"]["queue_backlog"]["outbox_default_batch_limit"] == 100
    assert contract["controls"]["rate_limiting"]["status"] == "outside-frozen-core"


def test_retry_policy_bounds_retry_storms() -> None:
    policy = RetryPolicy(
        max_attempts=5,
        initial_delay_seconds=1,
        max_delay_seconds=60,
    )

    assert policy.is_retryable(1) is True
    assert policy.is_retryable(4) is True
    assert policy.is_retryable(5) is False
    assert policy.delay_for(1) == 1
    assert policy.delay_for(5) == 16
    assert policy.delay_for(10) == 60


def test_api_degrades_to_503_when_application_is_unavailable() -> None:
    client = TestClient(create_app(None, enable_docs=True))
    response = client.get("/v1/diagnostics")

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"
