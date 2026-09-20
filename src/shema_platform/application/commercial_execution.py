from __future__ import annotations

from collections.abc import Callable
from datetime import timedelta
from hashlib import sha256
from uuid import NAMESPACE_URL, uuid4, uuid5

from shema_platform.application.commands import Actor
from shema_platform.application.communication import (
    CommunicationGateway,
    CommunicationSendResult,
)
from shema_platform.application.ports import UnitOfWork
from shema_platform.domain.commercial_action import CommercialActionStatus
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import IdempotencyConflict, PolicyDenied, QuarantineRequired
from shema_platform.foundation.outbox import OutboxEvent, utc_now
from shema_platform.foundation.policy import Decision, PolicyContext, PolicyEngine


class CommercialActionSendWorkflow:
    """Recovery-safe external send guarded by a durable, leased reservation."""

    SEND_LEASE_SECONDS = 300

    def __init__(
        self,
        unit_of_work_factory: Callable[[], UnitOfWork],
        communication_gateway: CommunicationGateway,
        authorizer: RBACAuthorizer,
        policy: PolicyEngine,
    ) -> None:
        self._unit_of_work_factory = unit_of_work_factory
        self._communication_gateway = communication_gateway
        self._authorizer = authorizer
        self._policy = policy

    @staticmethod
    def request_hash(
        action_id: str,
        body: str,
        idempotency_key: str,
    ) -> str:
        payload = "\n".join((action_id, idempotency_key, body))
        return sha256(payload.encode("utf-8")).hexdigest()

    @staticmethod
    def pending_ref(action_id: str) -> str:
        return f"pending:{action_id}"

    def execute(
        self,
        *,
        actor: Actor,
        action_id: str,
        body: str,
        idempotency_key: str,
    ) -> CommunicationSendResult:
        self._authorizer.require(
            actor.actor_id,
            Permission.COMMERCIAL_ACTION_SEND,
        )
        request_hash = self.request_hash(action_id, body, idempotency_key)
        worker_id = f"commercial-send:{uuid4()}"
        now = utc_now()
        lease_until = now + timedelta(seconds=self.SEND_LEASE_SECONDS)

        with self._unit_of_work_factory() as uow:
            existing = uow.idempotency.get(idempotency_key)
            action = uow.commercial_actions.get(action_id)

            if action is None:
                raise KeyError(f"unknown commercial action: {action_id}")

            decision = self._policy.evaluate(
                PolicyContext(
                    actor_id=actor.actor_id,
                    action="commercial_action_send",
                    resource_type="commercial_action",
                    resource_id=action_id,
                    actor_trust_level=actor.trust_level,
                    resource_trust_level=2,
                    evidence_level=2 if action.evidence_refs else 0,
                )
            )
            if decision.decision is not Decision.ALLOW:
                raise PolicyDenied(decision.reason)

            if existing is not None:
                if existing.request_hash != request_hash:
                    raise IdempotencyConflict(
                        "idempotency key reused with different request"
                    )
                if not existing.result_ref.startswith("pending:"):
                    if action.status is not CommercialActionStatus.SENT:
                        raise QuarantineRequired(
                            "idempotency result exists but commercial action is not sent"
                        )
                    return CommunicationSendResult(
                        action_id=action.action_id,
                        channel=action.channel,
                        external_message_id=existing.result_ref,
                        accepted=True,
                    )
                if existing.result_ref != self.pending_ref(action_id):
                    raise IdempotencyConflict(
                        "idempotency key is reserved for another commercial action"
                    )
            else:
                uow.idempotency.reserve(
                    idempotency_key,
                    request_hash,
                    self.pending_ref(action_id),
                )

            sending = uow.commercial_actions.claim_for_send(
                action_id,
                worker_id,
                lease_until=lease_until,
                now=now,
            )

        result = self._communication_gateway.send(
            sending,
            body=body,
            idempotency_key=idempotency_key,
        )

        with self._unit_of_work_factory() as uow:
            completed = uow.idempotency.complete(
                idempotency_key,
                request_hash,
                result.external_message_id,
            )
            current = uow.commercial_actions.get(action_id)
            if current is None:
                raise KeyError(f"unknown commercial action: {action_id}")

            if current.status is CommercialActionStatus.SENT:
                if completed.result_ref != result.external_message_id:
                    raise IdempotencyConflict(
                        "external communication result differs from durable result"
                    )
                return CommunicationSendResult(
                    action_id=action_id,
                    channel=current.channel,
                    external_message_id=completed.result_ref,
                    accepted=True,
                )

            if (
                current.status is not CommercialActionStatus.SENDING
                or current.send_worker_id != worker_id
                or current.send_lease_until is None
                or current.send_lease_until <= utc_now()
            ):
                raise QuarantineRequired(
                    "commercial action send lease is no longer owned by this worker"
                )

            sent = current.mark_sent()
            uow.commercial_actions.save(sent)

            event_key = (
                "commercial-action.sent:"
                f"{action_id}:{completed.result_ref}"
            )
            event = OutboxEvent(
                event_id=str(uuid5(NAMESPACE_URL, event_key)),
                event_type="commercial_action.sent",
                aggregate_type="commercial_action",
                aggregate_id=action_id,
                payload={
                    "action_id": action_id,
                    "identity_id": sent.identity_id,
                    "channel": sent.channel,
                    "external_message_id": completed.result_ref,
                },
                occurred_at=utc_now(),
            )
            uow.outbox.append(event)

            uow.audits.append(
                AuditRecord(
                    audit_id=str(
                        uuid5(
                            NAMESPACE_URL,
                            f"audit:{event_key}",
                        )
                    ),
                    actor_id=actor.actor_id,
                    action="commercial_action.sent",
                    resource_type="commercial_action",
                    resource_id=action_id,
                    outcome="success",
                    occurred_at=event.occurred_at,
                    metadata={
                        "channel": sent.channel,
                        "external_message_id": completed.result_ref,
                        "send_attempt": sent.send_attempt,
                    },
                )
            )

        return result
