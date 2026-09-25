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
from shema_platform.domain.commercial_action import (
    CommercialAction,
    CommercialActionStatus,
)
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import Permission, RBACAuthorizer
from shema_platform.foundation.errors import (
    ExternalEffectUnknown,
    IdempotencyConflict,
    PolicyDenied,
    QuarantineRequired,
)
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

    @staticmethod
    def effect_idempotency_key(action_id: str) -> str:
        return f"commercial-send:{action_id}"

    def _quarantine_unknown_external_effect(
        self,
        *,
        actor: Actor,
        action_id: str,
        request_hash: str,
        idempotency_key: str,
        worker_id: str,
        error: ExternalEffectUnknown,
    ) -> None:
        with self._unit_of_work_factory() as uow:
            current = uow.commercial_actions.get(action_id)
            if current is None:
                raise KeyError(f"unknown commercial action: {action_id}")

            failed = CommercialAction(
                action_id=current.action_id,
                identity_id=current.identity_id,
                contact_ref=current.contact_ref,
                channel=current.channel,
                evidence_refs=current.evidence_refs,
                status=CommercialActionStatus.FAILED,
                send_attempt=current.send_attempt,
            )
            uow.commercial_actions.save(failed)

            uow.quarantine.add(
                object_type="commercial_action",
                object_ref=action_id,
                reason_code="external_effect_unknown",
                payload={
                    "request_hash": request_hash,
                    "command_idempotency_key": idempotency_key,
                    "external_effect_idempotency_key": self.effect_idempotency_key(
                        action_id
                    ),
                    "send_attempt": current.send_attempt,
                },
            )

            event_key = (
                "commercial-action.external-effect-unknown:"
                f"{action_id}:{request_hash}"
            )
            occurred_at = utc_now()
            uow.outbox.append(
                OutboxEvent(
                    event_id=str(uuid5(NAMESPACE_URL, event_key)),
                    event_type="commercial_action.external_effect_unknown",
                    aggregate_type="commercial_action",
                    aggregate_id=action_id,
                    payload={
                        "action_id": action_id,
                        "channel": current.channel,
                        "reason_code": "external_effect_unknown",
                        "request_hash": request_hash,
                    },
                    occurred_at=occurred_at,
                )
            )
            uow.audits.append(
                AuditRecord(
                    audit_id=str(uuid5(NAMESPACE_URL, f"audit:{event_key}")),
                    actor_id=actor.actor_id,
                    action="commercial_action.external_effect_unknown",
                    resource_type="commercial_action",
                    resource_id=action_id,
                    outcome="quarantined",
                    occurred_at=occurred_at,
                    metadata={
                        "channel": current.channel,
                        "send_attempt": current.send_attempt,
                        "worker_id": worker_id,
                        "error_type": type(error).__name__,
                    },
                )
            )

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

        try:
            result = self._communication_gateway.send(
                sending,
                body=body,
                idempotency_key=self.effect_idempotency_key(action_id),
            )
        except ExternalEffectUnknown as exc:
            self._quarantine_unknown_external_effect(
                actor=actor,
                action_id=action_id,
                request_hash=request_hash,
                idempotency_key=idempotency_key,
                worker_id=worker_id,
                error=exc,
            )
            raise QuarantineRequired(
                "external communication outcome is unknown; action quarantined"
            ) from exc

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

            if current.status is not CommercialActionStatus.SENDING:
                raise QuarantineRequired(
                    "commercial action is no longer waiting for leased completion"
                )

            sent = uow.commercial_actions.complete_send(
                action_id,
                worker_id,
                now=utc_now(),
            )

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
