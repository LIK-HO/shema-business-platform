from __future__ import annotations

from fastapi.testclient import TestClient

from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DADATA_PROVIDER_ID,
    DaDataActivationReadiness,
)
from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.experience.runtime_composition import (
    compose_counterparty_provider_runtime,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import Permission
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
    def __init__(self, records=None):
        self.identities = Identities(records=records)
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
                        Permission.INTELLIGENCE_PROVIDER_ROLLBACK,
                    }
                ),
            )
        raise AuthenticationRequired()


class OutcomeProvider:
    provider_id = DADATA_PROVIDER_ID

    def __init__(
        self,
        outcomes: list[object],
        *,
        canonical_name: str = 'ООО "Пример"',
    ) -> None:
        self._outcomes = list(outcomes)
        self.canonical_name = canonical_name
        self.calls = 0

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        self.calls += 1
        if self._outcomes:
            outcome = self._outcomes.pop(0)
            if isinstance(outcome, BaseException):
                raise outcome
        return CounterpartyProviderRecord(
            provider_id=DADATA_PROVIDER_ID,
            source_ref="https://fixture.example/dadata",
            canonical_name=self.canonical_name,
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


def request_body() -> dict:
    return {
        "identifierType": "INN",
        "identifier": "7707083893",
    }


def build(
    provider: OutcomeProvider,
    *,
    records=None,
    max_attempts: int = 3,
    delays: list[float] | None = None,
):
    state = UOW(records=records)
    assembly = compose_counterparty_provider_runtime(
        configuration=DaDataConfiguration(api_key="test-secret", enabled=True),
        readiness=ready(),
        telemetry=InMemoryTelemetrySink(),
        provider_factory=lambda _configuration: provider,
        unit_of_work_factory=lambda: state,
        max_attempts=max_attempts,
        backoff_seconds=0.25,
        sleeper=(delays.append if delays is not None else (lambda _: None)),
    )
    return assembly, state


def activate(client: TestClient) -> None:
    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer activate-token"},
        json={
            "reason": "negative outcome rehearsal",
            "operatorConfirmed": True,
            "activationVersion": "negative-runtime:v1",
        },
    )
    assert response.status_code == 200


def test_not_found_is_mapped_without_evidence_or_identity_mutation() -> None:
    provider = OutcomeProvider(
        [
            CounterpartyLookupProviderError(
                "NOT_FOUND",
                "fixture not found",
                retryable=False,
            )
        ]
    )
    assembly, state = build(provider, max_attempts=3)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))
    activate(client)

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"
    assert state.evidence.records == []
    assert state.audits.records == []
    assert state.identities.records == []
    assert provider.calls == 1


def test_rate_limit_retries_then_succeeds_once() -> None:
    delays: list[float] = []
    provider = OutcomeProvider(
        [
            CounterpartyLookupProviderError(
                "PROVIDER_RATE_LIMIT",
                "fixture rate limit",
                retryable=True,
            ),
        ]
    )
    assembly, state = build(provider, delays=delays)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))
    activate(client)

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={
            "Authorization": "Bearer lookup-token",
            "X-Correlation-Id": "corr-rate-retry",
        },
        json=request_body(),
    )

    assert response.status_code == 200
    assert provider.calls == 2
    assert delays == [0.25]
    assert len(state.evidence.records) == 4
    assert len(state.audits.records) == 1
    assert state.audits.records[0].correlation_id == "corr-rate-retry"


def test_rate_limit_exhaustion_is_429_and_writes_no_evidence() -> None:
    delays: list[float] = []
    error = CounterpartyLookupProviderError(
        "PROVIDER_RATE_LIMIT",
        "fixture rate limit",
        retryable=True,
    )
    provider = OutcomeProvider([error, error, error])
    assembly, state = build(provider, delays=delays)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))
    activate(client)

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )

    assert response.status_code == 429
    assert response.json()["code"] == "provider_rate_limit"
    assert provider.calls == 3
    assert delays == [0.25, 0.5]
    assert state.evidence.records == []
    assert state.audits.records == []


