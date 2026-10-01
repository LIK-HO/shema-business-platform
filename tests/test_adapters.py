from shema_platform.adapters.communication.max import (
    CanonicalCommunicationEvent,
    MaxAdapter,
    MaxEventKind,
    MaxMockAdapter,
    MaxWebhookEvent,
)


def test_max_adapter_normalizes_to_canonical_event() -> None:
    adapter: MaxAdapter = MaxMockAdapter()
    normalized = adapter.normalize(
        MaxWebhookEvent(
            event_id="max-event-1",
            api_version="2",
            kind=MaxEventKind.MESSAGE,
            payload={"chat_id": "42", "text": "Здравствуйте"},
        )
    )

    assert isinstance(normalized, CanonicalCommunicationEvent)
    assert normalized.channel == "max"
    assert normalized.event_id == "max-event-1"
    assert normalized.external_version == "2"
    assert normalized.payload["text"] == "Здравствуйте"


def test_max_adapter_rejects_missing_identity_fields() -> None:
    adapter = MaxMockAdapter()
    try:
        adapter.normalize(MaxWebhookEvent("", "2", MaxEventKind.MESSAGE, {}))
    except ValueError as exc:
        assert "event_id" in str(exc)
    else:
        raise AssertionError("missing event_id must fail")
