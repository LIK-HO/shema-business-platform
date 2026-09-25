from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.commercial_execution import CommercialActionSendWorkflow
from shema_platform.application.communication import (
    CommunicationAdapter,
    CommunicationGateway,
    CommunicationSendRequest,
    CommunicationSendResult,
)
from shema_platform.domain.commercial_action import CommercialAction, CommercialActionStatus
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import (
    AuthorizationError,
    ExternalEffectUnknown,
    IdempotencyConflict,
    QuarantineRequired,
)
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.outbox import OutboxStore
from shema_platform.foundation.policy import PolicyEngine


@dataclass
class MemoryActions:
    actions: dict[str, CommercialAction] = field(default_factory=dict)

    def add(self, action: CommercialAction) -> None:
        self.actions[action.action_id] = action

    def get(self, action_id: str) -> CommercialAction | None:
        return self.actions.get(action_id)

    def claim_for_send(
        self,
        action_id: str,
        worker_id: str,
        *,
        lease_until: datetime,
        now: datetime,
    ) -> CommercialAction:
        current = self.get(action_id)
        if current is None:
            raise KeyError(f"unknown commercial action: {action_id}")
        if current.status is CommercialActionStatus.SENDING:
            if current.send_lease_until is None or current.send_lease_until > now:
                raise QuarantineRequired("commercial action send is already in progress")
        elif current.status is not CommercialActionStatus.READY:
            raise QuarantineRequired("commercial action is not available for external send")

        return_value = current.mark_sending(
            worker_id=worker_id,
            lease_until=lease_until,
            attempt=current.send_attempt + 1,
        )
        self.actions[action_id] = return_value
        return return_value

    def complete_send(
        self,
        action_id: str,
        worker_id: str,
        *,
        now: datetime,
    ) -> CommercialAction:
        current = self.get(action_id)
        if current is None:
            raise KeyError(f"unknown commercial action: {action_id}")
        if (
            current.status is not CommercialActionStatus.SENDING
            or current.send_worker_id != worker_id
            or current.send_lease_until is None
            or current.send_lease_until <= now
        ):
            raise QuarantineRequired("commercial action completion requires current lease")
        sent = current.mark_sent()
        self.actions[action_id] = sent
        return sent

    def save(self, action: CommercialAction) -> None:
        if action.status is CommercialActionStatus.SENT:
            raise QuarantineRequired("commercial action SENT requires lease-guarded completion")
        self.actions[action.action_id] = action


@dataclass
class MemoryAudit:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass
class MemoryQuarantine:
    records: list[dict[str, object]] = field(default_factory=list)

    def add(
        self,
        *,
        object_type: str,
        object_ref: str,
        reason_code: str,
        payload: dict[str, object],
    ) -> None:
        self.records.append(
            {
                "object_type": object_type,
                "object_ref": object_ref,
                "reason_code": reason_code,
                "payload": dict(payload),
            }
        )


@dataclass
class AmbiguousAdapter(CommunicationAdapter):
    channel: str = "max"
    calls: int = 0

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        self.calls += 1
        raise ExternalEffectUnknown("provider outcome cannot be determined")


@dataclass
class MemoryAdapter(CommunicationAdapter):
    channel: str = "max"
    calls: list[CommunicationSendRequest] = field(default_factory=list)
    receipts: dict[str, CommunicationSendResult] = field(default_factory=dict)

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        self.calls.append(request)
        existing = self.receipts.get(request.idempotency_key)
        if existing is not None:
            return existing
        result = CommunicationSendResult(
            action_id=request.action_id,
            channel=request.channel,
            external_message_id=f"external:{request.idempotency_key}",
            accepted=True,
        )
        self.receipts[request.idempotency_key] = result
        return result


@dataclass
class MemoryUow:
    commercial_actions: MemoryActions
    idempotency: IdempotencyStore
    outbox: OutboxStore
    audits: MemoryAudit
    quarantine: MemoryQuarantine

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback) -> bool:
        return False


