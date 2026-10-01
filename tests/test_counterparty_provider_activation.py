from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime

import pytest

from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DADATA_PROVIDER_ID,
    DaDataActivationError,
    DaDataActivationReadiness,
    DaDataControlledActivationGate,
)
from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupIdentifierType,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.application.counterparty_provider_activation import (
    CounterpartyProviderActivationCommand,
    CounterpartyProviderActivationService,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.errors import AuthorizationError
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


def readiness() -> DaDataActivationReadiness:
    return DaDataActivationReadiness(
        source_registry_entry=True,
        authoritative_provider_contract_evidence=True,
        provider_neutral_counterparty_lookup_port=True,
        deterministic_positive_fixture=True,
        deterministic_negative_fixture_matrix=True,
        bounded_retry_policy=True,
        application_timeout_policy=True,
        credential_boundary=True,
        redacted_observability=True,
        kill_switch=True,
        rollback_without_schema_change=True,
        full_release_ci=True,
    )


class FakeProvider:
    provider_id = DADATA_PROVIDER_ID

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        return CounterpartyProviderRecord(
            provider_id=DADATA_PROVIDER_ID,
            source_ref="https://dadata.ru/api/find-party/",
            canonical_name="ООО ТЕСТ",
            tax_id=query.identifier,
            registration_id=None,
            legal_status="ACTIVE",
            observed_at_ms=None,
            provider_type="LEGAL",
        )


def gate_and_service():
    telemetry = InMemoryTelemetrySink()
    gate = DaDataControlledActivationGate(
        telemetry=telemetry,
        provider_factory=lambda _configuration: FakeProvider(),
        now=lambda: datetime(2026, 9, 27, 12, 0, tzinfo=UTC),
    )
    configuration = DaDataConfiguration(
        api_key="test-secret",
        enabled=True,
    )
    service = CounterpartyProviderActivationService(
        gate=gate,
        configuration=configuration,
        readiness=readiness(),
    )
    return telemetry, gate, service


def request(*, authorized: bool = True) -> CounterpartyProviderActivationCommand:
    return CounterpartyProviderActivationCommand(
        provider_id=DADATA_PROVIDER_ID,
        actor_id="operator-1",
        reason="controlled verification",
        operator_authorized=authorized,
        activation_version="activation:test-v1",
        correlation_id="corr-1",
    )


def test_activation_is_fail_closed_without_explicit_authorization() -> None:
    _, gate, service = gate_and_service()

    with pytest.raises(AuthorizationError, match="explicit operator authorization"):
        service.activate(
            request(authorized=False),
            permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ACTIVATE}),
        )
    assert gate.state.enabled is False


def test_activation_requires_authorized_permission() -> None:
    _, gate, service = gate_and_service()

    with pytest.raises(AuthorizationError, match="permission denied"):
        service.activate(
            request(),
            permissions=frozenset(),
        )
    assert gate.state.enabled is False


def test_activation_binds_provider_and_redacts_telemetry() -> None:
    telemetry, gate, service = gate_and_service()

    response = service.activate(
        request(),
        permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ACTIVATE}),
    )
    assert response.enabled is True
    record = service.provider().lookup(
        CounterpartyLookupQuery(
            identifier_type=CounterpartyLookupIdentifierType.INN,
            identifier="7707083893",
        )
    )
    assert record.canonical_name == "ООО ТЕСТ"
    events = telemetry.all()
    assert [event.name for event in events] == ["intelligence.provider.activated"]
    assert "test-secret" not in str(events[0].attributes)
    assert "reason" not in str(events[0].attributes)


def test_activation_requires_all_readiness_gates() -> None:
    telemetry = InMemoryTelemetrySink()
    gate = DaDataControlledActivationGate(
        telemetry=telemetry,
        provider_factory=lambda _configuration: FakeProvider(),
    )
    service = CounterpartyProviderActivationService(
        gate=gate,
        configuration=DaDataConfiguration(api_key="test-secret", enabled=True),
        readiness=replace(readiness(), full_release_ci=False),
    )

    with pytest.raises(DaDataActivationError, match="full_release_ci"):
        service.activate(
            request(),
            permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ACTIVATE}),
        )
    assert gate.state.enabled is False


def test_configuration_kill_switch_blocks_activation() -> None:
    _, gate, service = gate_and_service()
    disabled = CounterpartyProviderActivationService(
        gate=gate,
        configuration=DaDataConfiguration(api_key="", enabled=False),
        readiness=readiness(),
    )
    with pytest.raises(DaDataActivationError, match="disabled by configuration"):
        disabled.activate(
            request(),
            permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ACTIVATE}),
        )
    assert gate.state.enabled is False


def test_rollback_blocks_future_execution_and_retains_safe_history() -> None:
    telemetry, gate, service = gate_and_service()
    service.activate(
        request(),
        permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ACTIVATE}),
    )

    rolled = service.rollback(
        provider_id=DADATA_PROVIDER_ID,
        actor_id="operator-2",
        reason="kill switch drill",
        operator_authorized=True,
        correlation_id="corr-4",
        permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ROLLBACK}),
    )
    assert rolled.enabled is False
    assert rolled.rollback_by == "operator-2"
    assert rolled.rollback_reason == "kill switch drill"
    with pytest.raises(DaDataActivationError, match="not active"):
        service.provider()
    assert gate.state.activation_version == "activation:test-v1"
    assert gate.state.rollback_by == "operator-2"
    assert "test-secret" not in str(gate.state)
    assert [event.name for event in telemetry.all()] == [
        "intelligence.provider.activated",
        "intelligence.provider.rolled_back",
    ]
