from __future__ import annotations

from shema_platform.application.operator_search import OperatorSearchService
from shema_platform.domain.search import SearchCriteria, SelectionLevel
from shema_platform.experience.api import ApplicationUnavailable, RequestContext
from shema_platform.experience.api_models import (
    AIRunRequest,
    AIRunResponse,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommercialActionSendRequest,
    CommunicationResult,
    DiscoveryRequest,
    DiscoveryResponse,
    EconomicResponse,
    OrderCreateRequest,
    OrderResponse,
    ResearchRequest,
    ResearchResponse,
    SearchHitResponse,
    SearchRequest,
    SearchResponse,
    SearchSourceAttemptResponse,
)


class SearchOnlyAPIApplication:
    """Bounded canonical API composition exposing only the completed search capability."""

    def __init__(self, service: OperatorSearchService) -> None:
        self._service = service

    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse:
        criteria = SearchCriteria(
            region=request.region,
            industries=frozenset(request.industries),
            limit=request.limit,
            selection_level=SelectionLevel(request.selection_level),
        )
        result = self._service.execute(
            criteria,
            source_ids=tuple(request.source_ids),
            budget=self._service_budget(request),
        )
        attempt_by_id = {item.source_ref: item for item in result.run.attempts}
        source_attempts = [
            SearchSourceAttemptResponse(
                sourceId=source.source_id,
                sourceClass=source.source_class,
                reliability=source.reliability,
                accessMode=source.access_mode,
                status=attempt_by_id[source.source_id].status.value,
                candidateCount=attempt_by_id[source.source_id].candidate_count,
                errorCode=attempt_by_id[source.source_id].error_code,
            )
            for source in result.plan.sources
        ]
        return SearchResponse(
            results=[
                SearchHitResponse(
                    candidateRef=hit.candidate_ref,
                    name=hit.name,
                    region=hit.region,
                    industries=sorted(hit.industries),
                    sourceRef=hit.source_ref,
                    taxId=hit.tax_id,
                    registrationId=hit.registration_id,
                    contactRefs=list(hit.contact_refs),
                    selectionLevel=hit.selection_level.value,
                )
                for hit in result.run.hits
            ],
            correlationId=context.correlation_id,
            completeness=result.run.completeness.value,
            planVersion=result.plan.plan_version,
            sourceAttempts=source_attempts,
        )

    @staticmethod
    def _service_budget(request: SearchRequest):
        from shema_platform.application.search_run import SearchBudget

        return SearchBudget(
            max_sources=request.max_sources,
            max_candidates=request.max_candidates,
        )

    @staticmethod
    def _unsupported() -> None:
        raise ApplicationUnavailable(
            "requested application capability is not composed"
        )

    def run_ai(self, request: AIRunRequest, context: RequestContext) -> AIRunResponse:
        self._unsupported()

    def discovery(self, request: DiscoveryRequest, context: RequestContext) -> DiscoveryResponse:
        self._unsupported()

    def research(self, request: ResearchRequest, context: RequestContext) -> ResearchResponse:
        self._unsupported()

    def create_commercial_action(
        self,
        request: CommercialActionCreateRequest,
        context: RequestContext,
    ) -> CommercialActionResponse:
        self._unsupported()

    def send_commercial_action(
        self,
        action_id: str,
        request: CommercialActionSendRequest,
        context: RequestContext,
    ) -> CommunicationResult:
        self._unsupported()

    def create_order(
        self,
        request: OrderCreateRequest,
        context: RequestContext,
    ) -> OrderResponse:
        self._unsupported()

    def get_order(self, order_id: str, context: RequestContext) -> OrderResponse:
        self._unsupported()

    def get_economics(self, entity_ref: str, context: RequestContext) -> EconomicResponse:
        self._unsupported()

    def get_diagnostics(self, context: RequestContext) -> EconomicResponse:
        self._unsupported()
