from datetime import UTC, datetime

import pytest

from shema_platform.foundation.audit import AuditLog, AuditRecord


def test_audit_record_metadata_is_immutable() -> None:
    metadata = {"source": "registry"}
    record = AuditRecord(
        audit_id="audit-1",
        actor_id="operator-1",
        action="identity.verify",
        resource_type="identity",
        resource_id="identity-1",
        outcome="success",
        occurred_at=datetime.now(UTC),
        metadata=metadata,
        correlation_id="corr-1",
        configuration_version="cfg-1",
    )

    metadata["source"] = "changed"

    assert record.metadata["source"] == "registry"
    assert record.correlation_id == "corr-1"
    assert record.configuration_version == "cfg-1"


def test_audit_log_is_append_only_from_application_api() -> None:
    audit = AuditLog()
    record = audit.append(
        audit_id="audit-1",
        actor_id="operator-1",
        action="identity.verify",
        resource_type="identity",
        resource_id="identity-1",
        outcome="success",
        metadata={"source": "registry"},
    )

    assert audit.all() == (record,)


def test_audit_record_rejects_missing_required_fields() -> None:
    with pytest.raises(ValueError, match="audit_id and actor_id"):
        AuditRecord(
            audit_id="",
            actor_id="operator-1",
            action="identity.verify",
            resource_type="identity",
            resource_id=None,
            outcome="success",
            occurred_at=datetime.now(UTC),
            metadata={},
        )
