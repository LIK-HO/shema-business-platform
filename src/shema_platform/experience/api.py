from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from decimal import Decimal
import hashlib
import json
from time import monotonic
from typing import Protocol
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Header, Path, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from shema_platform.adapters.ai.composition import AIProviderCompositionError
from shema_platform.adapters.iam.oidc import OIDCConfiguration, OIDCJWTAuthenticator
from shema_platform.adapters.intelligence.dadata_activation import DaDataActivationError
from shema_platform.application.counterparty_check import (
    AuthoritativeCounterpartyLookup,
    CounterpartyCheckService,
    CounterpartyIdentifierType,
)
from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupIdentifierType,
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
)
from shema_platform.application.counterparty_monitoring import (
    CounterpartyMonitoringService,
)
from shema_platform.application.counterparty_provider_activation import (
    CounterpartyProviderActivationCommand,
    CounterpartyProviderActivationService,
)
from shema_platform.application.counterparty_provider_runtime_lookup import (
    CounterpartyProviderRuntimeLookupService,
)
from shema_platform.application.commands import Actor
from shema_platform.application.public_intake import (
    PublicIntakePayload,
    PublicIntakeRateLimited,
    PublicIntakeSecurityRejected,
    PublicIntakeService,
)
from shema_platform.application.resource_read_authorization import ResourceReadAuthorizer
from shema_platform.application.repeat_order import RepeatOrderService
from shema_platform.domain.repeat_order import RepeatCadence, RepeatCadenceUnit, RepeatOrderContext
from shema_platform.experience.api_models import (
    AIRunRequest,
    AIRunResponse,
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommercialActionSendRequest,
    CommunicationResult,
    CounterpartyCheckRequest,
    CounterpartyCheckResponse,
    CounterpartyContradictionResponse,
    CounterpartyFavoriteListResponse,
    CounterpartyFavoriteResponse,
    CounterpartyMonitorListResponse,
    CounterpartyMonitorResponse,
    CounterpartyProviderActivationRequest,
    CounterpartyProviderActivationResponse,
    CounterpartyProviderLookupRequest,
    CounterpartyProviderLookupResponse,
    CounterpartyProviderRollbackRequest,
    CounterpartySubscriptionRequest,
    DiagnosticsResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    EconomicResponse,
    ErrorEnvelope,
    OperatorCapabilitiesResponse,
    OperatorNotificationListResponse,
    OperatorNotificationResponse,
    OrderCreateRequest,
    OrderResponse,
    PublicIntakeRequest,
    PublicIntakeResponse,
    ResearchRequest,
    ResearchResponse,
    RepeatCadenceRequest,
    RepeatContextRequest,
    RepeatPlanActionRequest,
    RepeatPlanConfirmRequest,
    RepeatPlanCreateRequest,
    RepeatPlanEditRequest,
    RepeatPlanResponse,
    SearchRequest,
    SearchResponse,
)
from shema_platform.experience.web import install_web_operator_surface
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import AuthorizationSubject, Permission, RBACAuthorizer
from shema_platform.foundation.errors import (
    AuthorizationError,
    IdempotencyConflict,
    PolicyDenied,
    QuarantineRequired,
)
from shema_platform.foundation.http_security import (
    BotChallengeVerifier,
    RequestBodySizeLimitMiddleware,
    trusted_peer_identity,
)
from shema_platform.foundation.provider_health import ProviderHealthRegistry
from shema_platform.foundation.runtime_security import RuntimeSecurityConfiguration
from shema_platform.foundation.safe_errors import safe_error_detail
from shema_platform.foundation.telemetry import (
    NoopTelemetrySink,
    StructuredLoggingTelemetrySink,
    TelemetrySink,
    build_event,
)


class ApplicationUnavailable(RuntimeError):
    """Raised when the HTTP edge has no application composition yet."""


@dataclass(frozen=True, slots=True)
class RequestContext:
    correlation_id: str
    actor_id: str
    trust_level: int
    idempotency_key: str | None
    permissions: frozenset[Permission] = frozenset()

    def authorization_subject(self) -> AuthorizationSubject:
        return AuthorizationSubject.from_actor(
            actor_id=self.actor_id,
            permissions=self.permissions,
        )


class APIApplication(Protocol):
    """Typed application boundary consumed by the HTTP edge."""

    def search(self, request: SearchRequest, context: RequestContext) -> SearchResponse: ...

    def discovery(
        self,
        request: DiscoveryRequest,
        context: RequestContext,
    ) -> DiscoveryResponse: ...

    def research(
        self,
        request: ResearchRequest,
        context: RequestContext,
    ) -> ResearchResponse: ...

    def run_ai(
        self,
        request: AIRunRequest,
        context: RequestContext,
    ) -> AIRunResponse: ...

    def create_commercial_action(
        self,
        request: CommercialActionCreateRequest,
        context: RequestContext,
    ) -> CommercialActionResponse: ...

    def send_commercial_action(
        self,
        action_id: str,
        request: CommercialActionSendRequest,
        context: RequestContext,
    ) -> CommunicationResult: ...

    def create_order(
        self,
        request: OrderCreateRequest,
        context: RequestContext,
    ) -> OrderResponse: ...

    def get_order(
        self,
        order_id: str,
        context: RequestContext,
    ) -> OrderResponse: ...

    def get_economics(
        self,
        entity_ref: str,
        context: RequestContext,
    ) -> EconomicResponse: ...

    def get_diagnostics(self, context: RequestContext) -> DiagnosticsResponse: ...


class CorrelationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        correlation_id = str(uuid4())
        request.state.correlation_id = correlation_id
        started = monotonic()

        try:
            response = await call_next(request)
        except Exception as exc:
            telemetry: TelemetrySink = request.app.state.telemetry
            telemetry.emit(
                build_event(
                    name="http.request.failed",
                    correlation_id=correlation_id,
                    attributes={
                        "component": "http",
                        "operation": request.method,
                        "status": 500,
                        "duration_ms": round((monotonic() - started) * 1000, 2),
                        "error_code": type(exc).__name__,
                    },
                )
            )
            raise

        telemetry = request.app.state.telemetry
        route = getattr(request.scope.get("route"), "path", "unknown")
        telemetry.emit(
            build_event(
                name="http.request.completed",
                correlation_id=correlation_id,
                attributes={
                    "component": "http",
                    "operation": request.method,
                    "route": route,
                    "status": response.status_code,
                    "duration_ms": round((monotonic() - started) * 1000, 2),
                },
            )
        )
        response.headers["X-Correlation-Id"] = correlation_id
        return response


class AuthenticationMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if (
            path in {
                "/",
                "/request",
                "/operator",
                "/max",
                "/system",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/health/ready",
                "/v1/public/intake",
            }
            or path.startswith("/web/")
        ):
            return await call_next(request)

        authenticator: AuthenticationPort | None = request.app.state.authenticator
        if authenticator is None:
            return _error(
                request,
                status_code=503,
                code="application_unavailable",
                message="Authentication services are not configured",
            )

        try:
            actor = authenticator.authenticate(
                request.headers.get("Authorization")
            )
        except AuthenticationRequired:
            return _error(
                request,
                status_code=401,
                code="authentication_required",
                message="Authentication required",
            )

        request.state.actor = actor
        return await call_next(request)


def _repeat_plan_response(plan) -> RepeatPlanResponse:
    return RepeatPlanResponse(
        planId=plan.plan_id,
        sourceOrderId=plan.source_order_id,
        identityId=plan.identity_id,
        ownerActorId=plan.owner_actor_id,
        cadenceUnit=plan.cadence.unit.value,
        cadenceInterval=plan.cadence.interval,
        scheduledFor=plan.context.scheduled_for,
        serviceScope=plan.context.service_scope,
        capacityUnits=str(plan.context.capacity_units),
        status=plan.status.value,
        pendingOrderId=plan.pending_order_id,
        lastOrderId=plan.last_order_id,
        skippedOccurrences=plan.skipped_occurrences,
        revision=plan.revision,
    )


async def _repeat_mutation(
    request: Request,
    plan_id: str,
    operation: str,
    idempotency_key: str,
) -> RepeatPlanResponse:
    context = _context(request, idempotency_key)
    service = request.app.state.repeat_order_service
    if service is None:
        raise ApplicationUnavailable("repeat order capability is not composed")
    actor = Actor(
        actor_id=context.actor_id,
        trust_level=context.trust_level,
        permissions=context.permissions,
    )
    request_hash = hashlib.sha256(
        json.dumps({"planId": plan_id, "operation": operation}, sort_keys=True).encode()
    ).hexdigest()
    method = {
        "pause": service.pause_plan,
        "resume": service.resume_plan,
        "skip": service.skip_once,
        "cancel": service.cancel_plan,
    }[operation]
    plan = method(
        actor=actor,
        plan_id=plan_id,
        request_hash=request_hash,
        idempotency_key=idempotency_key,
        correlation_id=context.correlation_id,
    )
    return _repeat_plan_response(plan)


def _context(
    request: Request,
    idempotency_key: str | None,
) -> RequestContext:
    actor: AuthenticatedActor = request.state.actor
    return RequestContext(
        correlation_id=request.state.correlation_id,
        actor_id=actor.actor_id,
        trust_level=actor.trust_level,
        idempotency_key=idempotency_key,
        permissions=actor.permissions,
    )

def _require_permission(
    request: Request,
    permission: Permission,
    idempotency_key: str | None = None,
) -> RequestContext:
    context = _context(request, idempotency_key)
    RBACAuthorizer(
        (
            AuthorizationSubject(
                actor_id=context.actor_id,
                permissions=context.permissions,
            ),
        )
    ).require(context.actor_id, permission)
    return context


def _resource_read_authorizer(request: Request) -> ResourceReadAuthorizer:
    authorizer = request.app.state.resource_read_authorizer
    if authorizer is None:
        raise ApplicationUnavailable(
            "resource read authorization capability is not composed"
        )
    return authorizer


def _error(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, object] | None = None,
) -> JSONResponse:
    payload = ErrorEnvelope(
        code=code,
        message=message,
        correlation_id=request.state.correlation_id,
        details=details,
    )
    return JSONResponse(
        status_code=status_code,
        content=payload.model_dump(mode="json", by_alias=True),
        headers={"X-Correlation-Id": request.state.correlation_id},
    )


