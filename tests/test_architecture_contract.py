import json
import pathlib


ROOT = pathlib.Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_architecture_baseline_exists() -> None:
    assert (ROOT / "ARCHITECTURE.md").is_file()


def test_machine_readable_architecture_contract_exists() -> None:
    contract = json.loads(read("architecture/contract.json"))
    assert contract["runtime"] == "modular_monolith"
    assert contract["transactional_authority"] == "postgresql"
    assert "max_is_an_adapter" in contract["critical_invariants"]


def test_database_migration_contains_foundation_tables() -> None:
    migration = read("db/migrations/0001_foundation.sql")
    for table in ("identity", "evidence", "idempotency_key", "audit_log", "outbox_event"):
        assert f"create table if not exists {table}" in migration


def test_discovery_migration_contains_candidate_and_quarantine_tables() -> None:
    migration = read("db/migrations/0002_discovery.sql")
    for table in ("search_candidate", "quarantine_record"):
        assert f"create table if not exists {table}" in migration
    assert "ux_search_candidate_source_ref" in migration
    assert "ix_quarantine_open" in migration


def test_domain_does_not_depend_on_upper_layers() -> None:
    domain_root = ROOT / "src/shema_platform/domain"
    forbidden = (
        "shema_platform.application",
        "shema_platform.adapters",
        "shema_platform.infrastructure",
    )
    for path in domain_root.rglob("*.py"):
        content = path.read_text()
        assert not any(token in content for token in forbidden)


def test_foundation_does_not_depend_on_upper_layers() -> None:
    foundation_root = ROOT / "src/shema_platform/foundation"
    forbidden = (
        "shema_platform.domain",
        "shema_platform.application",
        "shema_platform.adapters",
    )
    for path in foundation_root.rglob("*.py"):
        content = path.read_text()
        assert not any(token in content for token in forbidden)


def test_legacy_boundary_is_explicit() -> None:
    architecture = read("ARCHITECTURE.md")
    assert "Airtable is legacy/transition data" in architecture
    assert "MAX is included in the adapter boundary" in architecture
