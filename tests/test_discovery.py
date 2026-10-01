from shema_platform.application.discovery import DiscoveryService
from shema_platform.application.identity import IdentityDirectory
from shema_platform.domain.identity import Identity, IdentityState, Resolution
from shema_platform.domain.qualification import QualificationService, QualificationStatus
from shema_platform.domain.search import SearchHit


def test_new_candidate_is_registered_but_not_qualified() -> None:
    service = DiscoveryService(IdentityDirectory(), QualificationService())

    result = service.process(
        SearchHit(
            candidate_ref="candidate-1",
            name="ООО Альфа",
            region="Moscow",
            industries=frozenset({"logistics"}),
            source_ref="source:1",
            tax_id="7700000000",
            contact_refs=("phone:+70000000000",),
        ),
        evidence_level=3,
        service_fit=True,
        economic_fit=True,
    )

    assert result.identity is not None
    assert result.identity.state is IdentityState.IDENTIFIED
    assert result.identity_resolution.resolution is Resolution.KEEP_SEPARATE
    assert result.qualification.status is QualificationStatus.REVIEW
    assert "identity_not_verified" in result.qualification.reasons


def test_verified_existing_identity_can_be_qualified_with_contact_and_fit() -> None:
    directory = IdentityDirectory(
        (
            Identity(
                "identity-1",
                "ООО Альфа",
                IdentityState.VERIFIED,
                tax_id="7700000000",
            ),
        )
    )
    service = DiscoveryService(directory, QualificationService())

    result = service.process(
        SearchHit(
            candidate_ref="candidate-1",
            name="ООО Альфа",
            region="Moscow",
            industries=frozenset({"logistics"}),
            source_ref="source:1",
            tax_id="7700000000",
            contact_refs=("phone:+70000000000",),
        ),
        evidence_level=2,
        service_fit=True,
        economic_fit=True,
    )

    assert result.identity is not None
    assert result.identity.identity_id == "identity-1"
    assert result.identity_resolution.resolution is Resolution.MERGE
    assert result.qualification.status is QualificationStatus.QUALIFIED
