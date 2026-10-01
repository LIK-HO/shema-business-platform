from datetime import UTC, datetime

import pytest

from shema_platform.foundation.provider_health import ProviderHealthRegistry


def test_disabled_provider_is_always_ready() -> None:
    registry = ProviderHealthRegistry()
    state = registry.register(
        "opencorporates",
        enabled=False,
        configured=False,
    )

    assert state.ready is True
    assert registry.ready() is True


def test_enabled_provider_requires_configuration_and_reachability() -> None:
    registry = ProviderHealthRegistry()
    registry.register(
        "opencorporates",
        enabled=True,
        configured=False,
    )

    assert registry.ready() is False


def test_last_known_failure_is_bounded_to_error_code() -> None:
    checked_at = datetime(2026, 9, 23, 17, 0, tzinfo=UTC)
    registry = ProviderHealthRegistry()
    registry.register(
        "opencorporates",
        enabled=True,
        configured=True,
    )

    state = registry.mark_unreachable(
        "opencorporates",
        error_code="HTTP_429",
        checked_at=checked_at,
    )

    assert state.reachable is False
    assert state.last_error_code == "HTTP_429"
    assert state.last_checked_at == checked_at

    registry.mark_reachable(
        "opencorporates",
        checked_at=checked_at,
    )

    recovered = registry.snapshot()[0]
    assert recovered.reachable is True
    assert recovered.last_error_code is None


def test_unregistered_provider_cannot_be_updated() -> None:
    registry = ProviderHealthRegistry()

    with pytest.raises(KeyError, match="health is not registered"):
        registry.mark_reachable("missing")
