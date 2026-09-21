from shema_platform.domain.qualification import (
    QualificationInput,
    QualificationService,
    QualificationStatus,
)


def test_unverified_identity_cannot_be_silently_qualified() -> None:
    decision = QualificationService().evaluate(
        QualificationInput(
            identity_verified=False,
            contact_available=True,
            service_fit=True,
            evidence_level=3,
            economic_fit=True,
        )
    )

    assert decision.status is QualificationStatus.REVIEW
    assert "identity_not_verified" in decision.reasons


def test_missing_contact_stays_in_review() -> None:
    decision = QualificationService().evaluate(
        QualificationInput(
            identity_verified=True,
            contact_available=False,
            service_fit=True,
            evidence_level=2,
            economic_fit=True,
        )
    )

    assert decision.status is QualificationStatus.REVIEW
    assert "contact_unavailable" in decision.reasons


def test_complete_candidate_can_be_qualified() -> None:
    decision = QualificationService().evaluate(
        QualificationInput(
            identity_verified=True,
            contact_available=True,
            service_fit=True,
            evidence_level=2,
            economic_fit=True,
        )
    )

    assert decision.status is QualificationStatus.QUALIFIED
    assert decision.reasons == ()
