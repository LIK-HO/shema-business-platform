from __future__ import annotations

from dataclasses import dataclass
from time import monotonic
from typing import Protocol
from uuid import uuid4

from fastapi import APIRouter, FastAPI, Header, Path, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from shema_platform.experience.api_models import (
    CommercialActionCreateRequest,
    CommercialActionResponse,
    CommercialActionSendRequest,
    CommunicationResult,
    DiagnosticsResponse,
    DiscoveryRequest,
    DiscoveryResponse,
    EconomicResponse,
    ErrorEnvelope,
    OrderCreateRequest,
    OrderResponse,
    ResearchRequest,
    ResearchResponse,
    SearchRequest,
    SearchResponse,
)
from shema_platform.adapters.iam.oidc import OIDCConfiguration, OIDCJWTAuthenticator
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import AuthorizationSubject, Permission
from shema_platform.foundation.errors import (
    AuthorizationError,
    IdempotencyConflict,
    PolicyDenied,
    QuarantineRequired,
)
from shema_platform.foundation.runtime_security import RuntimeSecurityConfiguration
from shema_platform.foundation.telemetry import (
    NoopTelemetrySink,
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
        correlation_id = request.headers.get("X-Correlation-Id") or str(uuid4())
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
        if request.url.path in {"/docs", "/redoc", "/openapi.json"}:
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
    app.state.telemetry = telemetry or NoopTelemetrySink()
    app.add_middleware(AuthenticationMiddleware)
    app.add_middleware(CorrelationMiddleware)

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
            message=str(exc),
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
            message=str(exc),
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
            message=str(exc),
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
            message=str(exc),
        )

    def services(request: Request) -> APIApplication:
        value = request.app.state.application
        if value is None:
            raise ApplicationUnavailable
        return value

    router = APIRouter(prefix="/v1")

    @router.post("/search", response_model=SearchResponse)
    async def search(
        request: Request,
        payload: SearchRequest,
    ) -> SearchResponse:
        return services(request).search(payload, _context(request, None))

    @router.post("/discovery/evaluate", response_model=DiscoveryResponse)
    async def discovery(
        request: Request,
        payload: DiscoveryRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> DiscoveryResponse:
        return services(request).discovery(payload, _context(request, idempotency_key))

    @router.post("/intelligence/research", response_model=ResearchResponse)
    async def research(
        request: Request,
        payload: ResearchRequest,
        idempotency_key: str = Header(min_length=8, alias="Idempotency-Key"),
    ) -> ResearchResponse:
        return services(request).research(payload, _context(request, idempotency_key))

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
        return services(request).create_order(payload, _context(request, idempotency_key))

    @router.get("/orders/{orderId}", response_model=OrderResponse)
    async def get_order(
        request: Request,
        order_id: str = Path(alias="orderId"),
    ) -> OrderResponse:
        return services(request).get_order(order_id, _context(request, None))

    @router.get("/economics/{entityRef}", response_model=EconomicResponse)
    async def get_economics(
        request: Request,
        entity_ref: str = Path(alias="entityRef"),
    ) -> EconomicResponse:
        return services(request).get_economics(entity_ref, _context(request, None))

    @router.get("/diagnostics", response_model=DiagnosticsResponse)
    async def get_diagnostics(request: Request) -> DiagnosticsResponse:
        return services(request).get_diagnostics(_context(request, None))

    app.include_router(router)
    return app


app = create_app(enable_docs=True)
