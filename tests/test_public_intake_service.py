from __future__ import annotations

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from shema_platform.application.counterparty_lookup import (
    CounterpartyLookupProviderError,
    CounterpartyLookupQuery,
    CounterpartyProviderRecord,
)
from shema_platform.application.public_intake import (
    IdentityMatch,
    PreflightDecision,
    PublicIntakePayload,
    PublicIntakeService,
)
from shema_platform.application.public_preflight import PublicCounterpartyPreflightService
from shema_platform.experience.api import create_app
from shema_platform.experience.api_models import (
    OperatorNotificationListResponse,
)
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import Permission

NOW = datetime(2026, 9, 28, 12, tzinfo=UTC)


class MemoryPublicIntakeRepository:
    def __init__(self) -> None:
        self.requests = {}
        self.outbox = []
        self.cache = {}
        self.budgets = {}

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def acquire_idempotency_lock(self, key):
        self.locked_keys = getattr(self, "locked_keys", set())
        if key in self.locked_keys:
            raise AssertionError("duplicate in-memory idempotency lock")
        self.locked_keys.add(key)

    def release_idempotency_lock(self, key):
        self.locked_keys.remove(key)

    def get_by_idempotency_key(self, key):
        return self.requests.get(key)

    def get_preflight_cache(self, cache_key, *, now):
        item = self.cache.get(cache_key)
        if item and item.expires_at > now:
            return item
        return None

    def consume_budget(self, *, public_client_key, budget, limit, window_seconds, now):
        window = int(now.timestamp()) // window_seconds
        key = (public_client_key, budget, window)
        current = self.budgets.get(key, 0)
        if current >= limit:
            from shema_platform.application.public_intake import PublicIntakeRateLimited

            raise PublicIntakeRateLimited("rate limit", budget=budget)
        self.budgets[key] = current + 1

    def save_preflight_cache(self, cache_key, snapshot):
        self.cache[cache_key] = snapshot

    def save_preflight_snapshot(self, snapshot, *, request_id):
        self.cache[f"snapshot:{snapshot.snapshot_id}"] = snapshot

    def add(self, record):
        self.requests[record.idempotency_key] = record

    def append_outbox(
        self,
        *,
        event_id,
        request_id,
        event_type,
        payload,
        occurred_at,
        notify_operator,
    ):
        self.outbox.append(
            {
                "event_id": event_id,
                "request_id": request_id,
                "event_type": event_type,
                "payload": payload,
                "notify_operator": notify_operator,
                "occurred_at": occurred_at,
            }
        )

    def mark_projected(self, request_id, *, now):
        for key, record in tuple(self.requests.items()):
            if record.request_id == request_id:
                from dataclasses import replace

                self.requests[key] = replace(record, projected_at=now)


class FakeProvider:
    provider_id = "fake_registry"
    source_version = "fake-registry:v1"
    source_authority = "official_registry"

    def __init__(self, record=None, error=None):
        self.record = record
        self.error = error
        self.calls = 0

    def lookup(self, query: CounterpartyLookupQuery) -> CounterpartyProviderRecord:
        self.calls += 1
        if self.error is not None:
            raise self.error
        return self.record


class MemoryProjector:
    def __init__(self, *, fail=False):
        self.fail = fail
        self.calls = []

    def project(self, record):
        if self.fail:
            raise RuntimeError("shema unavailable")
        self.calls.append(record.request_id)


class PermissionedAuthenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer operator-token":
            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset({Permission.PUBLIC_INTAKE_REVIEW}),
            )
        raise AuthenticationRequired()


class FakeBotChallengeVerifier:
    def verify(self, *, token: str, peer_identity: str) -> bool:
        return token == "passed" and bool(peer_identity)


