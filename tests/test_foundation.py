from datetime import datetime, timezone

import pytest

from shema_platform.application.commands import Actor, CommercialActionCommand, CommandService
from shema_platform.domain.identity import Identity, IdentityState, Resolution
from shema_platform.foundation.evidence import Evidence, TruthClass, TrustLevel
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.policy import PolicyEngine


def test_verified_identity_can_resolve_merge() -> None:
    left = Identity("1", "ООО Альфа", IdentityState.VERIFIED, tax_id="7700000000")
    right = Identity("2", "ООО Альфа", IdentityState.CANDIDATE, tax_id="7700000000")
    assert left.resolve_with(right) is Resolution.MERGE


def test_conflicting_tax_ids_require_review() -> None:
    left = Identity("1", "Альфа", IdentityState.VERIFIED, tax_id="7700000000")
    right = Identity("2", "Альфа", IdentityState.CANDIDATE, tax_id="7800000000")
    assert left.resolve_with(right) is Resolution.MANUAL_REVIEW


def test_evidence_rejects_invalid_confidence() -> None:
    with pytest.raises(ValueError):
        Evidence(
            evidence_id="e1", subject_ref="identity:1", claim="Claim",
            source_ref="source:1",
            observed_at=datetime.now(timezone.utc),
            captured_at=datetime.now(timezone.utc),
            truth_class=TruthClass.FACT, trust_level=TrustLevel.T2_VERIFIED,
            confidence=1.5,
        )


def test_critical_action_requires_trust_and_evidence() -> None:
    service = CommandService(PolicyEngine(), IdempotencyStore())
    command = CommercialActionCommand(
        command_id="cmd-1", actor=Actor("operator-1", trusted_level=2),
        identity_id="identity-1", evidence_level=2, request_hash="hash-1",
    )
    assert service.execute(command) == "identity-1"


def test_idempotency_replays_same_result() -> None:
    store = IdempotencyStore()
    first = store.reserve("k1", "h1", "result-1")
    second = store.reserve("k1", "h1", "result-1")
    assert first == second
    assert second.result_ref == "result-1"


def test_policy_denies_untrusted_actor() -> None:
    service = CommandService(PolicyEngine(), IdempotencyStore())
    command = CommercialActionCommand(
        command_id="cmd-1", actor=Actor("operator-1", trusted_level=1),
        identity_id="identity-1", evidence_level=2, request_hash="hash-1",
    )
    with pytest.raises(Exception):
        service.execute(command)
