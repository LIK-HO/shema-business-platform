import pytest

from shema_platform.domain.commercial_action import (
    CommercialAction,
    CommercialActionStatus,
)
from shema_platform.foundation.errors import QuarantineRequired


def test_action_requires_identity_contact_channel_and_evidence() -> None:
    action = CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="phone:+70000000000",
        channel="max",
        evidence_refs=("evidence:1",),
    )

    ready = action.mark_ready()
    assert ready.status is CommercialActionStatus.READY


@pytest.mark.parametrize(
    "identity_id,contact_ref,channel,evidence_refs",
    [
        ("", "phone:+70000000000", "max", ("evidence:1",)),
        ("identity-1", "", "max", ("evidence:1",)),
        ("identity-1", "phone:+70000000000", "", ("evidence:1",)),
        ("identity-1", "phone:+70000000000", "max", ()),
    ],
)
def test_action_rejects_incomplete_send_context(
    identity_id: str,
    contact_ref: str,
    channel: str,
    evidence_refs: tuple[str, ...],
) -> None:
    action = CommercialAction(
        action_id="action-1",
        identity_id=identity_id,
        contact_ref=contact_ref,
        channel=channel,
        evidence_refs=evidence_refs,
    )

    with pytest.raises(QuarantineRequired):
        action.mark_ready()


def test_only_ready_action_can_be_sent() -> None:
    action = CommercialAction(
        action_id="action-1",
        identity_id="identity-1",
        contact_ref="phone:+70000000000",
        channel="max",
        evidence_refs=("evidence:1",),
    )

    with pytest.raises(ValueError, match="only ready"):
        action.mark_sent()

    assert action.mark_ready().mark_sent().status is CommercialActionStatus.SENT
