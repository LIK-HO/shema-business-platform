from __future__ import annotations

from typing import Protocol


class ResourceReadAuthorizer(Protocol):
    """Server-side resource-scope gate executed after permission checks."""

    def require_order_read(self, *, order_id: str, actor_id: str) -> None: ...

    def require_economics_read(self, *, entity_ref: str, actor_id: str) -> None: ...