def payload(**overrides) -> PublicIntakePayload:
    values = dict(
        service_type="Погрузка",
        location="Москва",
        preferred_date_or_period="2026-10-05",
        work_or_cargo_description="Погрузить оборудование в офисном помещении",
        contact_name="Иван Петров",
        contact_channel="+79990000000",
        company_name="ООО Альфа",
        inn="7707083893",
    )
    values.update(overrides)
    return PublicIntakePayload(**values)


def make_service(*, provider=None, projector=None, submission_limit=5, lookup_limit=20):
    repository = MemoryPublicIntakeRepository()
    preflight = PublicCounterpartyPreflightService(
        provider=provider,
        cache_lookup=repository.get_preflight_cache,
        consume_lookup_budget=lambda client, now: repository.consume_budget(
            public_client_key=client,
            budget="registry_lookup",
            limit=lookup_limit,
            window_seconds=600,
            now=now,
        ),
        cache_store=repository.save_preflight_cache,
        sleeper=lambda _: None,
    )
    service = PublicIntakeService(
        lambda: repository,
        preflight=preflight,
        projector=projector or MemoryProjector(),
        submission_limit=submission_limit,
        lookup_limit=lookup_limit,
        enforce_edge_proof=False,
        allowed_origins=frozenset({"https://example.test"}),
        clock=lambda: NOW,
    )
    return service, repository


def test_preflight_rejects_invalid_identifier_without_provider_call() -> None:
    provider = FakeProvider(
        record=CounterpartyProviderRecord(
            provider_id="fake_registry",
            source_ref="https://registry.example.test/party",
            canonical_name="ООО Альфа",
            tax_id="7707083893",
            registration_id="1027700132195",
            legal_status="ACTIVE",
        )
    )
    service, _ = make_service(provider=provider)

    result = service.submit(
        payload=payload(inn="7707083894"),
        idempotency_key="invalid-inn-1",
        public_client_key="public-client-1",
        origin="https://example.test",
        bot_challenge_passed=True,
        correlation_id="corr-invalid",
    )

    assert result.record.preflight.decision is PreflightDecision.BLOCKING_FACT
    assert "INVALID_IDENTIFIER_CHECKSUM" in result.record.preflight.flags
    assert provider.calls == 0


def test_preflight_matches_counterparty_without_gpt() -> None:
    provider = FakeProvider(
        record=CounterpartyProviderRecord(
            provider_id="fake_registry",
            source_ref="https://registry.example.test/party",
            canonical_name="ООО Альфа",
            tax_id="7707083893",
            registration_id="1027700132195",
            legal_status="ACTIVE",
        )
    )
    projector = MemoryProjector()
    service, repository = make_service(provider=provider, projector=projector)

    result = service.submit(
        payload=payload(),
        idempotency_key="preflight-inn-1",
        public_client_key="public-client-1",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-preflight",
    )

    assert result.record.preflight.decision is PreflightDecision.NORMAL
    assert result.record.preflight.identity_match is IdentityMatch.MATCH
    assert result.projection_status == "PROJECTED"
    assert projector.calls == [result.record.request_id]
    assert len(repository.outbox) == 1
    assert provider.calls == 1


def test_provider_unavailable_is_unknown_and_request_is_still_accepted() -> None:
    provider = FakeProvider(
        error=CounterpartyLookupProviderError(
            "PROVIDER_RATE_LIMIT",
            "provider busy",
            retryable=False,
        )
    )
    service, repository = make_service(provider=provider)

    result = service.submit(
        payload=payload(),
        idempotency_key="provider-off-1",
        public_client_key="public-client-2",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-provider-off",
    )

    assert result.record.status.value == "ACCEPTED"
    assert result.record.preflight.decision is PreflightDecision.UNKNOWN
    assert "PROVIDER_UNAVAILABLE" in result.record.preflight.flags
    assert any(item["event_type"] == "provider_unavailable" for item in repository.outbox)


