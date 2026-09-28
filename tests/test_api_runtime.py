from fastapi.testclient import TestClient

from shema_platform.adapters.intelligence.dadata import DaDataConfiguration
from shema_platform.adapters.intelligence.dadata_activation import (
    DADATA_PROVIDER_ID,
    DaDataActivationReadiness,
    DaDataControlledActivationGate,
)
from shema_platform.application.counterparty_check import (
    CounterpartyCheckResult,
    CounterpartyContradiction,
    FreshnessState,
)
from shema_platform.application.counterparty_provider_activation import (
    CounterpartyProviderActivationService,
)
from shema_platform.experience.api import (
    APIApplication,
    RequestContext,
    create_app,
)
from shema_platform.experience.api_models import (
    AIRunRequest,
    AIRunResponse,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommunicationResult,
    DiagnosticCheck,
    DiagnosticsResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    EconomicResponse,
    OrderCreateRequest,
    OrderResponse,
    ResearchRequest,
    ResearchResponse,
    SearchRequest,
    SearchResponse,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import Permission
from shema_platform.foundation.errors import QuarantineRequired
from shema_platform.foundation.telemetry import InMemoryTelemetrySink


class RejectingAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        raise AuthenticationRequired()


class FakeAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer test-token":
            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset(Permission),
            )
        raise AuthenticationRequired()


class PermissionedAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer permissioned-token":
            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset({Permission.ORDER_CREATE}),
            )
        raise AuthenticationRequired()


class ProviderActivationAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer provider-token":
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


class FakeApplication(APIApplication):
    def run_ai(self, request: AIRunRequest, context: RequestContext) -> AIRunResponse:
        assert context.actor_id == "operator-1"
        assert context.trust_level == 2
        assert request.resource_ref == "identity-1"
        return AIRunResponse(
            runId="run-1",
            taskId="task-1",
            providerId="yandexgpt",
            model="yandexgpt",
            modelVersion="latest",
            promptVersion=request.prompt_version,
            inputRefs=request.input_refs,
            evidenceRefs=request.evidence_refs,
            output="bounded output",
            tokens=15,
            cost=0.01,
            durationSeconds=0.2,
            correlationId=context.correlation_id,
        )

    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse:
        assert context.actor_id == "operator-1"
        assert context.trust_level == 2
        assert context.idempotency_key is None
        return SearchResponse(results=[], correlationId=context.correlation_id)

    def discovery(self, request: DiscoveryRequest, context: RequestContext) -> DiscoveryResponse:
        return DiscoveryResponse(
            candidateRef=request.candidate_ref,
            qualification="review",
            reasons=["test"],
        )

    def research(self, request: ResearchRequest, context: RequestContext) -> ResearchResponse:
        return ResearchResponse(subjectRef=request.subject_ref, evidence=[])

    def create_commercial_action(
        self,
        request: CommercialActionCreateRequest,
        context: RequestContext,
    ) -> CommercialActionResponse:
        return CommercialActionResponse(
            actionId="action-1",
            identityId=request.identity_id,
            contactRef=request.contact_ref,
            channel=request.channel,
            status="ready",
        )

    def send_commercial_action(
        self,
        action_id: str,
        request,
        context: RequestContext,
    ) -> CommunicationResult:
        return CommunicationResult(
            actionId=action_id,
            channel="max",
            externalMessageId="message-1",
            accepted=True,
        )

    def create_order(
        self,
        request: OrderCreateRequest,
        context: RequestContext,
    ) -> OrderResponse:
        return OrderResponse(
            orderId="order-1",
            identityId="identity-1",
            sourceActionId=request.action_id,
            status="draft",
            lines=request.lines,
        )

    def get_order(self, order_id: str, context: RequestContext) -> OrderResponse:
        raise KeyError(order_id)

    def get_economics(self, entity_ref: str, context: RequestContext) -> EconomicResponse:
        return EconomicResponse(entityRef=entity_ref, entries=[])

    def get_diagnostics(self, context: RequestContext) -> DiagnosticsResponse:
        return DiagnosticsResponse(
            healthy=True,
            checks=[DiagnosticCheck(checkId="api", status="pass", message="ok")],
        )


