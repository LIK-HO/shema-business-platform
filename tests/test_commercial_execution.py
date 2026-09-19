from dataclasses import dataclass, field

import pytest

from shema_platform.application.commands import Actor
from shema_platform.application.commercial_execution import CommercialActionSendWorkflow
from shema_platform.application.communication import (
    CommunicationAdapter,
    CommunicationGateway,
    CommunicationSendRequest,
    CommunicationSendResult,
)
from shema_platform.domain.commercial_action import CommercialAction
from shema_platform.foundation.audit import AuditRecord
from shema_platform.foundation.authorization import (
    AuthorizationSubject,
    Permission,
    RBACAuthorizer,
)
from shema_platform.foundation.errors import AuthorizationError, IdempotencyConflict
from shema_platform.foundation.policy import PolicyEngine
from shema_platform.foundation.idempotency import IdempotencyStore
from shema_platform.foundation.outbox import OutboxStore


@dataclass
class MemoryActions:
    actions: dict[str, CommercialAction] = field(default_factory=dict)

    def add(self, action: CommercialAction) -> None:
        self.actions[action.action_id] = action

    def get(self, action_id: str) -> CommercialAction | None:
        return self.actions.get(action_id)

    def save(self, action: CommercialAction) -> None:
        self.actions[action.action_id] = action


@dataclass
class MemoryAudit:
    records: list[AuditRecord] = field(default_factory=list)

    def append(self, record: AuditRecord) -> None:
        self.records.append(record)


@dataclass
class MemoryAdapter(CommunicationAdapter):
    channel: str = "max"
    calls: list[CommunicationSendRequest] = field(default_factory=list)

    def send(self, request: CommunicationSendRequest) -> CommunicationSendResult:
        self.calls.append(request)
        return CommunicationSendResult(
            action_id=request.action_id,
            channel=request.channel,
            external_message_id=f"external:{request.idempotency_key}",
            accepted=True,
        )


@dataclass
class MemoryUow:
    actions: MemoryActions
    idempotency: IdempotencyStore
    outbox: OutboxStore
    audits: MemoryAudit

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
    uow = MemoryUow(actions, IdempotencyStore(), OutboxStore(), MemoryAudit())
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


def test_send_marks_action_sent_and_publishes_outbox() -> None:
    workflow, uow, adapter = workflow_parts()

    result = workflow.execute(
        actor=Actor("operator-1", trust_level=2),
        action_id="action-1",
        body="Здравствуйте",
        idempotency_key="send-key-1",
    )

    assert result.accepted
    assert uow.actions.get("action-1").status.value == "sent"
    assert len(uow.outbox.pending()) == 1
    assert len(uow.audits.records) == 1
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
