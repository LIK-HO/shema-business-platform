from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Any

from shema_platform.application.search_run import SearchBudget
from shema_platform.domain.search import SearchCriteria


@dataclass(frozen=True, slots=True)
class SearchRegistrySource:
    source_id: str
    name: str
    source_class: str
    reliability: str
    access_mode: str
    network_automation: bool


@dataclass(frozen=True, slots=True)
class RegistrySearchPlan:
    plan_version: str
    criteria: SearchCriteria
    sources: tuple[SearchRegistrySource, ...]
    budget: SearchBudget
    lawful_access_required: bool

    @property
    def source_ids(self) -> tuple[str, ...]:
        return tuple(source.source_id for source in self.sources)


class SearchSourceRegistry:
    """Validated in-memory view of the machine-readable intelligence source registry."""

    def __init__(
        self,
        sources: Sequence[SearchRegistrySource],
        *,
        lawful_access_required: bool,
    ) -> None:
        items = tuple(sources)
        ids = tuple(item.source_id for item in items)
        if len(ids) != len(set(ids)):
            raise ValueError("source_id values must be unique")
        if any(not item.source_id.strip() for item in items):
            raise ValueError("source_id is required")
        if any(item.network_automation for item in items):
            raise ValueError("network automation is disabled by the registry policy")
        self._sources = {item.source_id: item for item in items}
        self._lawful_access_required = lawful_access_required

    @classmethod
    def from_contract(cls, contract: Mapping[str, Any]) -> SearchSourceRegistry:
        policy = contract.get("policy")
        sources = contract.get("sources")
        if (
            not isinstance(policy, Mapping)
            or not isinstance(sources, Sequence)
            or isinstance(sources, (str, bytes))
        ):
            raise ValueError("source registry contract is malformed")
        if policy.get("network_execution_enabled") is not False:
            raise ValueError("registry policy must keep network execution disabled")
        if policy.get("source_provenance_operator_visible") is not True:
            raise ValueError("registry policy must expose source provenance")
        if policy.get("source_reliability_separate_from_claim_confidence") is not True:
            raise ValueError("registry policy must separate reliability from claim confidence")
        parsed = []
        for raw in sources:
            if not isinstance(raw, Mapping):
                raise ValueError("registry source entry is malformed")
            parsed.append(
                SearchRegistrySource(
                    source_id=str(raw.get("source_id", "")),
                    name=str(raw.get("name", "")),
                    source_class=str(raw.get("source_class", "")),
                    reliability=str(raw.get("default_reliability", "")),
                    access_mode=str(raw.get("access_mode", "")),
                    network_automation=bool(raw.get("network_automation")),
                )
            )
        return cls(
            parsed,
            lawful_access_required=bool(policy.get("lawful_access_required")),
        )

    def resolve(self, source_ids: Sequence[str]) -> tuple[SearchRegistrySource, ...]:
        normalized = tuple(item.strip() for item in source_ids if item.strip())
        if not normalized:
            raise ValueError("at least one source_id is required")
        if len(normalized) != len(set(normalized)):
            raise ValueError("source_id values must be unique in a search plan")
        missing = tuple(item for item in normalized if item not in self._sources)
        if missing:
            raise ValueError("unknown search source: " + ", ".join(missing))
        return tuple(self._sources[item] for item in normalized)

    @property
    def lawful_access_required(self) -> bool:
        return self._lawful_access_required


class RegistryBackedSearchPlanner:
    PLAN_VERSION = "search-plan:v1"

    def __init__(self, registry: SearchSourceRegistry) -> None:
        self._registry = registry

    def plan(
        self,
        criteria: SearchCriteria,
        source_ids: Sequence[str],
        *,
        budget: SearchBudget | None = None,
    ) -> RegistrySearchPlan:
        return RegistrySearchPlan(
            plan_version=self.PLAN_VERSION,
            criteria=criteria,
            sources=self._registry.resolve(source_ids),
            budget=budget or SearchBudget(),
            lawful_access_required=self._registry.lawful_access_required,
        )
