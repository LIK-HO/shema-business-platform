from __future__ import annotations

from dataclasses import dataclass

from shema_platform.application.identity import IdentityDirectory, IdentityMatch, IdentityResolution
from shema_platform.domain.identity import Identity, IdentityState
from shema_platform.domain.qualification import (
    QualificationDecision,
    QualificationInput,
    QualificationService,
)
from shema_platform.domain.search import SearchHit


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    candidate_ref: str
    identity: Identity | None
    identity_resolution: IdentityResolution
    qualification: QualificationDecision


class DiscoveryService:
    """Compose search output, identity resolution and conservative qualification."""

    def __init__(
        self,
        identity_directory: IdentityDirectory,
        qualification_service: QualificationService,
    ) -> None:
        self._identities = identity_directory
        self._qualification = qualification_service

    def process(
        self,
        hit: SearchHit,
        *,
        evidence_level: int,
        service_fit: bool,
        economic_fit: bool,
    ) -> DiscoveryResult:
        if hit.tax_id:
            provisional = Identity(
                identity_id=hit.candidate_ref,
                canonical_name=hit.name,
                state=IdentityState.IDENTIFIED,
                tax_id=hit.tax_id,
                registration_id=hit.registration_id,
            )
            resolution = self._identities.resolve(provisional)

            if resolution.match is IdentityMatch.NEW:
                identity = self._identities.register(provisional)
            elif resolution.existing_identity_ids:
                identity = next(
                    item
                    for item in self._identities.all()
                    if item.identity_id == resolution.existing_identity_ids[0]
                )
            else:
                identity = None
        else:
            identity = None
            resolution = self._identities.resolve(
                Identity(
                    identity_id=hit.candidate_ref,
                    canonical_name=hit.name,
                    state=IdentityState.RAW,
                )
            )

        verified = identity is not None and identity.state in {
            IdentityState.VERIFIED,
            IdentityState.ACTIVE,
        }
        qualification = self._qualification.evaluate(
            QualificationInput(
                identity_verified=verified,
                contact_available=bool(hit.contact_refs),
                service_fit=service_fit,
                evidence_level=evidence_level,
                economic_fit=economic_fit,
            )
        )
        return DiscoveryResult(
            candidate_ref=hit.candidate_ref,
            identity=identity,
            identity_resolution=resolution,
            qualification=qualification,
        )
