import pytest

from shema_platform.application.research_routing import (
    ResearchDepth,
    ResearchRoute,
    ResearchRoutingPolicy,
    SourceRequirement,
    SourceRule,
)


def policy() -> ResearchRoutingPolicy:
    return ResearchRoutingPolicy(
        (
            ResearchRoute(
                "logistics",
                ResearchDepth.R1_IDENTITY,
                (
                    SourceRule("official_registry", SourceRequirement.REQUIRED),
                    SourceRule("social_profile", SourceRequirement.PROHIBITED),
                ),
            ),
            ResearchRoute(
                "logistics",
                ResearchDepth.R2_CONTEXT,
                (
                    SourceRule("official_registry", SourceRequirement.REQUIRED),
                    SourceRule("company_site", SourceRequirement.REQUIRED),
                    SourceRule("industry_source", SourceRequirement.OPTIONAL),
                ),
            ),
        )
    )


def test_routing_exposes_required_and_allowed_sources() -> None:
    route = policy().route(" Logistics ", ResearchDepth.R2_CONTEXT)

    assert route.required_source_classes() == frozenset(
        {"official_registry", "company_site"}
    )
    assert route.allowed_source_classes() == frozenset(
        {"official_registry", "company_site", "industry_source"}
    )


def test_routing_prohibits_explicit_source_class() -> None:
    route = policy().route("logistics", ResearchDepth.R1_IDENTITY)

    assert route.is_prohibited("social_profile")
    assert "social_profile" not in route.allowed_source_classes()


def test_routing_fails_closed_for_unknown_route() -> None:
    with pytest.raises(KeyError, match="no research route"):
        policy().route("unknown", ResearchDepth.R4_DEEP)
