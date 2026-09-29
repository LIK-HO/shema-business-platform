from __future__ import annotations

from collections.abc import Callable

from shema_platform.application.ports import UnitOfWork
from shema_platform.application.resource_read_authorization import ResourceReadAuthorizer
from shema_platform.foundation.errors import AuthorizationError


class PostgresResourceReadAuthorizer(ResourceReadAuthorizer):
    """Authorize sensitive reads against canonical PostgreSQL ownership state.

    Economics currently use order_id as their entity_ref in Phase 3A. That
    relationship is enforced here rather than inferred from caller data.
    """

    def __init__(self, unit_of_work_factory: Callable[[], UnitOfWork]) -> None:
        self._unit_of_work_factory = unit_of_work_factory

    def require_order_read(self, *, order_id: str, actor_id: str) -> None:
        with self._unit_of_work_factory() as uow:
            order = uow.orders.get(order_id)
        if order is None:
            raise KeyError(f"unknown order: {order_id}")
        self._require_owner(
            owner_actor_id=order.owner_actor_id,
            actor_id=actor_id,
            resource_type="order",
            resource_id=order_id,
        )

    def require_economics_read(self, *, entity_ref: str, actor_id: str) -> None:
        with self._unit_of_work_factory() as uow:
            order = uow.orders.get(entity_ref)
            entries = uow.economics.list_for_entity(entity_ref)
        if order is None:
            raise KeyError(f"unknown economics resource: {entity_ref}")
        if any(entry.entity_ref != entity_ref for entry in entries):
            raise AuthorizationError("economic resource lineage mismatch")
        self._require_owner(
            owner_actor_id=order.owner_actor_id,
            actor_id=actor_id,
            resource_type="economics",
            resource_id=entity_ref,
        )

    @staticmethod
    def _require_owner(
        *,
        owner_actor_id: str | None,
        actor_id: str,
        resource_type: str,
        resource_id: str,
    ) -> None:
        if not owner_actor_id or owner_actor_id != actor_id:
            raise AuthorizationError(
                f"{resource_type} resource is outside the actor resource scope: "
                f"{resource_id}"
            )