def test_same_idempotency_key_converges_and_different_payload_fails_closed() -> None:
    service, repository = make_service(provider=None)

    first = service.submit(
        payload=payload(),
        idempotency_key="same-key-123",
        public_client_key="public-client-3",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-1",
    )
    second = service.submit(
        payload=payload(),
        idempotency_key="same-key-123",
        public_client_key="public-client-3",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-2",
    )

    assert second.deduplicated is True
    assert second.record.request_id == first.record.request_id
    assert len(repository.requests) == 1
    assert len(repository.outbox) == 1

    with pytest.raises(Exception, match="different payload"):
        service.submit(
            payload=payload(location="Москва, другой адрес"),
            idempotency_key="same-key-123",
            public_client_key="public-client-3",
            origin=None,
            bot_challenge_passed=False,
            correlation_id="corr-3",
        )


def test_submission_rate_limit_is_independent_from_lookup_budget() -> None:
    service, _ = make_service(submission_limit=1, lookup_limit=1)

    service.submit(
        payload=payload(inn=None),
        idempotency_key="limit-key-1",
        public_client_key="limited-client",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-limit-1",
    )

    from shema_platform.application.public_intake import PublicIntakeRateLimited

    with pytest.raises(PublicIntakeRateLimited, match="submission"):
        service.submit(
            payload=payload(inn=None),
            idempotency_key="limit-key-2",
            public_client_key="limited-client",
            origin=None,
            bot_challenge_passed=False,
            correlation_id="corr-limit-2",
        )


def test_honeypot_quarantines_without_operator_notification() -> None:
    service, repository = make_service()

    result = service.submit(
        payload=payload(),
        idempotency_key="spam-key-1",
        public_client_key="spam-client",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-spam",
        honeypot_value="bot-filled",
    )

    assert result.record.status.value == "QUARANTINED_SPAM"
    assert all(item["notify_operator"] is False for item in repository.outbox)


def test_shema_projection_failure_keeps_accepted_intake() -> None:
    projector = MemoryProjector(fail=True)
    service, repository = make_service(projector=projector, provider=None)

    result = service.submit(
        payload=payload(inn=None),
        idempotency_key="outage-key-1",
        public_client_key="outage-client",
        origin=None,
        bot_challenge_passed=False,
        correlation_id="corr-outage",
    )

    assert result.projection_status == "PENDING_PROJECTION"
    assert len(repository.requests) == 1
    stored = repository.get_by_idempotency_key("outage-key-1")
    assert stored is not None
    assert stored.projected_at is None


def test_public_api_accepts_without_auth_and_preserves_correlation() -> None:
    service, _ = make_service(provider=None)

    app = create_app(
        application=None,
        authenticator=PermissionedAuthenticator(),
        public_intake=service,
        bot_challenge_verifier=FakeBotChallengeVerifier(),
    )
    response = TestClient(app).post(
        "/v1/public/intake",
        headers={
            "Idempotency-Key": "api-intake-1",
            "Origin": "https://example.test",
            "X-Bot-Challenge": "passed",
            "X-Public-Client-Key": "attacker-controlled-key",
            "X-Correlation-Id": "corr-api-intake",
        },
        json={
            "serviceType": "Погрузка",
            "location": "Москва",
            "preferredDateOrPeriod": "2026-10-05",
            "workOrCargoDescription": "Погрузить оборудование",
            "contactName": "Иван Петров",
            "contactChannel": "+79990000000",
            "entrySurface": "public_web",
        },
    )

    assert response.status_code == 202
    assert response.headers["X-Correlation-Id"] != "corr-api-intake"
    assert response.json()["correlationId"] == response.headers["X-Correlation-Id"]