class FakeAuthoritativeLookup:
    def lookup(self, *, identifier_type, identifier):
        from datetime import UTC, datetime

        from shema_platform.application.counterparty_check import (
            CounterpartyObservation,
            SourceReliability,
        )

        return CounterpartyObservation(
            identifier_type=identifier_type,
            identifier=identifier,
            canonical_name='ООО "New Name"',
            tax_id=identifier,
            registration_id="1027700132195",
            legal_status="active",
            source_ref="https://pb.nalog.ru/server-verified",
            source_reliability=SourceReliability.AUTHORITATIVE,
            claim_confidence=0.99,
            observed_at=datetime(2026, 9, 26, 10, tzinfo=UTC),
            expires_at=datetime(2026, 10, 3, 10, tzinfo=UTC),
        )


class FakeCounterpartyChecker:
    def __init__(self):
        self.calls = []

    def check(self, observation, *, actor_id, correlation_id, now=None):
        self.calls.append((observation, actor_id, correlation_id))
        return CounterpartyCheckResult(
            subject_ref="identity-1",
            identity=None,
            freshness=FreshnessState.FRESH,
            evidence_ids=("evidence-1",),
            contradictions=(
                CounterpartyContradiction(
                    field="canonical_name",
                    existing_value="Old Name",
                    observed_value="New Name",
                ),
            ),
            quarantined=True,
            operator_brief="review required",
        )


class QuarantineApplication(FakeApplication):
    def research(self, request: ResearchRequest, context: RequestContext) -> ResearchResponse:
        raise QuarantineRequired("review required")


def client(application: APIApplication | None = None) -> TestClient:
    return TestClient(
        create_app(
            application,
            FakeAuthenticator() if application is not None else None,
        )
    )


def test_runtime_api_propagates_verified_permissions() -> None:
    captured = {}

    class CapturingApplication(FakeApplication):
        def search(self, request, context):
            captured["permissions"] = context.permissions
            return super().search(request, context)

    response = TestClient(
        create_app(CapturingApplication(), PermissionedAuthenticator())
    ).post(
        "/v1/search",
        headers={"Authorization": "Bearer permissioned-token"},
        json={"region": "Moscow", "industries": ["logistics"]},
    )

    assert response.status_code == 200
    assert captured["permissions"] == frozenset({Permission.ORDER_CREATE})


def test_runtime_api_emits_redacted_telemetry() -> None:
    telemetry_sink = InMemoryTelemetrySink()

    response = TestClient(
        create_app(FakeApplication(), FakeAuthenticator(), telemetry=telemetry_sink)
    ).post(
        "/v1/search",
        headers={
            "Authorization": "Bearer test-token",
            "X-Correlation-Id": "corr-telemetry",
        },
        json={
            "region": "Moscow",
            "industries": ["logistics"],
        },
    )

    assert response.status_code == 200
    event = telemetry_sink.all()[-1]
    assert event.name == "http.request.completed"
    assert event.correlation_id != "corr-telemetry"
    assert event.correlation_id
    assert event.attributes["status"] == 200
    assert "authorization" not in event.attributes
    assert "body" not in event.attributes


