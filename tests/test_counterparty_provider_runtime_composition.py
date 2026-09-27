from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DADATA_PROVIDER_ID,
    DaDataActivationReadiness,
    DaDataActivationError,
)
from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupIdentifierType,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.experience.runtime_composition import (
    CounterpartyProviderRuntimeAssembly,
    compose_counterparty_provider_runtime,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


class ActivationAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer activate-token":
            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ACTIVATE}),
            )
        if authorization == "Bearer rollback-token":
            return AuthenticatedActor(
                "operator-2",
                trust_level=2,
                permissions=frozenset({Permission.INTELLIGENCE_PROVIDER_ROLLBACK}),
            )
        raise AuthenticationRequired()


class FakeProvider:
    provider_id = DADATA_PROVIDER_ID

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        return CounterpartyProviderRecord(
            provider_id=DADATA_PROVIDER_ID,
            source_ref="fixture:dadata",
            canonical_name="ООО ТЕСТ",
            tax_id=query.identifier,
            registration_id=None,
            legal_status="ACTIVE",
            observed_at_ms=1_758_960_000_000,
            provider_type="LEGAL",
        )


def ready_witness() -> DaDataActivationReadiness:
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


def blocked_witness() -> DaDataActivationReadiness:
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
        full_release_ci=False,
    )


def runtime(*, readiness: DaDataActivationReadiness) -> CounterpartyProviderRuntimeAssembly:
    return compose_counterparty_provider_runtime(
        configuration=DaDataConfiguration(
            api_key="test-secret",
            enabled=True,
        ),
        readiness=readiness,
        telemetry=InMemoryTelemetrySink(),
        provider_factory=lambda _configuration: FakeProvider(),
    )


def test_runtime_composition_is_explicit_and_does_not_activate_provider() -> None:
    assembly = runtime(readiness=ready_witness())

    assert isinstance(assembly, CounterpartyProviderRuntimeAssembly)
    with pytest.raises(DaDataActivationError, match="not active"):
        assembly.provider()


def test_runtime_composition_does_not_construct_provider_before_activation() -> None:
    constructed = False

    def factory(_configuration):
        nonlocal constructed
        constructed = True
        return FakeProvider()

    compose_counterparty_provider_runtime(
        configuration=DaDataConfiguration(api_key="test-secret", enabled=True),
        readiness=ready_witness(),
        telemetry=InMemoryTelemetrySink(),
        provider_factory=factory,
    )

    assert constructed is False


def test_runtime_http_activation_fails_closed_on_incomplete_readiness() -> None:
    assembly = runtime(readiness=blocked_witness())
    client = TestClient(
        assembly.create_http_app(authenticator=ActivationAuthenticator())
    )

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer activate-token"},
        json={
            "reason": "rehearsal",
            "operatorAuthorized": True,
            "activationVersion": "runtime-rehearsal:v1",
        },
    )

    assert response.status_code == 409
    assert response.json()["code"] == "provider_activation_blocked"


def test_runtime_http_activation_uses_fake_provider_and_rollback_is_fail_closed() -> None:
    assembly = runtime(readiness=ready_witness())
    client = TestClient(
        assembly.create_http_app(authenticator=ActivationAuthenticator())
    )

    activated = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={
            "Authorization": "Bearer activate-token",
            "X-Correlation-Id": "corr-runtime-activate",
        },
        json={
            "reason": "runtime rehearsal",
            "operatorAuthorized": True,
            "activationVersion": "runtime-rehearsal:v1",
        },
    )

    assert activated.status_code == 200
    assert activated.headers["X-Correlation-Id"] == "corr-runtime-activate"
    assert activated.json()["enabled"] is True

    record = assembly.provider().lookup(
        CounterpartyLookupQuery(
            identifier_type=CounterpartyLookupIdentifierType.INN,
            identifier="7707083893",
        )
    )
    assert record.canonical_name == "ООО ТЕСТ"

    rolled_back = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/rollback",
        headers={
            "Authorization": "Bearer rollback-token",
            "X-Correlation-Id": "corr-runtime-rollback",
        },
        json={
            "reason": "rehearsal rollback",
            "operatorAuthorized": True,
        },
    )

    assert rolled_back.status_code == 200
    assert rolled_back.json()["enabled"] is False
    with pytest.raises(DaDataActivationError, match="not active"):
        assembly.provider()


def test_runtime_composition_keeps_authentication_boundary() -> None:
    assembly = runtime(readiness=ready_witness())
    client = TestClient(assembly.create_http_app(authenticator=ActivationAuthenticator()))

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        json={
            "reason": "unauthenticated",
            "operatorAuthorized": True,
            "activationVersion": "runtime-rehearsal:v1",
        },
    )

    assert response.status_code == 401
