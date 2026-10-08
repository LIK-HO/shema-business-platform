from __future__ import annotations

from shema_platform.experience.api import APIApplication, ApplicationUnavailable, RequestContext
from shema_platform.experience.api_models import (
    AIRunRequest,
    AIRunResponse,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommercialActionSendRequest,
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


class ProviderNeutralRuntimeApplication:
    """Canonical provider-neutral application composition for the HTTP runtime.

    The runtime edge is always composed explicitly. Optional providers and
    capability-specific applications remain separate boundaries and are never
    activated implicitly during process startup.
    """

    def __init__(self, capabilities: dict[str, APIApplication] | None = None) -> None:
        self._capabilities = dict(capabilities or {})

    def _service(self, capability: str) -> APIApplication:
        application = self._capabilities.get(capability)
        if application is None:
            raise ApplicationUnavailable(
                f"{capability} capability is not composed"
            )
        return application

    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse:
        return self._service("search").search(request, context)

    def run_ai(self, request: AIRunRequest, context: RequestContext) -> AIRunResponse:
        return self._service("ai").run_ai(request, context)

    def discovery(
        self,
        request: DiscoveryRequest,
        context: RequestContext,
    ) -> DiscoveryResponse:
        return self._service("discovery").discovery(request, context)

    def research(
        self,
        request: ResearchRequest,
        context: RequestContext,
    ) -> ResearchResponse:
        return self._service("research").research(request, context)

    def create_commercial_action(
        self,
        request: CommercialActionCreateRequest,
        context: RequestContext,
    ) -> CommercialActionResponse:
        return self._service("commercial").create_commercial_action(request, context)

    def send_commercial_action(
        self,
        action_id: str,
        request: CommercialActionSendRequest,
        context: RequestContext,
    ) -> CommunicationResult:
        return self._service("commercial").send_commercial_action(
            action_id,
            request,
            context,
        )

    def create_order(
        self,
        request: OrderCreateRequest,
        context: RequestContext,
    ) -> OrderResponse:
        return self._service("orders").create_order(request, context)

    def get_order(
        self,
        order_id: str,
        context: RequestContext,
    ) -> OrderResponse:
        return self._service("orders").get_order(order_id, context)

    def get_economics(
        self,
        entity_ref: str,
        context: RequestContext,
    ) -> EconomicResponse:
        return self._service("economics").get_economics(entity_ref, context)

    def get_diagnostics(self, context: RequestContext) -> DiagnosticsResponse:
        capabilities = sorted(self._capabilities)
        checks = [
            DiagnosticCheck(
                checkId="canonical_application",
                status="pass",
                message="provider-neutral canonical application is composed",
            ),
            DiagnosticCheck(
                checkId="capability_composition",
                status="pass" if capabilities else "warn",
                message=(
                    "configured capabilities: " + ", ".join(capabilities)
                    if capabilities
                    else "no optional capability is activated"
                ),
            ),
        ]
        return DiagnosticsResponse(
            healthy=True,
            checks=checks,
        )