def test_public_api_rate_limit_ignores_caller_supplied_client_key() -> None:
    service, _ = make_service(provider=None, submission_limit=1)

    app = create_app(
        application=None,
        authenticator=PermissionedAuthenticator(),
        public_intake=service,
    )
    first = TestClient(app).post(
        "/v1/public/intake",
        headers={
            "Idempotency-Key": "api-rate-1",
            "Origin": "https://example.test",
            "X-Bot-Challenge": "passed",
            "X-Public-Client-Key": "attacker-key-a",
        },
        json={
            "serviceType": "Погрузка",
            "location": "Москва",
            "preferredDateOrPeriod": "2026-10-05",
            "workOrCargoDescription": "Погрузить оборудование",
            "contactName": "Иван Петров",
            "contactChannel": "+79990000000",
            "entrySurface": "public_web",
        },
    )
    second = TestClient(app).post(
        "/v1/public/intake",
        headers={
            "Idempotency-Key": "api-rate-2",
            "Origin": "https://example.test",
            "X-Bot-Challenge": "passed",
            "X-Public-Client-Key": "attacker-key-b",
        },
        json={
            "serviceType": "Погрузка",
            "location": "Москва",
            "preferredDateOrPeriod": "2026-10-05",
            "workOrCargoDescription": "Погрузить оборудование",
            "contactName": "Иван Петров",
            "contactChannel": "+79990000000",
            "entrySurface": "public_web",
        },
    )

    assert first.status_code == 202
    assert second.status_code == 429


def test_public_api_rejects_spoofed_bot_header_without_server_verifier() -> None:
    service, _ = make_service(provider=None)
    app = create_app(public_intake=service)
    response = TestClient(app).post(
        "/v1/public/intake",
        headers={
            "Idempotency-Key": "api-spoof-1",
            "Origin": "https://example.test",
            "X-Bot-Challenge": "passed",
        },
        json={
            "serviceType": "Погрузка",
            "location": "Москва",
            "preferredDateOrPeriod": "2026-10-05",
            "workOrCargoDescription": "Погрузить оборудование",
            "contactName": "Иван Петров",
            "contactChannel": "+79990000000",
        },
    )
    assert response.status_code == 400
    assert response.json()["code"] == "public_intake_security_rejected"


def test_public_api_default_edge_policy_rejects_missing_proof() -> None:
    service, _ = make_service(provider=None)
    app = create_app(public_intake=service)
    response = TestClient(app).post(
        "/v1/public/intake",
        headers={"Idempotency-Key": "api-default-1"},
        json={
            "serviceType": "Погрузка",
            "location": "Москва",
            "preferredDateOrPeriod": "2026-10-05",
            "workOrCargoDescription": "Погрузить оборудование",
            "contactName": "Иван Петров",
            "contactChannel": "+79990000000",
        },
    )
    assert response.status_code == 403


def test_operator_notification_center_requires_permission() -> None:
    class NoPermissionAuthenticator(AuthenticationPort):
        def authenticate(self, authorization: str | None) -> AuthenticatedActor:
            if authorization == "Bearer operator-token":
                return AuthenticatedActor("operator-1", trust_level=2)
            raise AuthenticationRequired()

    class Reader:
        def list_unread(self, *, limit):
            return ()

    app = create_app(
        application=None,
        authenticator=NoPermissionAuthenticator(),
        operator_notification_reader=Reader(),
    )
    response = TestClient(app).get(
        "/v1/operator/notifications",
        headers={"Authorization": "Bearer operator-token"},
    )

    assert response.status_code == 403


def test_operator_notification_center_returns_notifications() -> None:
    class Reader:
        def list_unread(self, *, limit):
            return (
                {
                    "eventId": "event-1",
                    "requestId": "request-1",
                    "eventType": "new_client_request",
                    "severity": "INFO",
                    "payload": {"requestId": "request-1"},
                    "createdAt": NOW.isoformat(),
                },
            )

    app = create_app(
        application=None,
        authenticator=PermissionedAuthenticator(),
        operator_notification_reader=Reader(),
    )
    response = TestClient(app).get(
        "/v1/operator/notifications",
        headers={"Authorization": "Bearer operator-token"},
    )

    assert response.status_code == 200
    body = OperatorNotificationListResponse.model_validate(response.json())
    assert body.notifications[0].event_id == "event-1"
