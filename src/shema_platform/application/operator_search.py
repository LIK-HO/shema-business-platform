from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from shema_platform.application.search_planning import (
    RegistryBackedSearchPlanner,
    RegistrySearchPlan,
)
from shema_platform.application.search_run import (
    SearchBudget,
    SearchRun,
    SearchRunService,
    SearchSource,
)
from shema_platform.domain.search import SearchCriteria


@dataclass(frozen=True, slots=True)
class OperatorSearchResult:
    plan: RegistrySearchPlan
    run: SearchRun


class OperatorSearchService:
    """Compose registry-backed planning with bounded canonical search execution."""

    def __init__(
        self,
        planner: RegistryBackedSearchPlanner,
        runner: SearchRunService,
        adapters: Mapping[str, object],
        *,
        default_source_ids: Sequence[str] = (),
    ) -> None:
        self._planner = planner
        self._runner = runner
        self._adapters = dict(adapters)
        self._default_source_ids = tuple(default_source_ids)

    def execute(
        self,
        criteria: SearchCriteria,
        *,
        source_ids: Sequence[str] = (),
        budget: SearchBudget | None = None,
    ) -> OperatorSearchResult:
        requested = tuple(item.strip() for item in source_ids if item.strip())
        selected = requested or self._default_source_ids
        plan = self._planner.plan(criteria, selected, budget=budget)

        sources: list[SearchSource] = []
        missing: list[str] = []
        for planned_source in plan.sources:
            adapter = self._adapters.get(planned_source.source_id)
            if adapter is None:
                missing.append(planned_source.source_id)
                continue
            if not hasattr(adapter, "search"):
                raise TypeError(
                    f"search adapter for {planned_source.source_id!r} has no search method"
                )
            sources.append(
                SearchSource(
                    source_ref=planned_source.source_id,
                    provider=adapter,  # type: ignore[arg-type]
                )
            )

        if missing:
            raise ValueError(
                "search source adapter not configured: " + ", ".join(missing)
            )

        run = self._runner.execute(
            criteria,
            sources,
            budget=plan.budget,
        )
        return OperatorSearchResult(plan=plan, run=run)
