from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from math import isfinite
from typing import Sequence
from uuid import uuid4

from shema_platform.domain.search import SearchCriteria, SearchHit, SearchProvider, SearchService


class SearchCompleteness(StrEnum):
    NOT_SEARCHED = "NOT_SEARCHED"
    SEARCHED_NOT_FOUND = "SEARCHED_NOT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    BUDGET_LIMITED = "BUDGET_LIMITED"
    COMPLETE = "COMPLETE"


class SearchSourceStatus(StrEnum):
    SEARCHED = "SEARCHED"
    SEARCHED_NOT_FOUND = "SEARCHED_NOT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    BUDGET_LIMITED = "BUDGET_LIMITED"


class SearchSourceUnavailable(RuntimeError):
    """A source was configured but could not safely return a search result."""


@dataclass(frozen=True, slots=True)
class SearchBudget:
    max_sources: int = 8
    max_candidates: int = 500

    def __post_init__(self) -> None:
        if self.max_sources < 1:
            raise ValueError("max_sources must be at least 1")
        if self.max_candidates < 1:
            raise ValueError("max_candidates must be at least 1")


@dataclass(frozen=True, slots=True)
class SearchSource:
    source_ref: str
    provider: SearchProvider

    def __post_init__(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")


@dataclass(frozen=True, slots=True)
class SearchPlan:
    plan_version: str
    criteria: SearchCriteria
    source_refs: tuple[str, ...]
    budget: SearchBudget

    def __post_init__(self) -> None:
        if not self.plan_version.strip():
            raise ValueError("plan_version is required")
        if len(self.source_refs) != len(set(self.source_refs)):
            raise ValueError("source_refs must be unique")


@dataclass(frozen=True, slots=True)
class SearchSourceAttempt:
    source_ref: str
    status: SearchSourceStatus
    candidate_count: int = 0
    error_code: str | None = None

    def __post_init__(self) -> None:
        if not self.source_ref.strip():
            raise ValueError("source_ref is required")
        if self.candidate_count < 0:
            raise ValueError("candidate_count cannot be negative")
        if self.status is SearchSourceStatus.SOURCE_UNAVAILABLE and not self.error_code:
            raise ValueError("SOURCE_UNAVAILABLE requires error_code")
        if self.status is not SearchSourceStatus.SOURCE_UNAVAILABLE and self.error_code:
            raise ValueError("error_code is only valid for SOURCE_UNAVAILABLE")


@dataclass(frozen=True, slots=True)
class SearchRun:
    run_id: str
    plan: SearchPlan
    hits: tuple[SearchHit, ...]
    attempts: tuple[SearchSourceAttempt, ...]
    completeness: SearchCompleteness

    def __post_init__(self) -> None:
        if not self.run_id.strip():
            raise ValueError("run_id is required")
        if len(self.attempts) > len(self.plan.source_refs):
            raise ValueError("attempt count cannot exceed planned source count")


@dataclass(frozen=True, slots=True)
class SearchQualityMetrics:
    precision: float
    recall: float
    source_coverage: float

    def __post_init__(self) -> None:
        for name, value in (
            ("precision", self.precision),
            ("recall", self.recall),
            ("source_coverage", self.source_coverage),
        ):
            if not isfinite(value) or not 0.0 <= value <= 1.0:
                raise ValueError(f"{name} must be finite and between 0 and 1")

    def as_dict(self) -> dict[str, float]:
        return {
            "precision": self.precision,
            "recall": self.recall,
            "source_coverage": self.source_coverage,
        }


@dataclass(frozen=True, slots=True)
class _CollectedSearchProvider(SearchProvider):
    hits: tuple[SearchHit, ...]

    def search(self, criteria: SearchCriteria) -> tuple[SearchHit, ...]:
        return self.hits


def evaluate_search_quality(
    expected_candidate_refs: Sequence[str],
    actual_hits: Sequence[SearchHit],
    *,
    planned_source_count: int,
    searched_source_count: int,
) -> SearchQualityMetrics:
    if planned_source_count < 1:
        raise ValueError("planned_source_count must be at least 1")
    if not 0 <= searched_source_count <= planned_source_count:
        raise ValueError("searched_source_count must be within planned source count")

    expected = {ref.strip() for ref in expected_candidate_refs if ref.strip()}
    actual = {hit.candidate_ref.strip() for hit in actual_hits if hit.candidate_ref.strip()}
    true_positive = len(expected.intersection(actual))

    if actual:
        precision = true_positive / len(actual)
    else:
        precision = 1.0 if not expected else 0.0

    recall = true_positive / len(expected) if expected else 1.0
    source_coverage = searched_source_count / planned_source_count

    return SearchQualityMetrics(
        precision=precision,
        recall=recall,
        source_coverage=source_coverage,
    )


class SearchRunService:
    """Bounded application search orchestration with explicit completeness."""

    PLAN_VERSION = "search-run:v1"

    def execute(
        self,
        criteria: SearchCriteria,
        sources: Sequence[SearchSource],
        *,
        budget: SearchBudget | None = None,
    ) -> SearchRun:
        effective_budget = budget or SearchBudget()
        source_tuple = tuple(sources)

        plan = SearchPlan(
            plan_version=self.PLAN_VERSION,
            criteria=criteria,
            source_refs=tuple(source.source_ref for source in source_tuple),
            budget=effective_budget,
        )

        if not source_tuple:
            return SearchRun(
                run_id=str(uuid4()),
                plan=plan,
                hits=(),
                attempts=(),
                completeness=SearchCompleteness.NOT_SEARCHED,
            )

        attempts: list[SearchSourceAttempt] = []
        collected_hits: list[SearchHit] = []
        remaining_candidates = effective_budget.max_candidates

        for index, source in enumerate(source_tuple):
            if index >= effective_budget.max_sources or remaining_candidates <= 0:
                attempts.extend(
                    SearchSourceAttempt(
                        source_ref=remaining_source.source_ref,
                        status=SearchSourceStatus.BUDGET_LIMITED,
                    )
                    for remaining_source in source_tuple[index:]
                )
                break

            try:
                hits = tuple(source.provider.search(criteria))
            except (SearchSourceUnavailable, TimeoutError) as exc:
                attempts.append(
                    SearchSourceAttempt(
                        source_ref=source.source_ref,
                        status=SearchSourceStatus.SOURCE_UNAVAILABLE,
                        error_code=type(exc).__name__,
                    )
                )
                continue

            capped_hits = hits[:remaining_candidates]
            collected_hits.extend(capped_hits)
            remaining_candidates -= len(capped_hits)

            attempts.append(
                SearchSourceAttempt(
                    source_ref=source.source_ref,
                    status=(
                        SearchSourceStatus.SEARCHED
                        if capped_hits
                        else SearchSourceStatus.SEARCHED_NOT_FOUND
                    ),
                    candidate_count=len(capped_hits),
                )
            )

            if remaining_candidates <= 0 and index + 1 < len(source_tuple):
                attempts.extend(
                    SearchSourceAttempt(
                        source_ref=remaining_source.source_ref,
                        status=SearchSourceStatus.BUDGET_LIMITED,
                    )
                    for remaining_source in source_tuple[index + 1 :]
                )
                break

        hits = SearchService(_CollectedSearchProvider(tuple(collected_hits))).execute(criteria)
        statuses = {attempt.status for attempt in attempts}

        if SearchSourceStatus.BUDGET_LIMITED in statuses:
            completeness = SearchCompleteness.BUDGET_LIMITED
        elif SearchSourceStatus.SOURCE_UNAVAILABLE in statuses:
            completeness = SearchCompleteness.SOURCE_UNAVAILABLE
        elif not hits:
            completeness = SearchCompleteness.SEARCHED_NOT_FOUND
        else:
            completeness = SearchCompleteness.COMPLETE

        return SearchRun(
            run_id=str(uuid4()),
            plan=plan,
            hits=hits,
            attempts=tuple(attempts),
            completeness=completeness,
        )
