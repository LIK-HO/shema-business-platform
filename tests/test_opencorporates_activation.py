import pytest

from shema_platform.adapters.intelligence.activation import (
    OpenCorporatesProviderFactory,
)
from shema_platform.foundation.configuration import ConfigurationSnapshot


def snapshot(
    *,
    enabled: bool,
    values: dict[str, object] | None = None,
) -> ConfigurationSnapshot:
    return ConfigurationSnapshot(
        version="p5-opencorporates-2026-09-23",
        environment="production",
        values=values or {},
        feature_flags={
            OpenCorporatesProviderFactory.FEATURE_FLAG: enabled,
        },
    )


def test_disabled_provider_does_not_activate() -> None:
    assert OpenCorporatesProviderFactory.from_snapshot(snapshot(enabled=False)) is None


def test_enabled_provider_requires_secret_configuration(monkeypatch) -> None:
    monkeypatch.delenv("OPENCORPORATES_API_TOKEN", raising=False)

    with pytest.raises(
        ValueError,
        match="requires OPENCORPORATES_API_TOKEN",
    ):
        OpenCorporatesProviderFactory.from_snapshot(snapshot(enabled=True))


def test_enabled_provider_reads_token_outside_snapshot(monkeypatch) -> None:
    monkeypatch.setenv("OPENCORPORATES_API_TOKEN", "runtime-secret")

    provider = OpenCorporatesProviderFactory.from_snapshot(
        snapshot(
            enabled=True,
            values={
                "opencorporates.api_version": "0.4",
                "opencorporates.timeout_seconds": 2,
                "opencorporates.cost_per_call": 0.1,
                "opencorporates.max_requests_per_second": 2,
                "opencorporates.coverage": ("company", "construction"),
                "opencorporates.confidence": 0.7,
            },
        )
    )

    assert provider is not None
    assert provider.capability.provider_id == "opencorporates"


def test_explicit_token_does_not_enter_configuration_snapshot() -> None:
    provider = OpenCorporatesProviderFactory.from_snapshot(
        snapshot(enabled=True),
        api_token="runtime-secret",
    )

    assert provider is not None


def test_invalid_snapshot_values_fail_closed() -> None:
    with pytest.raises(ValueError, match="timeout_seconds must be positive"):
        OpenCorporatesProviderFactory.from_snapshot(
            snapshot(
                enabled=True,
                values={"opencorporates.timeout_seconds": 0},
            ),
            api_token="runtime-secret",
        )
