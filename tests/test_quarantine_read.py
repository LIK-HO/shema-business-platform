from datetime import UTC, datetime

import pytest

from shema_platform.platform.quarantine_read import PostgresQuarantineReader


class Cursor:
    def __init__(self, rows):
        self._rows = rows

    def fetchall(self):
        return self._rows


class Connection:
    def __init__(self, rows):
        self.rows = rows
        self.calls: list[tuple[str, tuple[object, ...]]] = []

    def execute(self, statement, parameters=()):
        self.calls.append((statement, parameters))
        return Cursor(self.rows)


def sample_row():
    now = datetime.now(UTC)
    return (
        "q1",
        "commercial_action",
        "action:1",
        "external_effect_unknown",
        {
            "request_hash": "hash",
            "external_effect_idempotency_key": "commercial-send:action:1",
        },
        now,
        None,
        None,
    )


def test_get_open_returns_structured_read_only_record() -> None:
    connection = Connection([sample_row()])
    reader = PostgresQuarantineReader(connection)

    records = reader.get_open(
        object_type="commercial_action",
        object_ref="action:1",
        reason_code="external_effect_unknown",
    )

    assert len(records) == 1
    record = records[0]
    assert record.quarantine_id == "q1"
    assert record.object_type == "commercial_action"
    assert record.object_ref == "action:1"
    assert record.reason_code == "external_effect_unknown"
    assert record.resolved_at is None
    assert record.resolution is None
    assert record.payload["external_effect_idempotency_key"] == (
        "commercial-send:action:1"
    )
    assert "update quarantine_record" not in connection.calls[0][0].lower()
    assert "delete from quarantine_record" not in connection.calls[0][0].lower()


def test_list_open_validates_limit_and_is_read_only() -> None:
    connection = Connection([sample_row()])
    reader = PostgresQuarantineReader(connection)

    with pytest.raises(ValueError):
        reader.list_open(limit=0)

    with pytest.raises(ValueError):
        reader.list_open(limit=1001)

    records = reader.list_open(limit=10)

    assert len(records) == 1
    statement = connection.calls[-1][0].lower()
    assert statement.strip().startswith("select")
    assert "resolved_at is null" in statement


def test_get_open_requires_identifiers() -> None:
    reader = PostgresQuarantineReader(Connection([]))

    with pytest.raises(ValueError):
        reader.get_open(object_type="", object_ref="action:1")

    with pytest.raises(ValueError):
        reader.get_open(object_type="commercial_action", object_ref="")
