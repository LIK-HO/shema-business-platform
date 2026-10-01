from __future__ import annotations

from datetime import datetime

from shema_platform.foundation.errors import IntegrityViolation
from shema_platform.foundation.provider_activation import (
    ProviderActivationState,
    ProviderActivationStateStore,
)


class PostgresProviderActivationStateStore(ProviderActivationStateStore):
    """PostgreSQL-backed provider kill-switch shared by all runtime replicas."""

    def __init__(self, connection_factory):
        self._connection_factory = connection_factory

    def get(self, provider_id: str) -> ProviderActivationState | None:
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                select
                    provider_id,
                    enabled,
                    configuration_version,
                    activation_version,
                    activated_by,
                    activated_at,
                    max_cost,
                    max_duration_seconds,
                    rollback_by,
                    rollback_at,
                    rollback_reason,
                    rollback_from_configuration_version
                from provider_activation_state
                where provider_id = %s
                """,
                (provider_id,),
            ).fetchone()
        return None if row is None else self._to_state(row)

    def activate(self, state: ProviderActivationState) -> None:
        if not state.enabled:
            raise ValueError("activation state must be enabled")
        with self._connection_factory() as connection:
            row = connection.execute(
                """
                insert into provider_activation_state (
                    provider_id,
                    enabled,
                    configuration_version,
                    activation_version,
                    activated_by,
                    activated_at,
                    max_cost,
                    max_duration_seconds,
                    rollback_by,
                    rollback_at,
                    rollback_reason,
                    rollback_from_configuration_version
                )
                values (%s, true, %s, %s, %s, %s, %s, %s, null, null, null, null)
                on conflict (provider_id) do update
                set enabled = true,
                    configuration_version = excluded.configuration_version,
                    activation_version = excluded.activation_version,
                    activated_by = excluded.activated_by,
                    activated_at = excluded.activated_at,
                    max_cost = excluded.max_cost,
                    max_duration_seconds = excluded.max_duration_seconds,
                    rollback_by = null,
                    rollback_at = null,
                    rollback_reason = null,
                    rollback_from_configuration_version = null,
                    updated_at = now()
                where provider_activation_state.enabled = false
                returning provider_id
                """,
                (
                    state.provider_id,
                    state.configuration_version,
                    state.activation_version,
                    state.activated_by,
                    state.activated_at,
                    state.max_cost,
                    state.max_duration_seconds,
                ),
            ).fetchone()
            if row is None:
                raise IntegrityViolation(
                    "provider activation already enabled on another runtime"
                )
            connection.commit()

    def rollback(
        self,
        *,
        provider_id: str,
        rolled_back_by: str,
        rolled_back_at: datetime,
        reason: str,
        expected_activation_version: str,
        expected_activated_at: datetime,
    ) -> None:
        with self._connection_factory() as connection:
            updated = connection.execute(
                """
                update provider_activation_state
                set enabled = false,
                    rollback_by = %s,
                    rollback_at = %s,
                    rollback_reason = %s,
                    rollback_from_configuration_version = configuration_version,
                    updated_at = now()
                where provider_id = %s
                  and enabled = true
                  and activation_version = %s
                  and activated_at = %s
                returning provider_id
                """,
                (
                    rolled_back_by,
                    rolled_back_at,
                    reason[:256],
                    provider_id,
                    expected_activation_version,
                    expected_activated_at,
                ),
            ).fetchone()
            if updated is None:
                raise IntegrityViolation(
                    "provider activation rollback lost its compare-and-set target"
                )
            connection.commit()

    @staticmethod
    def _to_state(row: tuple[object, ...]) -> ProviderActivationState:
        (
            provider_id,
            enabled,
            configuration_version,
            activation_version,
            activated_by,
            activated_at,
            max_cost,
            max_duration_seconds,
            rollback_by,
            rollback_at,
            rollback_reason,
            rollback_from_configuration_version,
        ) = row
        return ProviderActivationState(
            provider_id=str(provider_id),
            enabled=bool(enabled),
            configuration_version=(
                str(configuration_version)
                if configuration_version is not None
                else None
            ),
            activation_version=(
                str(activation_version)
                if activation_version is not None
                else None
            ),
            activated_by=(
                str(activated_by) if activated_by is not None else None
            ),
            activated_at=activated_at,
            max_cost=float(max_cost) if max_cost is not None else None,
            max_duration_seconds=(
                float(max_duration_seconds)
                if max_duration_seconds is not None
                else None
            ),
            rollback_by=(
                str(rollback_by) if rollback_by is not None else None
            ),
            rollback_at=rollback_at,
            rollback_reason=(
                str(rollback_reason)
                if rollback_reason is not None
                else None
            ),
            rollback_from_configuration_version=(
                str(rollback_from_configuration_version)
                if rollback_from_configuration_version is not None
                else None
            ),
        )
