from __future__ import annotations

from shema_platform.experience.api import APIApplication, RequestContext
from shema_platform.experience.api_models import (
    AIRunRequest,
    AIRunResponse,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommercialActionSendRequest,
    CommunicationResult,
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


class SearchAugmentedAPIApplication:
    """Add the verified search capability without changing the base runtime semantics."""

    def __init__(self, base: APIApplication, search: APIApplication) -> None:
        self._base = base
        self._search = search

    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse:
        return self._search.search(request, context)

    def run_ai(self, request: AIRunRequest, context: RequestContext) -> AIRunResponse:
        return self._base.run_ai(request, context)

    def discovery(
        self,
        request: DiscoveryRequest,
        context: RequestContext,
    ) -> DiscoveryResponse:
        return self._base.discovery(request, context)

    def research(
        self,
        request: ResearchRequest,
        context: RequestContext,
    ) -> ResearchResponse:
        return self._base.research(request, context)

    def create_commercial_action(
        self,
        request: CommercialActionCreateRequest,
        context: RequestContext,
    ) -> CommercialActionResponse:
        return self._base.create_commercial_action(request, context)

    def send_commercial_action(
        self,
        action_id: str,
        request: CommercialActionSendRequest,
        context: RequestContext,
    ) -> CommunicationResult:
        return self._base.send_commercial_action(action_id, request, context)

    def create_order(
        self,
        request: OrderCreateRequest,
        context: RequestContext,
    ) -> OrderResponse:
        return self._base.create_order(request, context)

    def get_order(
        self,
        order_id: str,
        context: RequestContext,
    ) -> OrderResponse:
        return self._base.get_order(order_id, context)

    def get_economics(
        self,
        entity_ref: str,
        context: RequestContext,
    ) -> EconomicResponse:
        return self._base.get_economics(entity_ref, context)

    def get_diagnostics(self, context: RequestContext) -> DiagnosticsResponse:
        return self._base.get_diagnostics(context)
