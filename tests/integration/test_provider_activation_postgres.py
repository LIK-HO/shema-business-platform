from datetime import UTC, datetime
from pathlib import Path
import os

import psycopg
import pytest

from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.foundation.provider_activation import ProviderActivationState
from shema_platform.platform.provider_activation_postgres import (
    PostgresProviderActivationStateStore,
)

pytestmark = pytest.mark.integration

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    pytest.skip("DATABASE_URL is not configured", allow_module_level=True)

ROOT = Path(__file__).resolve().parents[2]


def apply_migrations(connection: psycopg.Connection) -> None:
    for name in ("0001_foundation.sql", "0013_provider_activation_state.sql"):
        for statement in (ROOT / "db/migrations" / name).read_text().split(";"):
            statement = statement.strip()
            if statement:
                connection.execute(statement)


def test_postgres_provider_rollback_rejects_stale_activation() -> None:
    provider_id = "provider:stale-rollback"
    first_at = datetime(2026, 9, 29, 10, 0, tzinfo=UTC)
    second_at = datetime(2026, 9, 29, 10, 0, 1, tzinfo=UTC)

    with psycopg.connect(DATABASE_URL) as setup:
        apply_migrations(setup)
        setup.execute(
            "delete from provider_activation_state where provider_id = %s",
            (provider_id,),
        )
        setup.commit()

    store = PostgresProviderActivationStateStore(
        lambda: psycopg.connect(DATABASE_URL)
    )
    store.activate(
        ProviderActivationState(
            provider_id=provider_id,
            enabled=True,
            configuration_version="cfg:v1",
            activation_version="activation:v1",
            activated_by="operator-a",
            activated_at=first_at,
        )
    )
    stale = store.get(provider_id)
    assert stale is not None

    store.rollback(
        provider_id=provider_id,
        rolled_back_by="operator-a",
        rolled_back_at=first_at,
        reason="controlled rollback",
        expected_activation_version="activation:v1",
        expected_activated_at=first_at,
    )
    store.activate(
        ProviderActivationState(
            provider_id=provider_id,
            enabled=True,
            configuration_version="cfg:v2",
            activation_version="activation:v2",
            activated_by="operator-b",
            activated_at=second_at,
        )
    )

    with pytest.raises(IntegrityViolation, match="compare-and-set"):
        store.rollback(
            provider_id=provider_id,
            rolled_back_by="stale-operator",
            rolled_back_at=second_at,
            reason="stale rollback",
            expected_activation_version=str(stale.activation_version),
            expected_activated_at=stale.activated_at,
        )

    current = store.get(provider_id)
    assert current is not None
    assert current.enabled is True
    assert current.activation_version == "activation:v2"
