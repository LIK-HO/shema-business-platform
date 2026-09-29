from __future__ import annotations

import pytest

from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import AuthorizationError


@pytest.mark.parametrize(
    ("granted", "forbidden"),
    (
        (
            frozenset({Permission.COMMERCIAL_ACTION_CREATE, Permission.ORDER_READ}),
            Permission.COMMERCIAL_ACTION_SEND,
        ),
        (
            frozenset(
                {
                    Permission.INTELLIGENCE_PROVIDER_ACTIVATE,
                    Permission.INTELLIGENCE_PROVIDER_LOOKUP,
                }
            ),
            Permission.INTELLIGENCE_PROVIDER_ROLLBACK,
        ),
        (
            frozenset({Permission.ORDER_READ, Permission.ECONOMICS_READ}),
            Permission.ORDER_CREATE,
        ),
        (
            frozenset({Permission.PUBLIC_INTAKE_REVIEW, Permission.DIAGNOSTICS_READ}),
            Permission.AI_RUN,
        ),
    ),
)
def test_permission_combinations_do_not_imply_ungranted_capability(
    granted: frozenset[Permission],
    forbidden: Permission,
) -> None:
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                actor_id="operator-1",
                permissions=granted,
            ),
        )
    )

    with pytest.raises(AuthorizationError, match="permission denied"):
        authorizer.require("operator-1", forbidden)
