from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import uuid4

from shema_platform.foundation.provider_health import (
    ProviderHealth,
    ProviderHealthRegistry,
)
from shema_platform.foundation.telemetry import (
    TelemetrySink,
    build_event,
)


@dataclass(frozen=True, slots=True)
class ProbeResult:
    reachable: bool
    error_code: str | None = None


class ProviderReadinessProbe(Protocol):
    provider_id: str

    def check(self) -> ProbeResult: ...


class ProviderProbeRunner:
    """Run explicit provider probes and update only operational health state."""

    def __init__(
        self,
        registry: ProviderHealthRegistry,
        telemetry: TelemetrySink,
    ) -> None:
        self._registry = registry
        self._telemetry = telemetry

    def run(
        self,
        probe: ProviderReadinessProbe,
        *,
        correlation_id: str | None = None,
    ) -> ProviderHealth:
        state = next(
            (
                item
                for item in self._registry.snapshot()
                if item.provider_id == probe.provider_id
            ),
            None,
        )
        if state is None:
            raise KeyError(
                f"provider health is not registered: {probe.provider_id}"
            )

        correlation = correlation_id or (
            f"provider-probe:{probe.provider_id}:{uuid4()}"
        )

        if not state.enabled:
            return state

        try:
            result = probe.check()
        except Exception:
            result = ProbeResult(
                reachable=False,
                error_code="PROBE_EXCEPTION",
            )

        if result.reachable:
            updated = self._registry.mark_reachable(probe.provider_id)
            self._telemetry.emit(
                build_event(
                    name="provider.probe.completed",
                    correlation_id=correlation,
                    attributes={
                        "component": "provider",
                        "operation": "readiness_probe",
                        "provider": probe.provider_id,
                        "status": 200,
                    },
                )
            )
            return updated

        error_code = (result.error_code or "PROBE_FAILED")[:128]
        updated = self._registry.mark_unreachable(
            probe.provider_id,
            error_code=error_code,
        )
        self._telemetry.emit(
            build_event(
                name="provider.probe.failed",
                correlation_id=correlation,
                attributes={
                    "component": "provider",
                    "operation": "readiness_probe",
                    "provider": probe.provider_id,
                    "status": 503,
                    "error_code": error_code,
                },
            )
        )
        return updated
