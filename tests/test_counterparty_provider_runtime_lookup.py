from __future__ import annotations

from fastapi.testclient import TestClient

from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DADATA_PROVIDER_ID,
    DaDataActivationReadiness,
)
from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.experience.runtime_composition import (
    compose_counterparty_provider_runtime,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.provider_activation import (
    InMemoryProviderActivationStateStore,
)
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


class Identities:
    def __init__(self, records=None):
        self.records = list(records or [])

    def find_by_tax_id(self, tax_id: str):
        return next((item for item in self.records if item.tax_id == tax_id), None)


class Evidence:
    def __init__(self):
        self.records = []

    def add(self, value):
        self.records.append(value)


class Quarantine:
    def __init__(self):
        self.records = []

    def add(self, **value):
        self.records.append(value)


class Audits:
    def __init__(self):
        self.records = []

    def append(self, value):
        self.records.append(value)


class UOW:
    def __init__(self):
        self.identities = Identities()
        self.evidence = Evidence()
        self.quarantine = Quarantine()
        self.audits = Audits()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False


class LookupAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization in {"Bearer activate-token", "Bearer lookup-token"}:
            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset(
                    {
                        Permission.INTELLIGENCE_PROVIDER_ACTIVATE,
                        Permission.INTELLIGENCE_PROVIDER_LOOKUP,
                    }
                ),
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
            source_ref="https://fixture.example/dadata",
            canonical_name='ООО "Пример"',
            tax_id=query.identifier,
            registration_id="1027700132195",
            legal_status="ACTIVE",
            observed_at_ms=1771891200000,
        )


def ready() -> DaDataActivationReadiness:
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


def build():
    state = UOW()
    assembly = compose_counterparty_provider_runtime(
        configuration=DaDataConfiguration(api_key="test-secret", enabled=True),
        readiness=ready(),
        telemetry=InMemoryTelemetrySink(),
        activation_state_store=InMemoryProviderActivationStateStore(),
        provider_factory=lambda _configuration: FakeProvider(),
        unit_of_work_factory=lambda: state,
        max_attempts=1,
        sleeper=lambda _: None,
    )
    return assembly, state


def request_body() -> dict:
    return {
        "identifierType": "INN",
        "identifier": "7707083893",
    }


def test_lookup_requires_active_provider_binding() -> None:
    assembly, _ = build()
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "provider_activation_blocked"


def test_lookup_runs_through_runtime_to_evidence_and_audit_then_rollback_blocks_future_lookup(
) -> None:
    assembly, state = build()
    client = TestClient(
        assembly.create_http_app(authenticator=LookupAuthenticator())
    )

    activated = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer activate-token"},
        json={
            "reason": "lookup vertical slice",
            "operatorConfirmed": True,
            "activationVersion": "lookup-runtime:v1",
        },
    )
    assert activated.status_code == 200

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={
            "Authorization": "Bearer lookup-token",
            "X-Correlation-Id": "corr-lookup-e2e",
        },
        json=request_body(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["providerId"] == DADATA_PROVIDER_ID
    assert payload["canonicalName"] == 'ООО "Пример"'
    assert payload["identityRef"] is None
    assert payload["quarantined"] is False
    assert len(payload["evidenceIds"]) == 4
    assert payload["correlationId"] != "corr-lookup-e2e"
    assert len(state.evidence.records) == 4
    assert len(state.audits.records) == 1
    assert state.audits.records[0].correlation_id == payload["correlationId"]
    assert state.identities.records == []

    rolled_back = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/rollback",
        headers={"Authorization": "Bearer rollback-token"},
        json={
            "reason": "lookup e2e rollback",
            "operatorConfirmed": True,
        },
    )
    assert rolled_back.status_code == 200

    blocked = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )
    assert blocked.status_code == 409
    assert blocked.json()["code"] == "provider_activation_blocked"


def test_lookup_permission_is_required() -> None:
    assembly, _ = build()
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))

    activated = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer activate-token"},
        json={
            "reason": "permission test",
            "operatorConfirmed": True,
            "activationVersion": "lookup-runtime:v1",
        },
    )
    assert activated.status_code == 200

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer rollback-token"},
        json=request_body(),
    )

    assert response.status_code == 403