def create_app(
    application: APIApplication | None = None,
    authenticator: AuthenticationPort | None = None,
    *,
    enable_docs: bool = True,
    telemetry: TelemetrySink | None = None,
    provider_health: ProviderHealthRegistry | None = None,
    counterparty_checker: CounterpartyCheckService | None = None,
    counterparty_monitoring: CounterpartyMonitoringService | None = None,
    counterparty_provider_activation: CounterpartyProviderActivationService | None = None,
    counterparty_provider_lookup: CounterpartyProviderRuntimeLookupService | None = None,
    public_intake: PublicIntakeService | None = None,
    operator_notification_reader=None,
    authoritative_counterparty_lookup: AuthoritativeCounterpartyLookup | None = None,
    bot_challenge_verifier: BotChallengeVerifier | None = None,
    resource_read_authorizer: ResourceReadAuthorizer | None = None,
    repeat_order_service=None,
) -> FastAPI:
    runtime_security = RuntimeSecurityConfiguration.from_environment(
        docs_enabled=enable_docs
    )
    runtime_security.enforce()

    if authenticator is None and runtime_security.environment == "production":
        authenticator = OIDCJWTAuthenticator.production(
            OIDCConfiguration.from_environment()
        )

    app = FastAPI(
        title="Shema Business Platform Canonical API",
        version="1.5.0",
        openapi_url="/openapi.json" if enable_docs else None,
        docs_url="/docs" if enable_docs else None,
        redoc_url="/redoc" if enable_docs else None,
    )
    app.state.application = application
    app.state.authenticator = authenticator
    app.state.provider_health = provider_health or ProviderHealthRegistry()
    app.state.counterparty_checker = counterparty_checker
    app.state.counterparty_monitoring = counterparty_monitoring
    app.state.counterparty_provider_activation = counterparty_provider_activation
    app.state.counterparty_provider_lookup = counterparty_provider_lookup
    app.state.public_intake = public_intake
    app.state.operator_notification_reader = operator_notification_reader
    app.state.authoritative_counterparty_lookup = authoritative_counterparty_lookup
    app.state.bot_challenge_verifier = bot_challenge_verifier
    app.state.resource_read_authorizer = resource_read_authorizer
    app.state.repeat_order_service = repeat_order_service
    default_telemetry: TelemetrySink = (
        StructuredLoggingTelemetrySink()
        if runtime_security.environment == "production"
        else NoopTelemetrySink()
    )
    app.state.telemetry = telemetry if telemetry is not None else default_telemetry
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(CorrelationMiddleware)
    app.add_middleware(RequestBodySizeLimitMiddleware, max_body_bytes=1_048_576)

    @app.exception_handler(AuthenticationRequired)
    async def authentication_required(
        request: Request,
        _: AuthenticationRequired,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=401,
            code="authentication_required",
            message="Authentication required",
        )

    @app.exception_handler(ApplicationUnavailable)
    async def application_unavailable(
        request: Request,
        _: ApplicationUnavailable,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=503,
            code="application_unavailable",
            message="Application services are not configured",
        )

    @app.exception_handler(AuthorizationError)
    async def authorization_error(
        request: Request,
        _: AuthorizationError,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=403,
            code="authorization_denied",
            message="Authorization denied",
        )

    @app.exception_handler(PolicyDenied)
    async def policy_denied(
        request: Request,
        exc: PolicyDenied,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=403,
            code="policy_denied",
            message=safe_error_detail(exc),
        )

    @app.exception_handler(IdempotencyConflict)
    async def idempotency_conflict(
        request: Request,
        exc: IdempotencyConflict,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=409,
            code="idempotency_conflict",
            message=safe_error_detail(exc),
        )

    @app.exception_handler(PublicIntakeSecurityRejected)
    async def public_intake_security_rejected(
        request: Request,
        exc: PublicIntakeSecurityRejected,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=400,
            code="public_intake_security_rejected",
            message=safe_error_detail(exc),
        )

    @app.exception_handler(PublicIntakeRateLimited)
    async def public_intake_rate_limited(
        request: Request,
        exc: PublicIntakeRateLimited,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=429,
            code="public_intake_rate_limited",
            message=safe_error_detail(exc),
            details={"budget": exc.budget},
        )

    @app.exception_handler(QuarantineRequired)
    async def quarantine_required(
        request: Request,
        exc: QuarantineRequired,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=423,
            code="review_required",
            message=safe_error_detail(exc),
        )

    @app.exception_handler(CounterpartyLookupProviderError)
    async def counterparty_provider_lookup_error(
        request: Request,
        exc: CounterpartyLookupProviderError,
    ) -> JSONResponse:
        status_code = (
            404
            if exc.code == "NOT_FOUND"
            else 429
            if exc.code == "PROVIDER_RATE_LIMIT"
            else 502
        )
        return _error(
            request,
            status_code=status_code,
            code=exc.code.lower(),
            message=safe_error_detail(exc),
            details={"retryable": exc.retryable},
        )

    @app.exception_handler(DaDataActivationError)
    async def dadata_activation_error(
        request: Request,
        exc: DaDataActivationError,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=409,
            code="provider_activation_blocked",
            message=safe_error_detail(exc),
        )

    @app.exception_handler(AIProviderCompositionError)
    async def ai_provider_composition_error(
        request: Request,
        exc: AIProviderCompositionError,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=503,
            code="ai_provider_unavailable",
            message=safe_error_detail(exc.failure.message),
            details={"failureCode": exc.failure.code.value},
        )

    @app.exception_handler(KeyError)
    async def not_found(
        request: Request,
        exc: KeyError,
    ) -> JSONResponse:
        return _error(
            request,
            status_code=404,
            code="not_found",
            message=safe_error_detail(exc),
        )

    def services(request: Request) -> APIApplication:
        value = request.app.state.application
        if value is None:
            raise ApplicationUnavailable
        return value

    @app.get("/health/ready")
    async def provider_readiness(request: Request) -> JSONResponse:
        registry: ProviderHealthRegistry = request.app.state.provider_health
        payload = {"ready": registry.ready()}
        return JSONResponse(
            status_code=200 if registry.ready() else 503,
            content=payload,
            headers={"X-Correlation-Id": request.state.correlation_id},
        )

    router = APIRouter(prefix="/v1")

    @app.post(
        "/v1/public/intake",
        response_model=PublicIntakeResponse,
        status_code=202,
    )
    async def public_intake_submission(
        request: Request,
        payload: PublicIntakeRequest,
        idempotency_key: str = Header(
            min_length=8,
            alias="Idempotency-Key",
        ),
        origin: str | None = Header(default=None),
        bot_challenge: str | None = Header(
            default=None,
            alias="X-Bot-Challenge",
        ),
    ) -> PublicIntakeResponse:
        service: PublicIntakeService | None = request.app.state.public_intake
        if service is None:
            raise ApplicationUnavailable(
                "public intake capability is not composed"
            )
        try:
            rate_limit_key = trusted_peer_identity(request.scope)
        except ValueError as exc:
            raise PublicIntakeSecurityRejected(
                "trusted client identity is unavailable"
            ) from exc

        verifier: BotChallengeVerifier | None = request.app.state.bot_challenge_verifier
        challenge_token = (bot_challenge or "").strip()
        if verifier is None:
            raise PublicIntakeSecurityRejected(
                "server-side bot challenge verification is unavailable"
            )
        try:
            challenge_verified = verifier.verify(
                token=challenge_token,
                peer_identity=rate_limit_key,
            )
        except Exception as exc:
            raise PublicIntakeSecurityRejected(
                "bot challenge verification failed"
            ) from exc
        if not challenge_verified:
            raise PublicIntakeSecurityRejected(
                "bot challenge verification rejected"
            )

        result = service.submit(
            payload=PublicIntakePayload(
                service_type=payload.service_type,
                location=payload.location,
                preferred_date_or_period=payload.preferred_date_or_period,
                work_or_cargo_description=payload.work_or_cargo_description,
                contact_name=payload.contact_name,
                contact_channel=payload.contact_channel,
                approximate_volume_or_weight=payload.approximate_volume_or_weight,
                access_or_lifting_constraints=payload.access_or_lifting_constraints,
                company_name=payload.company_name,
                inn=payload.inn,
                ogrn_or_ogrnip=payload.ogrn_or_ogrnip,
                comments=payload.comments,
                utm_source=payload.utm_source,
                utm_medium=payload.utm_medium,
                utm_campaign=payload.utm_campaign,
                referrer=payload.referrer,
                entry_surface=payload.entry_surface,
            ),
            idempotency_key=idempotency_key,
            public_client_key=rate_limit_key,
            origin=origin,
            bot_challenge_passed=True,
            correlation_id=request.state.correlation_id,
            honeypot_value=payload.honeypot,
        )
        return PublicIntakeResponse(
            requestId=result.record.request_id,
            correlationId=result.record.correlation_id,
            status=result.record.status.value,
            preflightDecision=result.record.preflight.decision.value,
            identityMatch=result.record.preflight.identity_match.value,
            projectionStatus=result.projection_status,
            deduplicated=result.deduplicated,
        )


    @router.get(
        "/operator/capabilities",
        response_model=OperatorCapabilitiesResponse,
    )
    async def operator_capabilities(request: Request) -> OperatorCapabilitiesResponse:
        context = _context(request, None)
        capabilities = {
            "publicIntake": request.app.state.public_intake is not None,
            "notifications": request.app.state.operator_notification_reader is not None,
            "counterpartyWorkspace": (
                request.app.state.counterparty_checker is not None
                or request.app.state.counterparty_monitoring is not None
            ),
            "search": request.app.state.application is not None,
            "repeatOrders": request.app.state.repeat_order_service is not None,
            "diagnostics": request.app.state.application is not None,
        }
        return OperatorCapabilitiesResponse(
            actorId=context.actor_id,
            capabilities=capabilities,
        )

    @router.post(
        "/operator/repeat-orders",
        response_model=RepeatPlanResponse,
    )
    async def create_repeat_plan(
        body: RepeatPlanCreateRequest,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> RepeatPlanResponse:
        context = _context(request, idempotency_key)
        service = request.app.state.repeat_order_service
        if service is None:
            raise ApplicationUnavailable("repeat order capability is not composed")
        payload = body.model_dump(by_alias=True)
        request_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, default=str).encode("utf-8")
        ).hexdigest()
        plan = service.create_plan(
            plan_id=body.plan_id,
            source_order_id=body.source_order_id,
            actor=Actor(
                actor_id=context.actor_id,
                trust_level=context.trust_level,
                permissions=context.permissions,
            ),
            cadence=RepeatCadence(
                unit=RepeatCadenceUnit(body.cadence.unit),
                interval=body.cadence.interval,
            ),
            context=RepeatOrderContext(
                scheduled_for=body.context.scheduled_for,
                service_scope=body.context.service_scope,
                capacity_units=Decimal(str(body.context.capacity_units)),
            ),
            request_hash=request_hash,
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
        )
        return RepeatPlanResponse(
            planId=plan.plan_id,
            sourceOrderId=plan.source_order_id,
            identityId=plan.identity_id,
            ownerActorId=plan.owner_actor_id,
            cadenceUnit=plan.cadence.unit.value,
            cadenceInterval=plan.cadence.interval,
            scheduledFor=plan.context.scheduled_for,
            serviceScope=plan.context.service_scope,
            capacityUnits=str(plan.context.capacity_units),
            status=plan.status.value,
            pendingOrderId=plan.pending_order_id,
            lastOrderId=plan.last_order_id,
            skippedOccurrences=plan.skipped_occurrences,
            revision=plan.revision,
        )

    @router.post(
        "/operator/repeat-orders/{plan_id}/next",
        response_model=OrderResponse,
    )
    async def create_repeat_next(
        plan_id: str,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> OrderResponse:
        context = _context(request, idempotency_key)
        service = request.app.state.repeat_order_service
        if service is None:
            raise ApplicationUnavailable("repeat order capability is not composed")
        actor = Actor(
            actor_id=context.actor_id,
            trust_level=context.trust_level,
            permissions=context.permissions,
        )
        result = service.create_next_repeat_order(
            actor=actor,
            plan_id=plan_id,
            request_hash=hashlib.sha256(plan_id.encode()).hexdigest(),
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
        )
        return OrderResponse(
            orderId=result.order_id,
            identityId=result.identity_id,
            sourceActionId=result.source_action_id,
            status=result.status.value,
            lines=[
                {
                    "lineId": line.line_id,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unitPrice": {
                        "amount": str(line.unit_price.amount),
                        "currency": line.unit_price.currency,
                    },
                }
                for line in result.lines
            ],
        )

    @router.post(
        "/operator/repeat-orders/{plan_id}/confirm",
        response_model=OrderResponse,
    )
    async def confirm_repeat(
        plan_id: str,
        body: RepeatPlanConfirmRequest,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> OrderResponse:
        context = _context(request, idempotency_key)
        service = request.app.state.repeat_order_service
        if service is None:
            raise ApplicationUnavailable("repeat order capability is not composed")
        actor = Actor(
            actor_id=context.actor_id,
            trust_level=context.trust_level,
            permissions=context.permissions,
        )
        result = service.confirm_repeat_order(
            actor=actor,
            plan_id=plan_id,
            order_id=body.order_id,
            request_hash=hashlib.sha256(
                json.dumps(body.model_dump(by_alias=True), sort_keys=True, default=str).encode()
            ).hexdigest(),
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
        )
        return OrderResponse(
            orderId=result.order_id,
            identityId=result.identity_id,
            sourceActionId=result.source_action_id,
            status=result.status.value,
            lines=[
                {
                    "lineId": line.line_id,
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unitPrice": {
                        "amount": str(line.unit_price.amount),
                        "currency": line.unit_price.currency,
                    },
                }
                for line in result.lines
            ],
        )

    @router.post("/operator/repeat-orders/{plan_id}/pause", response_model=RepeatPlanResponse)
    async def pause_repeat(
        plan_id: str,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> RepeatPlanResponse:
        return await _repeat_mutation(request, plan_id, "pause", idempotency_key)

    @router.post("/operator/repeat-orders/{plan_id}/resume", response_model=RepeatPlanResponse)
    async def resume_repeat(
        plan_id: str,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> RepeatPlanResponse:
        return await _repeat_mutation(request, plan_id, "resume", idempotency_key)

    @router.post("/operator/repeat-orders/{plan_id}/skip", response_model=RepeatPlanResponse)
    async def skip_repeat(
        plan_id: str,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> RepeatPlanResponse:
        return await _repeat_mutation(request, plan_id, "skip", idempotency_key)

    @router.post("/operator/repeat-orders/{plan_id}/cancel", response_model=RepeatPlanResponse)
    async def cancel_repeat(
        plan_id: str,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> RepeatPlanResponse:
        return await _repeat_mutation(request, plan_id, "cancel", idempotency_key)

    @router.put("/operator/repeat-orders/{plan_id}/context", response_model=RepeatPlanResponse)
    async def edit_repeat_context(
        plan_id: str,
        body: RepeatPlanEditRequest,
        request: Request,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> RepeatPlanResponse:
        context = _context(request, idempotency_key)
        service = request.app.state.repeat_order_service
        if service is None:
            raise ApplicationUnavailable("repeat order capability is not composed")
        actor = Actor(
            actor_id=context.actor_id,
            trust_level=context.trust_level,
            permissions=context.permissions,
        )
        payload = body.model_dump(by_alias=True)
        plan = service.edit_context(
            actor=actor,
            plan_id=plan_id,
            context=RepeatOrderContext(
                scheduled_for=body.context.scheduled_for,
                service_scope=body.context.service_scope,
                capacity_units=Decimal(str(body.context.capacity_units)),
            ),
            request_hash=hashlib.sha256(
                json.dumps(payload, sort_keys=True, default=str).encode()
            ).hexdigest(),
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
        )
        return _repeat_plan_response(plan)

    @router.get(
        "/operator/notifications",
        response_model=OperatorNotificationListResponse,
    )
    async def operator_notifications(
        request: Request,
        limit: int = 50,
    ) -> OperatorNotificationListResponse:
        if limit < 1 or limit > 100:
            raise ValueError("limit must be between 1 and 100")
        reader = request.app.state.operator_notification_reader
        if reader is None:
            raise ApplicationUnavailable(
                "operator notification center is not composed"
            )
        context = _context(request, None)
        RBACAuthorizer(
            (
                AuthorizationSubject(
                    actor_id=context.actor_id,
                    permissions=context.permissions,
                ),
            )
        ).require(
            context.actor_id,
            Permission.PUBLIC_INTAKE_REVIEW,
        )
        notifications = reader.list_unread(limit=limit)
        return OperatorNotificationListResponse(
            notifications=[
                OperatorNotificationResponse(**notification)
                for notification in notifications
            ]
        )

    @router.post("/search", response_model=SearchResponse)
    async def search(
        request: Request,
        payload: SearchRequest,
    ) -> SearchResponse:
        return services(request).search(
            payload,
            _require_permission(request, Permission.SEARCH_RUN),
        )

    @router.post("/ai/run", response_model=AIRunResponse)
    async def run_ai(
        request: Request,
        payload: AIRunRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> AIRunResponse:
        return services(request).run_ai(
            payload,
            _require_permission(
                request,
                Permission.AI_RUN,
                idempotency_key=idempotency_key,
            ),
        )

    @router.post("/discovery/evaluate", response_model=DiscoveryResponse)
    async def discovery(
        request: Request,
        payload: DiscoveryRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> DiscoveryResponse:
        context = _require_permission(request, Permission.DISCOVERY_RUN)
        return services(request).discovery(
            payload,
            RequestContext(
                correlation_id=context.correlation_id,
                actor_id=context.actor_id,
                trust_level=context.trust_level,
                idempotency_key=idempotency_key,
                permissions=context.permissions,
            ),
        )

    @router.post("/intelligence/research", response_model=ResearchResponse)
    async def research(
        request: Request,
        payload: ResearchRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> ResearchResponse:
        context = _require_permission(request, Permission.RESEARCH_RUN)
        return services(request).research(
            payload,
            RequestContext(
                correlation_id=context.correlation_id,
                actor_id=context.actor_id,
                trust_level=context.trust_level,
                idempotency_key=idempotency_key,
                permissions=context.permissions,
            ),
        )

    @router.post(
        "/intelligence/counterparty-check",
        response_model=CounterpartyCheckResponse,
    )
    async def counterparty_check(
        request: Request,
        payload: CounterpartyCheckRequest,
    ) -> CounterpartyCheckResponse:
        context = _require_permission(request, Permission.COUNTERPARTY_CHECK)
        checker: CounterpartyCheckService | None = request.app.state.counterparty_checker
        authoritative_lookup: AuthoritativeCounterpartyLookup | None = (
            request.app.state.authoritative_counterparty_lookup
        )
        if checker is None or authoritative_lookup is None:
            raise ApplicationUnavailable(
                "authoritative counterparty lookup capability is not composed"
            )

        identifier_type = CounterpartyIdentifierType(payload.identifier_type)
        observation = authoritative_lookup.lookup(
            identifier_type=identifier_type,
            identifier=payload.identifier,
        )
        if (
            observation.identifier != payload.identifier.strip()
            or observation.identifier_type is not identifier_type
        ):
            raise AuthorizationError(
                "authoritative provider returned mismatched counterparty identity"
            )

        result = checker.check(
            observation,
            actor_id=context.actor_id,
            correlation_id=context.correlation_id,
        )
        return CounterpartyCheckResponse(
            subjectRef=result.subject_ref,
            identityRef=result.identity.identity_id if result.identity else None,
            identityState=result.identity.state.value if result.identity else None,
            freshness=result.freshness.value,
            evidenceIds=list(result.evidence_ids),
            contradictions=[
                CounterpartyContradictionResponse(
                    field=item.field,
                    existingValue=item.existing_value,
                    observedValue=item.observed_value,
                )
                for item in result.contradictions
            ],
            quarantined=result.quarantined,
            operatorBrief=result.operator_brief,
            correlationId=context.correlation_id,
        )

    @router.post(
        "/intelligence/counterparties/monitoring",
        response_model=CounterpartyMonitorResponse,
    )
    async def save_counterparty_monitoring(
        request: Request,
        payload: CounterpartySubscriptionRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> CounterpartyMonitorResponse:
        context = _require_permission(
            request,
            Permission.COUNTERPARTY_MONITOR_MANAGE,
            idempotency_key,
        )
        service: CounterpartyMonitoringService | None = (
            request.app.state.counterparty_monitoring
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty monitoring capability is not composed"
            )
        result = service.save_monitoring(
            identifier_type=CounterpartyIdentifierType(payload.identifier_type),
            identifier=payload.identifier,
            actor_id=context.actor_id,
            permissions=context.permissions,
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
            now=datetime.now(UTC),
        )
        return CounterpartyMonitorResponse(
            monitorId=result.monitor_id,
            actorId=result.actor_id,
            identifierType=result.identifier_type.value,
            identifier=result.identifier,
            status=result.status.value,
            nextCheckAt=result.next_check_at,
            lastCheckedAt=result.last_checked_at,
        )

    @router.get(
        "/intelligence/counterparties/monitoring",
        response_model=CounterpartyMonitorListResponse,
    )
    async def list_counterparty_monitoring(
        request: Request,
    ) -> CounterpartyMonitorListResponse:
        context = _require_permission(request, Permission.COUNTERPARTY_MONITOR_MANAGE)
        service: CounterpartyMonitoringService | None = (
            request.app.state.counterparty_monitoring
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty monitoring capability is not composed"
            )
        return CounterpartyMonitorListResponse(
            monitors=[
                CounterpartyMonitorResponse(
                    monitorId=item.monitor_id,
                    actorId=item.actor_id,
                    identifierType=item.identifier_type.value,
                    identifier=item.identifier,
                    status=item.status.value,
                    nextCheckAt=item.next_check_at,
                    lastCheckedAt=item.last_checked_at,
                )
                for item in service.list_monitors(context.actor_id, context.permissions)
            ]
        )

    @router.post(
        "/intelligence/counterparties/favorites",
        response_model=CounterpartyFavoriteResponse,
    )
    async def save_counterparty_favorite(
        request: Request,
        payload: CounterpartySubscriptionRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> CounterpartyFavoriteResponse:
        context = _require_permission(
            request,
            Permission.COUNTERPARTY_FAVORITE_MANAGE,
            idempotency_key,
        )
        service: CounterpartyMonitoringService | None = (
            request.app.state.counterparty_monitoring
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty monitoring capability is not composed"
            )
        result = service.save_favorite(
            identifier_type=CounterpartyIdentifierType(payload.identifier_type),
            identifier=payload.identifier,
            actor_id=context.actor_id,
            permissions=context.permissions,
            idempotency_key=idempotency_key,
            correlation_id=context.correlation_id,
            now=datetime.now(UTC),
        )
        return CounterpartyFavoriteResponse(
            favoriteId=result.favorite_id,
            actorId=result.actor_id,
            identifierType=result.identifier_type.value,
            identifier=result.identifier,
            createdAt=result.created_at,
        )

    @router.get(
        "/intelligence/counterparties/favorites",
        response_model=CounterpartyFavoriteListResponse,
    )
    async def list_counterparty_favorites(
        request: Request,
    ) -> CounterpartyFavoriteListResponse:
        context = _require_permission(request, Permission.COUNTERPARTY_FAVORITE_MANAGE)
        service: CounterpartyMonitoringService | None = (
            request.app.state.counterparty_monitoring
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty monitoring capability is not composed"
            )
        return CounterpartyFavoriteListResponse(
            favorites=[
                CounterpartyFavoriteResponse(
                    favoriteId=item.favorite_id,
                    actorId=item.actor_id,
                    identifierType=item.identifier_type.value,
                    identifier=item.identifier,
                    createdAt=item.created_at,
                )
                for item in service.list_favorites(context.actor_id, context.permissions)
            ]
        )

    @router.post(
        "/intelligence/providers/{providerId}/activation",
        response_model=CounterpartyProviderActivationResponse,
    )
    async def activate_counterparty_provider(
        request: Request,
        payload: CounterpartyProviderActivationRequest,
        provider_id: str = Path(alias="providerId"),
    ) -> CounterpartyProviderActivationResponse:
        service: CounterpartyProviderActivationService | None = (
            request.app.state.counterparty_provider_activation
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty provider activation capability is not composed"
            )
        context = _require_permission(
            request,
            Permission.INTELLIGENCE_PROVIDER_ACTIVATE,
        )
        result = service.activate(
            CounterpartyProviderActivationCommand(
                provider_id=provider_id,
                actor_id=context.actor_id,
                reason=payload.reason,
                operator_authorized=payload.operator_confirmed,
                activation_version=payload.activation_version,
                correlation_id=context.correlation_id,
            ),
            permissions=context.permissions,
        )
        return CounterpartyProviderActivationResponse(
            providerId=result.provider_id,
            enabled=result.enabled,
            activatedBy=result.activated_by,
            activationVersion=result.activation_version,
            rollbackBy=result.rollback_by,
            rollbackReason=result.rollback_reason,
        )

    @router.post(
        "/intelligence/providers/{providerId}/lookup",
        response_model=CounterpartyProviderLookupResponse,
    )
    async def lookup_counterparty_provider(
        request: Request,
        payload: CounterpartyProviderLookupRequest,
        provider_id: str = Path(alias="providerId"),
    ) -> CounterpartyProviderLookupResponse:
        service: CounterpartyProviderRuntimeLookupService | None = (
            request.app.state.counterparty_provider_lookup
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty provider lookup capability is not composed"
            )
        context = _require_permission(
            request,
            Permission.INTELLIGENCE_PROVIDER_LOOKUP,
        )
        result = service.execute(
            CounterpartyLookupQuery(
                identifier_type=CounterpartyLookupIdentifierType(payload.identifier_type),
                identifier=payload.identifier,
            ),
            actor_id=context.actor_id,
            permissions=context.permissions,
            correlation_id=context.correlation_id,
        )
        if result.provider_record.provider_id != provider_id:
            raise ValueError("counterparty provider identity mismatch")
        return CounterpartyProviderLookupResponse(
            providerId=result.provider_record.provider_id,
            sourceRef=result.provider_record.source_ref,
            canonicalName=result.provider_record.canonical_name,
            taxId=result.provider_record.tax_id,
            registrationId=result.provider_record.registration_id,
            legalStatus=result.provider_record.legal_status,
            observedAtMs=result.provider_record.observed_at_ms,
            evidenceIds=list(result.evidence_result.evidence_ids),
            subjectRef=result.evidence_result.subject_ref,
            identityRef=result.evidence_result.identity_ref,
            contradictions=[
                CounterpartyContradictionResponse(
                    field=field,
                    existingValue=existing,
                    observedValue=observed,
                )
                for field, existing, observed in result.evidence_result.contradictions
            ],
            quarantined=result.evidence_result.quarantined,
            correlationId=context.correlation_id,
        )

    @router.post(
        "/intelligence/providers/{providerId}/rollback",
        response_model=CounterpartyProviderActivationResponse,
    )
    async def rollback_counterparty_provider(
        request: Request,
        payload: CounterpartyProviderRollbackRequest,
        provider_id: str = Path(alias="providerId"),
    ) -> CounterpartyProviderActivationResponse:
        service: CounterpartyProviderActivationService | None = (
            request.app.state.counterparty_provider_activation
        )
        if service is None:
            raise ApplicationUnavailable(
                "counterparty provider activation capability is not composed"
            )
        context = _require_permission(
            request,
            Permission.INTELLIGENCE_PROVIDER_ROLLBACK,
        )
        result = service.rollback(
            provider_id=provider_id,
            actor_id=context.actor_id,
            reason=payload.reason,
            operator_authorized=payload.operator_confirmed,
            correlation_id=context.correlation_id,
            permissions=context.permissions,
        )
        return CounterpartyProviderActivationResponse(
            providerId=result.provider_id,
            enabled=result.enabled,
            activatedBy=result.activated_by,
            activationVersion=result.activation_version,
            rollbackBy=result.rollback_by,
            rollbackReason=result.rollback_reason,
        )

    @router.post(
        "/commercial-actions",
        response_model=CommercialActionResponse,
        status_code=201,
    )
    async def create_commercial_action(
        request: Request,
        payload: CommercialActionCreateRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> CommercialActionResponse:
        _require_permission(request, Permission.COMMERCIAL_ACTION_CREATE)
        return services(request).create_commercial_action(
            payload,
            _context(request, idempotency_key),
        )

    @router.post(
        "/commercial-actions/{actionId}/send",
        response_model=CommunicationResult,
    )
    async def send_commercial_action(
        request: Request,
        payload: CommercialActionSendRequest,
        action_id: str = Path(alias="actionId"),
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> CommunicationResult:
        _require_permission(request, Permission.COMMERCIAL_ACTION_SEND)
        return services(request).send_commercial_action(
            action_id,
            payload,
            _context(request, idempotency_key),
        )

    @router.post("/orders", response_model=OrderResponse, status_code=201)
    async def create_order(
        request: Request,
        payload: OrderCreateRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> OrderResponse:
        context = _require_permission(request, Permission.ORDER_CREATE)
        return services(request).create_order(
            payload,
            RequestContext(
                correlation_id=context.correlation_id,
                actor_id=context.actor_id,
                trust_level=context.trust_level,
                idempotency_key=idempotency_key,
                permissions=context.permissions,
            ),
        )

    @router.get("/orders/{orderId}", response_model=OrderResponse)
    async def get_order(
        request: Request,
        order_id: str = Path(alias="orderId"),
    ) -> OrderResponse:
        context = _require_permission(request, Permission.ORDER_READ)
        _resource_read_authorizer(request).require_order_read(
            order_id=order_id,
            actor_id=context.actor_id,
        )
        return services(request).get_order(order_id, context)

    @router.get("/economics/{entityRef}", response_model=EconomicResponse)
    async def get_economics(
        request: Request,
        entity_ref: str = Path(alias="entityRef"),
    ) -> EconomicResponse:
        context = _require_permission(request, Permission.ECONOMICS_READ)
        _resource_read_authorizer(request).require_economics_read(
            entity_ref=entity_ref,
            actor_id=context.actor_id,
        )
        return services(request).get_economics(entity_ref, context)

    @router.get("/diagnostics", response_model=DiagnosticsResponse)
    async def get_diagnostics(request: Request) -> DiagnosticsResponse:
        return services(request).get_diagnostics(
            _require_permission(request, Permission.DIAGNOSTICS_READ),
        )

    app.include_router(router)
    install_web_operator_surface(app)
    return app


app = create_app(enable_docs=True)
