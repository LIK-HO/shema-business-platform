from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from types import MappingProxyType


class ProviderNotConfigured(RuntimeError):
    """Production provider binding is missing."""


@dataclass(frozen=True, slots=True)
class ProviderRegistry[ProviderT]:
    providers: Mapping[str, ProviderT]

    def __post_init__(self) -> None:
        normalized = {
            key.strip(): value
            for key, value in self.providers.items()
            if key.strip()
        }
        object.__setattr__(
            self,
            "providers",
            MappingProxyType(normalized),
        )

    def get(self, provider: str) -> ProviderT:
        name = provider.strip()
        if not name:
            raise ProviderNotConfigured("provider name is required")
        adapter = self.providers.get(name)
        if adapter is None:
            raise ProviderNotConfigured(
                f"provider is not configured: {name}"
            )
        return adapter

    def require_for_production(self, provider: str) -> ProviderT:
        return self.get(provider)
