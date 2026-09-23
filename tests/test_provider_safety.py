import pytest

from shema_platform.adapters.communication.max import MaxAdapter
from shema_platform.adapters.communication.safety import (
    ExternalEffectSafety,
    SafeCommunicationAdapter,
    require_safe_external_effect,
)
from shema_platform.application.communication import CommunicationSendRequest
from shema_platform.foundation.errors import QuarantineRequired


def request() -> CommunicationSendRequest:
    return CommunicationSendRequest(
        action_id="action-1",
        channel="max",
        contact_ref="chat:42",
        body="Здравствуйте",
        idempotency_key="commercial-send:action-1",
    )


def test_provider_is_safe_when_idempotency_is_proven() -> None:
    safety = ExternalEffectSafety(
        provider="test-provider",
        supports_idempotency=True,
        supports_reconciliation=False,
        evidence_ref="test-proof:idempotency",
    )

    require_safe_external_effect(safety)


def test_provider_is_safe_when_reconciliation_is_proven() -> None:
    safety = ExternalEffectSafety(
        provider="test-provider",
        supports_idempotency=False,
        supports_reconciliation=True,
        evidence_ref="test-proof:reconciliation",
    )

    require_safe_external_effect(safety)


def test_provider_without_safety_proof_fails_closed() -> None:
    safety = ExternalEffectSafety(
        provider="max",
        supports_idempotency=False,
        supports_reconciliation=False,
        evidence_ref="max:published-api-contract:2026-09-23",
    )

    with pytest.raises(
        QuarantineRequired,
        match="not certified for crash-safe retry",
    ):
        require_safe_external_effect(safety)


def test_safe_adapter_delegates_only_after_capability_gate() -> None:
    adapter = SafeCommunicationAdapter(
        MaxAdapter(),
        ExternalEffectSafety(
            provider="deterministic-test",
            supports_idempotency=True,
            supports_reconciliation=False,
            evidence_ref="test-proof:deterministic-idempotency",
        ),
    )

    result = adapter.send(request())

    assert result.accepted is True
    assert result.external_message_id == "max:commercial-send:action-1"


def test_safe_adapter_rejects_uncertified_provider_during_composition() -> None:
    with pytest.raises(
        QuarantineRequired,
        match="not certified for crash-safe retry",
    ):
        SafeCommunicationAdapter(
            MaxAdapter(),
            ExternalEffectSafety(
                provider="max",
                supports_idempotency=False,
                supports_reconciliation=False,
                evidence_ref="max:published-api-contract:2026-09-23",
            ),
        )


def test_safety_requires_evidence_reference() -> None:
    with pytest.raises(ValueError, match="evidence_ref is required"):
        ExternalEffectSafety(
            provider="max",
            supports_idempotency=True,
            supports_reconciliation=False,
            evidence_ref="",
        )
