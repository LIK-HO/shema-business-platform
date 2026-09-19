from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from shema_platform.experience.api import (
    APIApplication,
    RequestContext,
    create_app,
)
from shema_platform.experience.api_models import (
    CommunicationResult,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommercialActionSendRequest,
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
from shema_platform.foundation.errors import QuarantineRequired


class FakeApplication(APIApplication):
    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse:
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
            contact_ref=request.contact_ref,
            channel=request.channel,
            status="ready",
        )

    def send_commercial_action(
        self,
        action_id: str,
        request: CommercialActionSendRequest,
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


def test_runtime_api_propagates_correlation_id() -> None:
    client = TestClient(create_app(FakeApplication()))

    response = client.post(
        "/v1/search",
        headers={"X-Correlation-Id": "corr-test"},
        json={
            "region": "Moscow",
            "industries": ["logistics"],
        },
    )

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"] == "corr-test"
    assert response.json()["correlationId"] == "corr-test"


def test_runtime_api_generates_correlation_id_when_missing() -> None:
    client = TestClient(create_app(FakeApplication()))

    response = client.get("/v1/diagnostics")

    assert response.status_code == 200
    assert response.headers["X-Correlation-Id"]
    assert response.json()["healthy"] is True


def test_runtime_api_requires_idempotency_for_critical_mutation() -> None:
    client = TestClient(create_app(FakeApplication()))

    response = client.post(
        "/v1/orders",
        json={"actionId": "action-1", "lines": []},
    )

    assert response.status_code == 422


def test_runtime_api_maps_quarantine_to_423() -> None:
    client = TestClient(create_app(QuarantineApplication()))

    response = client.post(
        "/v1/intelligence/research",
        headers={"Idempotency-Key": "research-1"},
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
    client = TestClient(create_app())

    response = client.get("/v1/diagnostics")

    assert response.status_code == 503
    assert response.json()["code"] == "application_unavailable"
