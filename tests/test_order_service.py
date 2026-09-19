import pytest
from decimal import Decimal

from shema_platform.application.commands import Actor
from shema_platform.application.order import OrderService
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.domain.money import Money
from shema_platform.domain.order import OrderLine
from shema_platform.foundation.authorization import AuthorizationSubject, Permission, RBACAuthorizer
from shema_platform.foundation.errors import PolicyDenied, QuarantineRequired
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.policy import PolicyEngine


def service() -> OrderService:
    return OrderService(
        RBACAuthorizer(
            (
                AuthorizationSubject(
                    "operator-1",
                    frozenset({Permission.ORDER_CREATE}),
                ),
            )
        ),
        PolicyEngine(),
        IdempotencyStore(),
    )


def sent_action() -> CommercialAction:
    return CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="chat:42",
        channel="max",
        evidence_refs=("evidence:1",),
    ).mark_ready().mark_sent()


def line() -> OrderLine:
    return OrderLine("line-1", "Погрузка", Decimal("2"), Money(1500, "RUB"))


def actor(trust_level: int = 2) -> Actor:
    return Actor("operator-1", trust_level=trust_level)


def test_order_can_be_created_from_sent_action() -> None:
    order = service().create_from_action(
        order_id="order-1",
        actor=actor(),
        action=sent_action(),
        lines=(line(),),
        request_hash="hash-1",
    )

    assert order.identity_id == "identity-1"
    assert order.source_action_id == "action-1"
    assert order.lines == (line(),)


def test_order_rejects_unsent_action() -> None:
    action = CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="chat:42",
        channel="max",
        evidence_refs=("evidence:1",),
    ).mark_ready()

    with pytest.raises(QuarantineRequired, match="sent or completed"):
        service().create_from_action(
            order_id="order-1",
            actor=actor(),
            action=action,
            lines=(line(),),
            request_hash="hash-1",
        )


def test_order_requires_permission_before_policy() -> None:
    no_permission = OrderService(
        RBACAuthorizer(),
        PolicyEngine(),
        IdempotencyStore(),
    )

    with pytest.raises(Exception, match="permission denied"):
        no_permission.create_from_action(
            order_id="order-1",
            actor=actor(),
            action=sent_action(),
            lines=(line(),),
            request_hash="hash-1",
        )


def test_order_rejects_untrusted_actor() -> None:
    with pytest.raises(PolicyDenied, match="actor_not_trusted"):
        service().create_from_action(
            order_id="order-1",
            actor=actor(trust_level=1),
            action=sent_action(),
            lines=(line(),),
            request_hash="hash-1",
        )
