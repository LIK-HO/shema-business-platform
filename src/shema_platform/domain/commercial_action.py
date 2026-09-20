from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from shema_platform.foundation.errors import QuarantineRequired


class CommercialActionStatus(StrEnum):
    DRAFT = "draft"
    READY = "ready"
    SENDING = "sending"
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
    send_attempt: int = 0
    send_worker_id: str | None = None
    send_lease_until: datetime | None = None

    def validate_for_send(self) -> None:
        if not self.identity_id.strip():
            raise QuarantineRequired("commercial action requires identity")
        if not self.contact_ref.strip():
            raise QuarantineRequired("commercial action requires contact")
        if not self.channel.strip():
            raise QuarantineRequired("commercial action requires channel")
        if not self.evidence_refs:
            raise QuarantineRequired("commercial action requires evidence")

    def validate_for_external_send(self) -> None:
        if self.status not in (
            CommercialActionStatus.READY,
            CommercialActionStatus.SENDING,
        ):
            raise QuarantineRequired(
                "commercial action must be ready or reserved before external send"
            )
        self.validate_for_send()

    def mark_ready(self) -> CommercialAction:
        self.validate_for_send()
        return CommercialAction(
            action_id=self.action_id,
            identity_id=self.identity_id,
            contact_ref=self.contact_ref,
            channel=self.channel,
            evidence_refs=self.evidence_refs,
            status=CommercialActionStatus.READY,
            send_attempt=self.send_attempt,
        )

    def mark_sending(
        self,
        *,
        worker_id: str,
        lease_until: datetime,
        attempt: int,
    ) -> CommercialAction:
        if not worker_id.strip():
            raise ValueError("send worker is required")
        if lease_until.tzinfo is None:
            raise ValueError("send lease must be timezone-aware")
        if attempt < 1:
            raise ValueError("send attempt must be >= 1")
        if self.status not in (
            CommercialActionStatus.READY,
            CommercialActionStatus.SENDING,
        ):
            raise QuarantineRequired("commercial action is not available for send")

        self.validate_for_send()
        return CommercialAction(
            action_id=self.action_id,
            identity_id=self.identity_id,
            contact_ref=self.contact_ref,
            channel=self.channel,
            evidence_refs=self.evidence_refs,
            status=CommercialActionStatus.SENDING,
            send_attempt=attempt,
            send_worker_id=worker_id,
            send_lease_until=lease_until,
        )

    def mark_sent(self) -> CommercialAction:
        if self.status is not CommercialActionStatus.SENDING:
            raise ValueError("only sending action can be marked sent")
        return CommercialAction(
            action_id=self.action_id,
            identity_id=self.identity_id,
            contact_ref=self.contact_ref,
            channel=self.channel,
            evidence_refs=self.evidence_refs,
            status=CommercialActionStatus.SENT,
            send_attempt=self.send_attempt,
        )
