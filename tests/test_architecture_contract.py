from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_architecture_baseline_exists() -> None:
    assert (ROOT / "ARCHITECTURE.md").is_file()


def test_database_migration_contains_foundation_tables() -> None:
    migration = (ROOT / "db/migrations/0001_foundation.sql").read_text()
    for table in ("identity", "evidence", "idempotency_key", "audit_log", "outbox_event"):
        assert f"create table if not exists {table}" in migration


def test_domain_does_not_depend_on_application_or_adapters() -> None:
    domain_root = ROOT / "src/shema_platform/domain"
    forbidden = ("application", "adapters", "infrastructure")
    for path in domain_root.rglob("*.py"):
        content = path.read_text()
        for token in forbidden:
            assert f"shema_platform.{token}" not in content


def test_legacy_boundary_is_explicit() -> None:
    architecture = (ROOT / "ARCHITECTURE.md").read_text()
    assert "Airtable is legacy/transition data" in architecture
    assert "MAX is included in the adapter boundary" in architecture