def test_provider_5xx_error_is_bounded_and_maps_to_502_without_partial_state() -> None:
    delays: list[float] = []
    error = CounterpartyLookupProviderError(
        "PROVIDER_INTERNAL_ERROR",
        "fixture provider failure",
        retryable=True,
    )
    provider = OutcomeProvider([error, error, error])
    assembly, state = build(provider, delays=delays)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))
    activate(client)

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )

    assert response.status_code == 502
    assert response.json()["code"] == "provider_internal_error"
    assert provider.calls == 3
    assert delays == [0.25, 0.5]
    assert state.evidence.records == []
    assert state.audits.records == []


def test_transport_failure_retries_once_then_succeeds_without_duplicate_evidence() -> None:
    delays: list[float] = []
    provider = OutcomeProvider([ConnectionError("fixture connection reset")])
    assembly, state = build(provider, delays=delays)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))
    activate(client)

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={
            "Authorization": "Bearer lookup-token",
            "X-Correlation-Id": "corr-transport-recovery",
        },
        json=request_body(),
    )

    assert response.status_code == 200
    assert provider.calls == 2
    assert delays == [0.25]
    assert len(state.evidence.records) == 4
    assert len(state.audits.records) == 1
    assert state.audits.records[0].correlation_id == "corr-transport-recovery"


def test_secondary_provider_contradiction_is_quarantined_without_identity_mutation() -> None:
    existing = Identity(
        identity_id="identity-1",
        canonical_name='ООО "Исходное"',
        state=IdentityState.IDENTIFIED,
        tax_id="7707083893",
        registration_id="1027700132195",
    )
    provider = OutcomeProvider([], canonical_name='ООО "Наблюдаемое"')
    assembly, state = build(provider, records=[existing], max_attempts=1)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))
    activate(client)

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={
            "Authorization": "Bearer lookup-token",
            "X-Correlation-Id": "corr-contradiction",
        },
        json=request_body(),
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["identityRef"] == "identity-1"
    assert payload["quarantined"] is True
    assert payload["contradictions"][0]["field"] == "canonical_name"
    assert len(state.evidence.records) == 4
    assert len(state.quarantine.records) == 1
    assert len(state.audits.records) == 1
    assert state.audits.records[0].outcome == "quarantined"
    assert state.audits.records[0].correlation_id == "corr-contradiction"
    assert state.identities.records == [existing]


def test_provider_errors_never_activate_network_fallback() -> None:
    provider = OutcomeProvider(
        [
            CounterpartyLookupProviderError(
                "PROVIDER_INTERNAL_ERROR",
                "fixture provider failure",
                retryable=False,
            )
        ]
    )
    assembly, _ = build(provider, max_attempts=1)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))

    activate(client)
    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )

    assert response.status_code == 502
    assert provider.calls == 1


def test_rollback_disables_binding_and_subsequent_lookup_fails_closed() -> None:
    provider = OutcomeProvider([])
    assembly, state = build(provider, max_attempts=1)
    client = TestClient(assembly.create_http_app(authenticator=LookupAuthenticator()))

    activate(client)

    rollback = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/rollback",
        headers={
            "Authorization": "Bearer activate-token",
            "X-Correlation-Id": "corr-rollback",
        },
        json={
            "reason": "negative runtime rehearsal rollback",
            "operatorAuthorized": True,
        },
    )

    assert rollback.status_code == 200
    assert rollback.json()["enabled"] is False

    response = client.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/lookup",
        headers={"Authorization": "Bearer lookup-token"},
        json=request_body(),
    )

    assert response.status_code == 409
    assert response.json()["code"] == "provider_activation_blocked"
    assert provider.calls == 0
    assert state.evidence.records == []
    assert state.audits.records == []