def workflow_parts() -> tuple[CommercialActionSendWorkflow, MemoryUow, MemoryAdapter]:
    actions = MemoryActions()
    actions.add(
        CommercialAction(
            action_id="action-1",
            identity_id="identity-1",
            contact_ref="chat:1",
            channel="max",
            evidence_refs=("evidence:1",),
        ).mark_ready()
    )
    uow = MemoryUow(
        actions,
        IdempotencyStore(),
        OutboxStore(),
        MemoryAudit(),
        MemoryQuarantine(),
    )
    adapter = MemoryAdapter()
    gateway = CommunicationGateway(adapter)
    authorizer = RBACAuthorizer(
        (
            AuthorizationSubject(
                "operator-1",
                frozenset({Permission.COMMERCIAL_ACTION_SEND}),
            ),
        )
    )
    workflow = CommercialActionSendWorkflow(
        lambda: uow,
        gateway,
        authorizer,
        PolicyEngine(),
    )
    return workflow, uow, adapter


def test_ambiguous_external_outcome_is_quarantined_without_retry() -> None:
    workflow, uow, _ = workflow_parts()
    ambiguous = AmbiguousAdapter()
    workflow = CommercialActionSendWorkflow(
        lambda: uow,
        CommunicationGateway(ambiguous),
        RBACAuthorizer(
            (
                AuthorizationSubject(
                    "operator-1",
                    frozenset({Permission.COMMERCIAL_ACTION_SEND}),
                ),
            )
        ),
        PolicyEngine(),
    )

    with pytest.raises(
        QuarantineRequired,
        match="outcome is unknown; action quarantined",
    ):
        workflow.execute(
            actor=Actor("operator-1", trust_level=2),
            action_id="action-1",
            body="Здравствуйте",
            idempotency_key="send-key-ambiguous",
        )

    action = uow.commercial_actions.get("action-1")
    assert action is not None
    assert action.status is CommercialActionStatus.FAILED
    assert uow.idempotency.get("send-key-ambiguous").result_ref == (
        "pending:action-1"
    )
    assert len(uow.quarantine.records) == 1
    assert uow.quarantine.records[0]["reason_code"] == "external_effect_unknown"
    assert len(uow.outbox.pending()) == 1
    assert len(uow.audits.records) == 1
    assert ambiguous.calls == 1

    with pytest.raises(QuarantineRequired):
        workflow.execute(
            actor=Actor("operator-1", trust_level=2),
            action_id="action-1",
            body="Здравствуйте",
            idempotency_key="send-key-ambiguous",
        )

    assert ambiguous.calls == 1


def test_send_marks_action_sent_and_publishes_outbox() -> None:
    workflow, uow, adapter = workflow_parts()

    result = workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="send-key-1",
    )

    assert result.accepted
    assert uow.commercial_actions.get("action-1").status.value == "sent"
    assert len(uow.outbox.pending()) == 1
    assert len(uow.audits.records) == 1
    assert uow.audits.records[0].actor_id == "operator-1"
    assert len(adapter.calls) == 1


def test_retry_uses_idempotency_without_second_external_call() -> None:
    workflow, uow, adapter = workflow_parts()

    first = workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="send-key-1",
    )
    second = workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="send-key-1",
    )

    assert second == first
    assert len(adapter.calls) == 1


def test_reusing_key_with_changed_request_is_rejected() -> None:
    workflow, _, adapter = workflow_parts()

    workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="send-key-1",
    )

    with pytest.raises(IdempotencyConflict):
        workflow.execute(
            actor=Actor("operator-1", trust_level=2),
            action_id="action-1",
            body="Другой текст",
            idempotency_key="send-key-1",
        )

    assert len(adapter.calls) == 1


def test_permission_is_required_before_external_effect() -> None:
    workflow, _, adapter = workflow_parts()
    with pytest.raises(AuthorizationError, match="permission denied"):
        workflow.execute(
            actor=Actor("operator-2", trust_level=2),
            action_id="action-1",
            body="Здравствуйте",
            idempotency_key="send-key-2",
        )

    assert adapter.calls == []


