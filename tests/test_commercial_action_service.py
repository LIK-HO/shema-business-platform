import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.commercial_action import CommercialActionService
from shema_platform.domain.commercial_action import CommercialActionStatus
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.foundation.authorization import AuthorizationSubject, Permission, RBACAuthorizer
from shema_platform.foundation.errors import PolicyDenied, QuarantineRequired
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.policy import PolicyEngine


def make_service() -> CommercialActionService:
    return CommercialActionService(
        RBACAuthorizer(
            (
                AuthorizationSubject(
                    "operator-1",
                    frozenset({Permission.COMMERCIAL_ACTION_CREATE}),
                ),
            )
        ),
        PolicyEngine(),
        IdempotencyStore(),
    )


def verified_identity() -> Identity:
    return Identity(
        "identity-1",
        "ООО Альфа",
        IdentityState.VERIFIED,
        tax_id="7700000000",
    )


def test_create_ready_action_is_gated_and_idempotent() -> None:
    service = make_service()
    action = service.create_ready(
        action_id="action-1",
        actor=Actor("operator-1", trust_level=2),
        identity=verified_identity(),
        contact_ref="phone:+70000000000",
        channel="max",
        evidence_refs=("evidence:1",),
        request_hash="request-hash-1",
    )

    assert action.status is CommercialActionStatus.READY
    assert action.identity_id == "identity-1"


def test_create_ready_action_rejects_unverified_identity() -> None:
    with pytest.raises(QuarantineRequired):
        make_service().create_ready(
            action_id="action-1",
            actor=Actor("operator-1", trust_level=2),
            identity=Identity(
                "identity-1",
                "ООО Альфа",
                IdentityState.CANDIDATE,
                tax_id="7700000000",
            ),
            contact_ref="phone:+70000000000",
            channel="max",
            evidence_refs=("evidence:1",),
            request_hash="request-hash-1",
        )


def test_create_ready_action_rejects_missing_evidence() -> None:
    with pytest.raises(PolicyDenied, match="critical_claims_need_evidence"):
        make_service().create_ready(
            action_id="action-1",
            actor=Actor("operator-1", trust_level=2),
            identity=verified_identity(),
            contact_ref="phone:+70000000000",
            channel="max",
            evidence_refs=(),
            request_hash="request-hash-1",
        )
