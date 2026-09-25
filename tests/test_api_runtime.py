from fastapi.testclient import TestClient

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
            return AuthenticatedActor("operator-1", trust_level=2)
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
    assert event.correlation_id == "corr-telemetry"
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
    assert response.headers["X-Correlation-Id"] == "corr-test"
    assert response.json()["correlationId"] == "corr-test"


def test_runtime_api_generates_correlation_id_when_missing() -> None:
    response = client(FakeApplication()).get(
        "/v1/diagnostics",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"]
    assert response.json()["healthy"] is True


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
        headers={"Authorization": "Bearer test-token", "X-Correlation-Id": "corr-ai"},
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
    assert response.json()["correlationId"] == "corr-ai"


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