def test_active_send_reservation_blocks_a_second_external_effect() -> None:
    workflow, uow, adapter = workflow_parts()
    request_hash = workflow.request_hash("action-1", "Здравствуйте", "send-key-1")
    now = datetime.now(UTC)
    uow.idempotency.reserve("send-key-1", request_hash, "pending:action-1")
    uow.commercial_actions.claim_for_send(
        "action-1",
        "worker-1",
        lease_until=now + timedelta(minutes=5),
        now=now,
    )

    with pytest.raises(QuarantineRequired, match="already in progress"):
        workflow.execute(
            actor=Actor("operator-1", trust_level=2),
            action_id="action-1",
            body="Здравствуйте",
            idempotency_key="send-key-1",
        )

    assert adapter.calls == []


def test_expired_send_reservation_can_be_reclaimed() -> None:
    workflow, uow, adapter = workflow_parts()
    request_hash = workflow.request_hash("action-1", "Здравствуйте", "send-key-1")
    now = datetime.now(UTC)
    uow.idempotency.reserve("send-key-1", request_hash, "pending:action-1")
    uow.commercial_actions.claim_for_send(
        "action-1",
        "worker-1",
        lease_until=now - timedelta(seconds=1),
        now=now - timedelta(seconds=10),
    )

    result = workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="send-key-1",
    )

    assert result.accepted
    assert len(adapter.calls) == 1
    action = uow.commercial_actions.get("action-1")
    assert action is not None
    assert action.status is CommercialActionStatus.SENT
    assert action.send_attempt == 2


def test_external_effect_key_is_stable_across_command_retries() -> None:
    workflow, uow, adapter = workflow_parts()
    effect_key = workflow.effect_idempotency_key("action-1")

    first_request_hash = workflow.request_hash(
        "action-1",
        "Здравствуйте",
        "command-key-1",
    )
    uow.idempotency.reserve(
        "command-key-1",
        first_request_hash,
        "pending:action-1",
    )
    now = datetime.now(UTC)
    uow.commercial_actions.claim_for_send(
        "action-1",
        "worker-1",
        lease_until=now - timedelta(seconds=1),
        now=now - timedelta(seconds=10),
    )
    first_receipt = adapter.send(
        CommunicationSendRequest(
            action_id="action-1",
            channel="max",
            contact_ref="chat:1",
            body="Здравствуйте",
            idempotency_key=effect_key,
        )
    )

    current = uow.commercial_actions.get("action-1")
    assert current is not None
    uow.commercial_actions.save(
        current.mark_sending(
            worker_id="worker-1",
            lease_until=now - timedelta(seconds=1),
            attempt=1,
        )
    )

    result = workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="command-key-2",
    )

    assert result.external_message_id == first_receipt.external_message_id
    assert len(adapter.calls) == 2
    assert adapter.calls[-1].idempotency_key == effect_key


def test_stale_send_worker_cannot_complete_action() -> None:
    workflow, uow, _ = workflow_parts()
    now = datetime.now(UTC)
    uow.commercial_actions.claim_for_send(
        "action-1",
        "worker-1",
        lease_until=now + timedelta(seconds=1),
        now=now,
    )

    with pytest.raises(QuarantineRequired, match="requires current lease"):
        uow.commercial_actions.complete_send(
            "action-1",
            "worker-2",
            now=now + timedelta(seconds=2),
        )


def test_direct_sent_save_is_rejected() -> None:
    workflow, uow, _ = workflow_parts()
    sent = (
        uow.commercial_actions.get("action-1")
        .mark_sending(
            worker_id="worker-1",
            lease_until=datetime.now(UTC) + timedelta(minutes=5),
            attempt=1,
        )
        .mark_sent()
    )
    with pytest.raises(QuarantineRequired, match="lease-guarded completion"):
        uow.commercial_actions.save(sent)
    assert workflow is not None
