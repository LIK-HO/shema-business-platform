from json import loads
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text()


def test_architecture_baseline_exists() -> None:
    assert (ROOT / "ARCHITECTURE.md").is_file()


def test_machine_readable_architecture_contract_exists() -> None:
    contract = loads(read("architecture/contract.json"))
    assert contract["version"] == "1.4"
    assert contract["runtime"] == "modular_monolith"
    assert contract["transactional_authority"] == "postgresql"
    assert "max_is_an_adapter" in contract["critical_invariants"]
    assert "commercial_action" in contract["persistence"]["canonical"]
    assert "order_header" in contract["persistence"]["canonical"]
    assert "economic_entry" in contract["persistence"]["canonical"]
    assert "ai_run" in contract["persistence"]["canonical"]
    assert "job_execution" in contract["persistence"]["canonical"]
    assert "commercial_send_reservation" in contract["operational_controls"]
    assert "commercial_send_is_lease_guarded" in contract["critical_invariants"]
    assert (
        "external_communication_deduplicates_by_idempotency_key"
        in contract["critical_invariants"]
    )
    assert (
        "external_effect_idempotency_key_is_stable_per_action"
        in contract["critical_invariants"]
    )
    assert "commercial_action_is_ready_before_external_send" not in contract[
        "critical_invariants"
    ]
    assert (
        "commercial_action_is_reserved_before_external_effect"
        in contract["critical_invariants"]
    )
    assert (
        "commercial_send_completion_requires_current_lease"
        in contract["critical_invariants"]
    )
    assert contract["persistence"]["uncertain_state"] == ["quarantine_record"]


def test_database_migrations_are_forward_only_and_declared() -> None:
    contract = loads(read("architecture/contract.json"))
    assert contract["persistence"]["migrations"] == [
        "0001_foundation.sql",
        "0002_discovery.sql",
        "0003_audit_context.sql",
        "0004_commercial_execution.sql",
        "0005_ai_run.sql",
        "0006_job_execution.sql",
        "0007_outbox_delivery_lease.sql",
        "0008_commercial_send_reservation.sql",
    ]
    assert "correlation_id" in read("db/migrations/0003_audit_context.sql")
    assert "commercial_action" in read("db/migrations/0004_commercial_execution.sql")
    assert "ai_run" in read("db/migrations/0005_ai_run.sql")
    assert "job_execution" in read("db/migrations/0006_job_execution.sql")
    assert "delivery_lease_until" in read("db/migrations/0007_outbox_delivery_lease.sql")
    assert "send_lease_until" in read("db/migrations/0008_commercial_send_reservation.sql")


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


def test_kernel_checkpoint_tracks_twelve_elements() -> None:
    checkpoint = read("docs/V1.4_KERNEL_CHECKPOINT.md")
    for element in (
        "1. Foundation / Architecture Contract",
        "4. Discovery + Qualification",
        "9. Commercial Action",
        "10. Order",
        "11. Economics",
        "12. Canonical API / Experience Boundary",
    ):
        assert element in checkpoint


def test_legacy_boundary_is_explicit() -> None:
    architecture = read("ARCHITECTURE.md")
    assert "Airtable is legacy/transition data" in architecture
    assert "MAX is included in the adapter boundary" in architecture
