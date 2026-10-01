from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace

from fastapi.testclient import TestClient

from shema_platform.experience.api import create_app
from shema_platform.foundation.authentication import (
    AuthenticatedActor,
    AuthenticationPort,
    AuthenticationRequired,
)
from shema_platform.foundation.authorization import Permission


class Authenticator(AuthenticationPort):
    def authenticate(self, authorization: str | None) -> AuthenticatedActor:
        if authorization == "Bearer operator-token":
            return AuthenticatedActor(
                "operator-1",
                trust_level=2,
                permissions=frozenset(
                    {
                        Permission.COUNTERPARTY_MONITOR_MANAGE,
                        Permission.COUNTERPARTY_FAVORITE_MANAGE,
                    }
                ),
            )
        if authorization == "Bearer readonly-token":
            return AuthenticatedActor(
                "operator-2",
                trust_level=2,
                permissions=frozenset({Permission.COUNTERPARTY_CHECK}),
            )
        raise AuthenticationRequired()


class FakeMonitoringService:
    def __init__(self):
        now = datetime(2026, 9, 29, 14, tzinfo=UTC)
        self.monitor = SimpleNamespace(
            monitor_id="monitor-api-1",
            actor_id="operator-1",
            identifier_type=type("IdentifierType", (), {"value": "INN"})(),
            identifier="7707083893",
            status=type("Status", (), {"value": "active"})(),
            next_check_at=now,
            last_checked_at=None,
        )
        self.favorite = SimpleNamespace(
            favorite_id="favorite-api-1",
            actor_id="operator-1",
            identifier_type=type("IdentifierType", (), {"value": "INN"})(),
            identifier="7707083893",
            created_at=now,
        )

    def save_monitoring(self, **kwargs):
        return self.monitor

    def list_monitors(self, actor_id, permissions):
        return (self.monitor,)

    def save_favorite(self, **kwargs):
        return self.favorite

    def list_favorites(self, actor_id, permissions):
        return (self.favorite,)


def client() -> TestClient:
    return TestClient(
        create_app(
            application=None,
            authenticator=Authenticator(),
            counterparty_monitoring=FakeMonitoringService(),
        )
    )


def test_counterparty_monitoring_requires_explicit_permission():
    response = client().post(
        "/v1/intelligence/counterparties/monitoring",
        headers={
            "Authorization": "Bearer readonly-token",
            "Idempotency-Key": "monitor-api-denied",
        },
        json={"identifierType": "INN", "identifier": "7707083893"},
    )
    assert response.status_code == 403


def test_counterparty_monitoring_and_favorite_routes_are_scoped():
    test_client = client()

    monitoring = test_client.post(
        "/v1/intelligence/counterparties/monitoring",
        headers={
            "Authorization": "Bearer operator-token",
            "Idempotency-Key": "monitor-api-1",
        },
        json={"identifierType": "INN", "identifier": "7707083893"},
    )
    assert monitoring.status_code == 200
    assert monitoring.json()["monitorId"] == "monitor-api-1"

    favorites = test_client.post(
        "/v1/intelligence/counterparties/favorites",
        headers={
            "Authorization": "Bearer operator-token",
            "Idempotency-Key": "favorite-api-1",
        },
        json={"identifierType": "INN", "identifier": "7707083893"},
    )
    assert favorites.status_code == 200
    assert favorites.json()["favoriteId"] == "favorite-api-1"

    listed = test_client.get(
        "/v1/intelligence/counterparties/monitoring",
        headers={"Authorization": "Bearer operator-token"},
    )
    assert listed.status_code == 200
    assert listed.json()["monitors"][0]["identifier"] == "7707083893"

    favorite_list = test_client.get(
        "/v1/intelligence/counterparties/favorites",
        headers={"Authorization": "Bearer operator-token"},
    )
    assert favorite_list.status_code == 200
    assert favorite_list.json()["favorites"][0]["identifier"] == "7707083893"
