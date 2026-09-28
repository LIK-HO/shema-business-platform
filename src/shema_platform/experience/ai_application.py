from __future__ import annotations

from shema_platform.application.ai_runtime import AIExecutionRequest, AIExecutionService
from shema_platform.experience.api import ApplicationUnavailable, RequestContext
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


class AIOnlyAPIApplication:
    """Bounded API composition exposing only the completed AI capability."""

    def __init__(self, service: AIExecutionService) -> None:
        self._service = service

    def run_ai(
        self,
        request: AIRunRequest,
        context: RequestContext,
    ) -> AIRunResponse:
        run = self._service.execute(
            AIExecutionRequest(
                task_type=request.task_type,
                prompt_version=request.prompt_version,
                resource_ref=request.resource_ref,
                input_refs=tuple(request.input_refs),
                evidence_refs=tuple(request.evidence_refs),
                evidence_required=request.evidence_required,
                max_tokens=request.max_tokens,
                max_cost=request.max_cost,
                max_duration_seconds=request.max_duration_seconds,
                actor_id=context.actor_id,
                actor_trust_level=context.trust_level,
                permissions=context.permissions,
                correlation_id=context.correlation_id,
            )
        )
        return AIRunResponse(
            runId=run.run_id,
            taskId=run.task_id,
            providerId=run.provider_id,
            model=run.model,
            modelVersion=run.model_version,
            promptVersion=run.prompt_version,
            inputRefs=run.input_refs,
            evidenceRefs=run.evidence_refs,
            output=run.output,
            tokens=run.tokens,
            cost=run.cost,
            durationSeconds=run.duration_seconds,
            correlationId=context.correlation_id,
        )

    @staticmethod
    def _unsupported() -> None:
        raise ApplicationUnavailable(
            "requested application capability is not composed"
        )

    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse:
        self._unsupported()

    def discovery(
        self,
        request: DiscoveryRequest,
        context: RequestContext,
    ) -> DiscoveryResponse:
        self._unsupported()

    def research(
        self,
        request: ResearchRequest,
        context: RequestContext,
    ) -> ResearchResponse:
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

    def get_order(
        self,
        order_id: str,
        context: RequestContext,
    ) -> OrderResponse:
        self._unsupported()

    def get_economics(
        self,
        entity_ref: str,
        context: RequestContext,
    ) -> EconomicResponse:
        self._unsupported()

    def get_diagnostics(self, context: RequestContext) -> DiagnosticsResponse:
        self._unsupported()
