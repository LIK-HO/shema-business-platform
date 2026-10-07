from __future__ import annotations

from dataclasses import dataclass

from shema_platform.application.communication import (
    CommunicationAdapter,
    CommunicationSendRequest,
    CommunicationSendResult,
)
from shema_platform.foundation.errors import QuarantineRequired


@dataclass(frozen=True, slots=True)
class ExternalEffectSafety:
    """Evidence-backed capability assessment for an external-effect provider."""

    provider: str
    supports_idempotency: bool
    supports_reconciliation: bool
    evidence_ref: str

    def __post_init__(self) -> None:
        if not self.provider.strip():
            raise ValueError("provider is required")
        if not self.evidence_ref.strip():
            raise ValueError("evidence_ref is required")

    @property
    def safe_for_retry(self) -> bool:
        return self.supports_idempotency or self.supports_reconciliation


def require_safe_external_effect(safety: ExternalEffectSafety) -> None:
    """Fail closed until repeated external effects are demonstrably safe."""

    if not safety.safe_for_retry:
        raise QuarantineRequired(
            f"external effect for provider {safety.provider!r} is not "
            "certified for crash-safe retry: idempotency or reconciliation "
            "capability is not proven"
        )


class SafeCommunicationAdapter:
    """Adapter wrapper that blocks uncertified external effects."""

    def __init__(
        self,
        adapter: CommunicationAdapter,
        safety: ExternalEffectSafety,
    ) -> None:
        require_safe_external_effect(safety)
        self._adapter = adapter
        self.channel = adapter.channel

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        return self._adapter.send(request)
