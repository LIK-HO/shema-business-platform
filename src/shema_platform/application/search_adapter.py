from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from shema_platform.application.search_planning import SearchRegistrySource
from shema_platform.application.search_run import SearchProvider, SearchSource


class SearchAdapterComplianceError(ValueError):
    """Raised when a search adapter violates the registry compliance boundary."""


class SearchAdapter(Protocol):
    def search(self, criteria): ...


@dataclass(frozen=True, slots=True)
class SearchAdapterDescriptor:
    source_id: str
    source_class: str
    reliability: str
    access_mode: str
    network_execution_enabled: bool = False
    lawful_access_confirmed: bool = False

    def __post_init__(self) -> None:
        for name, value in (
            ("source_id", self.source_id),
            ("source_class", self.source_class),
            ("reliability", self.reliability),
            ("access_mode", self.access_mode),
        ):
            if not value.strip():
                raise SearchAdapterComplianceError(f"{name} is required")


@dataclass(frozen=True, slots=True)
class CompliantSearchAdapter:
    source: SearchRegistrySource
    descriptor: SearchAdapterDescriptor
    adapter: SearchProvider

    def search_source(self) -> SearchSource:
        validate_search_adapter(
            self.source,
            self.descriptor,
            self.adapter,
            lawful_access_required=True,
        )
        return SearchSource(
            source_ref=self.source.source_id,
            provider=self.adapter,
        )


def validate_search_adapter(
    source: SearchRegistrySource,
    descriptor: SearchAdapterDescriptor,
    adapter: object,
    *,
    lawful_access_required: bool,
) -> None:
    if source.source_id != descriptor.source_id:
        raise SearchAdapterComplianceError("source_id does not match registry source")
    if source.source_class != descriptor.source_class:
        raise SearchAdapterComplianceError("source_class does not match registry source")
    if source.reliability != descriptor.reliability:
        raise SearchAdapterComplianceError("reliability does not match registry source")
    if source.access_mode != descriptor.access_mode:
        raise SearchAdapterComplianceError("access_mode does not match registry source")
    if source.network_automation:
        raise SearchAdapterComplianceError(
            "registry source cannot permit network automation"
        )
    if descriptor.network_execution_enabled:
        raise SearchAdapterComplianceError(
            "adapter network execution must remain disabled"
        )
    if lawful_access_required and not descriptor.lawful_access_confirmed:
        raise SearchAdapterComplianceError(
            "lawful access must be explicitly confirmed"
        )
    search = getattr(adapter, "search", None)
    if not callable(search):
        raise SearchAdapterComplianceError(
            "search adapter must expose a callable search method"
        )
