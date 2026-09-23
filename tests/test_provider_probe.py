from dataclasses import dataclass

import pytest

from shema_platform.adapters.intelligence.opencorporates import (
    OpenCorporatesConfiguration,
    OpenCorporatesProvider,
)
from shema_platform.foundation.provider_health import ProviderHealthRegistry
from shema_platform.foundation.provider_probe import (
    ProbeResult,
    ProviderProbeRunner,
)
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


def configuration() -> OpenCorporatesConfiguration:
    return OpenCorporatesConfiguration(
        api_token="runtime-secret",
        timeout_seconds=1,
        max_requests_per_second=1000,
    )


@dataclass
class ProbeRequester:
    status: int
    calls: list[dict[str, str]]

    def __call__(
        self,
        url: str,
        params: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        self.calls.append(params)
        return self.status, b'{"ignored":true}'


def test_opencorporates_probe_does_not_parse_or_return_provider_payload() -> None:
    requester = ProbeRequester(status=200, calls=[])
    provider = OpenCorporatesProvider(
        configuration(),
        requester=requester,
    )

    result = provider.check()

    assert result == ProbeResult(reachable=True, error_code=None)
    assert requester.calls == [
        {
            "api_token": "runtime-secret",
            "q": "__shema_provider_readiness_probe__",
            "per_page": "1",
            "order": "score",
        }
    ]


@pytest.mark.parametrize(
    ("status", "error_code"),
    [
        (401, "HTTP_401"),
        (429, "HTTP_429"),
        (500, "HTTP_500"),
    ],
)
def test_opencorporates_probe_maps_http_failures(
    status: int,
    error_code: str,
) -> None:
    requester = ProbeRequester(status=status, calls=[])
    provider = OpenCorporatesProvider(
        configuration(),
        requester=requester,
    )

    result = provider.check()

    assert result.reachable is False
    assert result.error_code == error_code


class FailingRequester:
    def __call__(
        self,
        url: str,
        params: dict[str, str],
        timeout_seconds: float,
    ) -> tuple[int, bytes]:
        raise ConnectionError("transport unavailable")


def test_opencorporates_probe_maps_transport_failure() -> None:
    provider = OpenCorporatesProvider(
        configuration(),
        requester=FailingRequester(),
    )

    result = provider.check()

    assert result == ProbeResult(
        reachable=False,
        error_code="CONNECTION_ERROR",
    )


def test_probe_runner_updates_health_and_emits_safe_telemetry() -> None:
    registry = ProviderHealthRegistry()
    registry.register(
        "opencorporates",
        enabled=True,
        configured=True,
    )
    telemetry = InMemoryTelemetrySink()
    runner = ProviderProbeRunner(registry, telemetry)
    requester = ProbeRequester(status=200, calls=[])
    provider = OpenCorporatesProvider(
        configuration(),
        requester=requester,
    )

    state = runner.run(
        provider,
        correlation_id="probe-corr-1",
    )

    assert state.ready is True
    events = telemetry.all()
    assert events[-1].name == "provider.probe.completed"
    assert events[-1].correlation_id == "probe-corr-1"
    assert events[-1].attributes["provider"] == "opencorporates"
    assert "runtime-secret" not in str(events[-1].attributes)


def test_probe_runner_fails_closed_and_does_not_leak_error_payload() -> None:
    registry = ProviderHealthRegistry()
    registry.register(
        "opencorporates",
        enabled=True,
        configured=True,
    )
    telemetry = InMemoryTelemetrySink()
    runner = ProviderProbeRunner(registry, telemetry)

    class ExplodingProbe:
        provider_id = "opencorporates"

        def check(self) -> ProbeResult:
            raise RuntimeError("secret-provider-payload")

    state = runner.run(
        ExplodingProbe(),
        correlation_id="probe-corr-2",
    )

    assert state.ready is False
    assert state.last_error_code == "PROBE_EXCEPTION"
    assert "secret-provider-payload" not in str(state)
    event = telemetry.all()[-1]
    assert event.name == "provider.probe.failed"
    assert event.attributes["error_code"] == "PROBE_EXCEPTION"
    assert "secret-provider-payload" not in str(event.attributes)


def test_disabled_provider_probe_is_not_called() -> None:
    registry = ProviderHealthRegistry()
    state = registry.register(
        "opencorporates",
        enabled=False,
        configured=False,
    )
    telemetry = InMemoryTelemetrySink()
    runner = ProviderProbeRunner(registry, telemetry)

    class MustNotRun:
        provider_id = "opencorporates"

        def check(self) -> ProbeResult:
            raise AssertionError("disabled probe must not run")

    result = runner.run(MustNotRun())

    assert result == state
    assert telemetry.all() == ()
