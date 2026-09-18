import pytest
from uuid import UUID

from shema_platform.foundation.configuration import (
    ConfigurationRegistry,
    ConfigurationSnapshot,
)
from shema_platform.foundation.correlation import CorrelationContext
from shema_platform.foundation.diagnostics import (
    DiagnosticResult,
    DiagnosticStatus,
    Diagnostics,
)


def test_configuration_snapshot_is_immutable_by_input_mutation() -> None:
    values = {"timeout_seconds": 10}
    flags = {"search.enabled": True}
    snapshot = ConfigurationSnapshot("cfg-1", "test", values, flags)

    values["timeout_seconds"] = 99
    flags["search.enabled"] = False

    assert snapshot.values["timeout_seconds"] == 10
    assert snapshot.feature_flags["search.enabled"] is True


def test_configuration_registry_rejects_version_collision() -> None:
    registry = ConfigurationRegistry()
    registry.register(ConfigurationSnapshot("cfg-1", "test", {}, {}))

    with pytest.raises(ValueError, match="version collision"):
        registry.register(
            ConfigurationSnapshot("cfg-1", "test", {"changed": True}, {})
        )


def test_configuration_activation_is_explicit() -> None:
    registry = ConfigurationRegistry()
    registry.register(ConfigurationSnapshot("cfg-1", "test", {}, {}))

    with pytest.raises(RuntimeError, match="no active configuration"):
        registry.active()

    active = registry.activate("cfg-1")
    assert active.version == "cfg-1"
    assert registry.active() is active


def test_correlation_context_has_uuid_correlation_id() -> None:
    context = CorrelationContext.new()
    assert isinstance(context.correlation_id, UUID)
    assert context.request_id is None


def test_diagnostics_detect_mismatched_check_id() -> None:
    diagnostics = Diagnostics()

    with pytest.raises(ValueError, match="mismatched check_id"):
        diagnostics.run(
            {
                "health.database": lambda: DiagnosticResult(
                    "health.cache",
                    DiagnosticStatus.PASS,
                    "ok",
                )
            }
        )


def test_diagnostics_health_is_fail_closed_but_warn_tolerant() -> None:
    diagnostics = Diagnostics()
    results = (
        DiagnosticResult("database", DiagnosticStatus.PASS, "ok"),
        DiagnosticResult("provider", DiagnosticStatus.WARN, "degraded"),
    )

    assert diagnostics.healthy(results)
    assert not diagnostics.healthy(
        results
        + (DiagnosticResult("queue", DiagnosticStatus.FAIL, "unavailable"),)
    )
