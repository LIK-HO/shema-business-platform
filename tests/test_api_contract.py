from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_canonical_api_contract_exists() -> None:
    openapi = read("api/openapi.yaml")
    architecture = read("docs/API_CONTRACT.md")

    assert "openapi: 3.1.0" in openapi
    assert "version: 1.4.0" in openapi
    assert "enum: [draft, ready, sending, sent, failed, completed, cancelled]" in openapi
    for route in (
        "/v1/search:",
        "/v1/discovery/evaluate:",
        "/v1/intelligence/research:",
        "/v1/commercial-actions:",
        "/v1/commercial-actions/{actionId}/send:",
        "/v1/orders:",
        "/v1/orders/{orderId}:",
        "/v1/economics/{entityRef}:",
        "/v1/diagnostics:",
    ):
        assert route in openapi

    assert "External effects are never executed by the client" in architecture
    assert "Idempotency-Key" in architecture
