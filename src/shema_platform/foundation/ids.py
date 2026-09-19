from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID, uuid4


@dataclass(frozen=True, slots=True)
class Id:
    """Strongly typed UUID wrapper for domain identifiers."""

    value: UUID

    @classmethod
    def new(cls) -> Id:
        return cls(uuid4())

    @classmethod
    def parse(cls, value: str | UUID) -> Id:
        return cls(value if isinstance(value, UUID) else UUID(value))

    def __str__(self) -> str:
        return str(self.value)