def test_runtime_api_propagates_correlation_id() -> None:
    response = client(FakeApplication()).post(
        "/v1/search",
        headers={
            "Authorization": "Bearer test-token",
            "X-Correlation-Id": "corr-test",
        },
        json={
            "region": "Moscow",
            "industries": ["logistics"],
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"]
    assert response.headers["X-Correlation-Id"] != "corr-test"
    assert response.json()["correlationId"] == response.headers["X-Correlation-Id"]


def test_runtime_api_generates_correlation_id_when_missing() -> None:
    response = client(FakeApplication()).get(
        "/v1/diagnostics",
        headers={"Authorization": "Bearer test-token", "Idempotency-Key": "ai-api-test-1"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"]
    assert response.json()["healthy"] is True


class NoPermissionAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer no-permission":
            return AuthenticatedActor("operator-no-permission", trust_level=2)
        raise AuthenticationRequired()


def test_runtime_api_rejects_authenticated_but_unauthorized_search() -> None:
    response = TestClient(
        create_app(FakeApplication(), NoPermissionAuthenticator())
    ).post(
        "/v1/search",
        headers={"Authorization": "Bearer no-permission"},
        json={"region": "Moscow", "industries": ["logistics"]},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


def test_runtime_api_rejects_authenticated_but_unauthorized_sensitive_read() -> None:
    response = TestClient(
        create_app(FakeApplication(), NoPermissionAuthenticator())
    ).get(
        "/v1/economics/identity-1",
        headers={"Authorization": "Bearer no-permission"},
    )

    assert response.status_code == 403
    assert response.json()["code"] == "authorization_denied"


def test_runtime_api_hard_limits_request_body() -> None:
    response = TestClient(
        create_app(FakeApplication(), FakeAuthenticator())
    ).post(
        "/v1/search",
        headers={"Authorization": "Bearer test-token"},
        content=b"x" * (1_048_576 + 1),
    )

    assert response.status_code == 413
    assert response.json()["code"] == "request_body_too_large"


def test_runtime_api_requires_authentication() -> None:
    response = TestClient(
        create_app(FakeApplication(), RejectingAuthenticator())
    ).get("/v1/diagnostics")

    assert response.status_code == 401
    assert response.json()["code"] == "authentication_required"


def test_runtime_api_requires_idempotency_for_critical_mutation() -> None:
    response = client(FakeApplication()).post(
        "/v1/orders",
        headers={"Authorization": "Bearer test-token"},
        json={"actionId": "action-1", "lines": []},
    )

    assert response.status_code == 422


def test_runtime_api_counterparty_check_exposes_evidence_boundary() -> None:
    checker = FakeCounterpartyChecker()
    response = TestClient(
        create_app(
            FakeApplication(),
            FakeAuthenticator(),
            counterparty_checker=checker,
            authoritative_counterparty_lookup=FakeAuthoritativeLookup(),
        )
    ).post(
        "/v1/intelligence/counterparty-check",
        headers={
            "Authorization": "Bearer test-token",
            "X-Correlation-Id": "corr-counterparty",
        },
        json={
            "identifierType": "INN",
            "identifier": "7707083893",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["subjectRef"] == "identity-1"
    assert body["evidenceIds"] == ["evidence-1"]
    assert body["quarantined"] is True
    assert body["correlationId"] != "corr-counterparty"
    assert body["contradictions"][0]["field"] == "canonical_name"
    assert checker.calls[0][1] == "operator-1"
    assert checker.calls[0][2] == body["correlationId"]


def test_runtime_api_counterparty_check_rejects_client_supplied_evidence_fields() -> None:
    response = TestClient(
        create_app(
            FakeApplication(),
            FakeAuthenticator(),
            counterparty_checker=FakeCounterpartyChecker(),
        )
    ).post(
        "/v1/intelligence/counterparty-check",
        headers={"Authorization": "Bearer test-token"},
        json={
            "identifierType": "INN",
            "identifier": "7707083893",
            "canonicalName": "attacker-controlled",
        },
    )

    assert response.status_code == 422


def test_runtime_api_counterparty_check_requires_composed_capability() -> None:
    response = TestClient(
        create_app(FakeApplication(), FakeAuthenticator())
    ).post(
        "/v1/intelligence/counterparty-check",
        headers={"Authorization": "Bearer test-token"},
        json={
            "identifierType": "INN",
            "identifier": "7707083893",
        },
    )

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"



def test_runtime_api_maps_quarantine_to_423() -> None:
    response = client(QuarantineApplication()).post(
        "/v1/intelligence/research",
        headers={
            "Authorization": "Bearer test-token",
            "Idempotency-Key": "research-1",
        },
        json={
            "subjectRef": "identity-1",
            "companyType": "logistics",
            "depth": "R2_CONTEXT",
            "query": "ООО Альфа",
        },
    )

    assert response.status_code == 423
    assert response.json()["code"] == "review_required"


def test_runtime_api_maps_missing_application_to_503() -> None:
    response = TestClient(
        create_app(None, FakeAuthenticator())
    ).get(
        "/v1/diagnostics",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"


def test_runtime_api_wires_ai_run_through_application_boundary() -> None:
    response = client(FakeApplication()).post(
        "/v1/ai/run",
        headers={
            "Authorization": "Bearer test-token",
            "X-Correlation-Id": "corr-ai",
            "Idempotency-Key": "ai-api-test-1",
        },
        json={
            "taskType": "qualification",
            "promptVersion": "prompt:v1",
            "resourceRef": "identity-1",
            "inputRefs": ["identity-1"],
            "evidenceRefs": ["evidence-1"],
            "maxTokens": 100,
            "maxCost": 0.10,
            "maxDurationSeconds": 1,
        },
    )

    assert response.status_code == 200
    assert response.json()["providerId"] == "yandexgpt"
    assert response.json()["correlationId"] != "corr-ai"


def test_runtime_api_does_not_accept_client_controlled_ai_trust_levels() -> None:
    response = client(FakeApplication()).post(
        "/v1/ai/run",
        headers={"Authorization": "Bearer test-token"},
        json={
            "taskType": "qualification",
            "promptVersion": "prompt:v1",
            "resourceRef": "identity-1",
            "inputRefs": ["identity-1"],
            "evidenceRefs": ["evidence-1"],
            "evidenceLevel": 2,
            "resourceTrustLevel": 2,
            "maxTokens": 100,
            "maxCost": 0.10,
            "maxDurationSeconds": 1,
        },
    )

    assert response.status_code == 422


def test_runtime_api_ai_route_uses_existing_application_unavailable_boundary() -> None:
    response = TestClient(
        create_app(None, FakeAuthenticator())
    ).post(
        "/v1/ai/run",
        headers={"Authorization": "Bearer test-token"},
        json={
            "taskType": "qualification",
            "promptVersion": "prompt:v1",
            "resourceRef": "identity-1",
            "inputRefs": ["identity-1"],
            "evidenceRefs": ["evidence-1"],
            "maxTokens": 100,
            "maxCost": 0.10,
            "maxDurationSeconds": 1,
        },
    )

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"


def _activation_service() -> CounterpartyProviderActivationService:
    readiness = DaDataActivationReadiness(
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
    gate = DaDataControlledActivationGate(telemetry=InMemoryTelemetrySink())
    return CounterpartyProviderActivationService(
        gate=gate,
        configuration=DaDataConfiguration(api_key="test-secret", enabled=True),
        readiness=readiness,
    )


def test_runtime_api_provider_activation_requires_explicit_confirmation() -> None:
    service = _activation_service()
    denied = TestClient(
        create_app(
            FakeApplication(),
            ProviderActivationAuthenticator(),
            counterparty_provider_activation=service,
        )
    ).post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer provider-token"},
        json={
            "reason": "controlled verification",
            "activationVersion": "activation:test-v1",
        },
    )
    assert denied.status_code == 403
    assert denied.json()["code"] == "authorization_denied"

    granted = TestClient(
        create_app(
            FakeApplication(),
            ProviderActivationAuthenticator(),
            counterparty_provider_activation=service,
        )
    ).post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer provider-token"},
        json={
            "reason": "controlled verification",
            "activationVersion": "activation:test-v1",
        },
    )
    assert granted.status_code == 200
    assert granted.json()["providerId"] == DADATA_PROVIDER_ID
    assert granted.json()["enabled"] is True


def test_runtime_api_provider_activation_remains_unavailable_when_not_composed() -> None:
    response = TestClient(
        create_app(FakeApplication(), ProviderActivationAuthenticator())
    ).post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer provider-token"},
        json={
            "reason": "should remain unavailable",
            "operatorConfirmed": True,
            "activationVersion": "activation:test-v1",
        },
    )
    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"


def test_runtime_api_provider_rollback_uses_path_provider_identity() -> None:
    service = _activation_service()
    client_instance = TestClient(
        create_app(
            FakeApplication(),
            ProviderActivationAuthenticator(),
            counterparty_provider_activation=service,
        )
    )
    activated = client_instance.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/activation",
        headers={"Authorization": "Bearer provider-token"},
        json={
            "reason": "controlled verification",
            "operatorConfirmed": True,
            "activationVersion": "activation:test-v1",
        },
    )
    assert activated.status_code == 200

    rolled_back = client_instance.post(
        f"/v1/intelligence/providers/{DADATA_PROVIDER_ID}/rollback",
        headers={"Authorization": "Bearer rollback-token"},
        json={
            "reason": "kill switch drill",
            "operatorAuthorized": True,
        },
    )
    assert rolled_back.status_code == 200
    assert rolled_back.json()["enabled"] is False
