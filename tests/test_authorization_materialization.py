from shema_platform.foundation.authentication import AuthenticatedActor
from shema_platform.foundation.authorization import AuthorizationMaterializer, Permission


def test_authorization_materializer_maps_roles_and_scopes_to_explicit_permissions() -> None:
    actor = AuthenticatedActor(
        "operator-1",
        trust_level=2,
        roles=("dispatcher",),
        scopes=("orders:write",),
    )

    subject = AuthorizationMaterializer(
        role_permissions={
            "dispatcher": frozenset({Permission.ORDER_CREATE}),
        },
        scope_permissions={
            "orders:write": frozenset({Permission.ORDER_CREATE}),
        },
    ).materialize(actor)

    assert subject.actor_id == "operator-1"
    assert subject.permissions == frozenset({Permission.ORDER_CREATE})


def test_unknown_iam_attributes_grant_no_permissions() -> None:
    actor = AuthenticatedActor(
        "operator-1",
        trust_level=2,
        roles=("unknown-role",),
        scopes=("unknown:scope",),
    )

    subject = AuthorizationMaterializer(
        role_permissions={},
        scope_permissions={},
    ).materialize(actor)

    assert subject.permissions == frozenset()
