from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from shema_platform.foundation.errors import QuarantineRequired


class CommercialActionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SENT = "sent"
    FAILED = "failed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


@dataclass(frozen=True, slots=True)
class CommercialAction:
    action_id: str
    identity_id: str
    contact_ref: str
    channel: str
    evidence_refs: tuple[str, ...]
    status: CommercialActionStatus = CommercialActionStatus.DRAFT

    def validate_for_send(self) -> None:
        if not self.identity_id.strip():
            raise QuarantineRequired("commercial action requires identity")
        if not self.contact_ref.strip():
            raise QuarantineRequired("commercial action requires contact")
        if not self.channel.strip():
            raise QuarantineRequired("commercial action requires channel")
        if not self.evidence_refs:
            raise QuarantineRequired("commercial action requires evidence")

    def mark_ready(self) -> CommercialAction:
        self.validate_for_send()
        return CommercialAction(
            action_id=self.action_id,
            identity_id=self.identity_id,
            contact_ref=self.contact_ref,
            channel=self.channel,
            evidence_refs=self.evidence_refs,
            status=CommercialActionStatus.READY,
        )

    def mark_sent(self) -> CommercialAction:
        if self.status is not CommercialActionStatus.READY:
            raise ValueError("only ready action can be sent")
        return CommercialAction(
            action_id=self.action_id,
            identity_id=self.identity_id,
            contact_ref=self.contact_ref,
            channel=self.channel,
            evidence_refs=self.evidence_refs,
            status=CommercialActionStatus.SENT,
        )
