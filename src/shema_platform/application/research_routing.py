from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


class ResearchDepth(StrEnum):
    R1_IDENTITY = "R1"
    R2_CONTEXT = "R2"
    R3_REPUTATION = "R3"
    R4_DEEP = "R4"


class SourceRequirement(StrEnum):
    REQUIRED = "required"
    OPTIONAL = "optional"
    PROHIBITED = "prohibited"


@dataclass(frozen=True, slots=True)
class SourceRule:
    source_class: str
    requirement: SourceRequirement


@dataclass(frozen=True, slots=True)
class ResearchRoute:
    company_type: str
    depth: ResearchDepth
    rules: tuple[SourceRule, ...]

    def allowed_source_classes(self) -> frozenset[str]:
        return frozenset(
            rule.source_class
            for rule in self.rules
            if rule.requirement is not SourceRequirement.PROHIBITED
        )

    def required_source_classes(self) -> frozenset[str]:
        return frozenset(
            rule.source_class
            for rule in self.rules
            if rule.requirement is SourceRequirement.REQUIRED
        )

    def is_prohibited(self, source_class: str) -> bool:
        return any(
            rule.source_class == source_class
            and rule.requirement is SourceRequirement.PROHIBITED
            for rule in self.rules
        )


class ResearchRoutingPolicy:
    """Declarative R1-R4 source-routing boundary.

    Rules are configuration, not provider implementation. This allows source
    providers to change without changing the domain semantics of research depth.
    """

    def __init__(self, routes: tuple[ResearchRoute, ...]) -> None:
        self._routes = {
            (route.company_type.strip().lower(), route.depth): route for route in routes
        }

    def route(self, company_type: str, depth: ResearchDepth) -> ResearchRoute:
        key = (company_type.strip().lower(), depth)
        try:
            return self._routes[key]
        except KeyError as exc:
            raise KeyError(
                f"no research route for company_type={company_type!r} depth={depth.value}"
            ) from exc
