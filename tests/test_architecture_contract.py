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
    assert (
        "idempotency_business_state_outbox_audit_are_one_transaction"
        in contract["critical_invariants"]
    )
    assert "order_persistence_respects_domain_lifecycle" in contract["critical_invariants"]
    assert "order_persistence_serializes_lifecycle_update" in contract[
        "critical_invariants"
    ]
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


def test_v1_5_unified_runtime_contract_is_additive() -> None:
    runtime = loads(read("architecture/runtime_contract.json"))
    kernel = loads(read("architecture/contract.json"))

    assert runtime["version"] == "1.5.0"
    assert runtime["baseline_kernel_contract"] == "1.4"
    assert runtime["iam"]["authentication_boundary"] == "oidc_jwt_adapter"
    assert runtime["iam"]["permission_materialization"] is True
    assert runtime["iam"]["unknown_permissions_fail_closed"] is True
    assert "RS256" in runtime["iam"]["allowed_algorithms"]
    assert "EdDSA" in runtime["iam"]["allowed_algorithms"]
    assert runtime["observability"]["telemetry_allowlist_based_redaction"] is True
    assert runtime["observability"]["telemetry_does_not_store_authorization_headers"] is True
    assert runtime["security"]["production_docs_disabled"] is True
    assert runtime["security"]["production_oidc_https_required"] is True
    assert runtime["supply_chain"]["dependency_audit"] == "pip-audit"
    assert runtime["supply_chain"]["audit_is_release_gate"] is True
    assert runtime["recovery"]["outbox_reclaim"] is True
    assert runtime["recovery"]["commercial_send_reclaim"] is True
    assert kernel["version"] == "1.4"


def test_gigachat_application_composition_contract_is_bounded() -> None:
    contract = loads(
        read("architecture/gigachat_application_composition_contract.json")
    )

    assert contract["version"] == "1.0"
    assert contract["frozen_kernel_impact"] is False
    assert contract["composition"]["provider"] == "gigachat"
    assert contract["composition"]["gateway"] == (
        "shema_platform.application.ai.AIGateway"
    )
    assert contract["composition"]["workflow"] == (
        "shema_platform.application.ai_runtime.AIExecutionService"
    )
    assert contract["activation"]["default_enabled"] is False
    assert contract["activation"]["explicit_operator"] is True
    assert contract["activation"]["rollback"] is True
    assert contract["trust"]["client_controls_trust"] is False
    assert contract["scope_stop"]["no_kernel_semantic_change"] is True
    assert contract["scope_stop"]["no_http_wiring"] is True
    assert contract["scope_stop"]["no_openai"] is True
    assert contract["scope_stop"]["no_cloud_local_fallback"] is True


def test_gigachat_provider_contract_is_bounded() -> None:
    contract = loads(read("architecture/gigachat_provider_contract.json"))

    assert contract["version"] == "1.0"
    assert contract["frozen_kernel_impact"] is False
    assert contract["provider"]["id"] == "gigachat"
    assert contract["provider"]["base_url"] == "https://api.giga.chat/v1"
    assert contract["provider"]["token_ttl_minutes"] == 30
    assert contract["provider"]["auth_key_runtime_only"] is True
    assert contract["provider"]["token_runtime_only"] is True
    assert contract["bounded_controls"]["no_automatic_retry"] is True
    assert contract["production_scope"]["allowed_scopes"] == [
        "GIGACHAT_API_B2B",
        "GIGACHAT_API_CORP",
    ]
    assert contract["activation"]["default_enabled"] is False
    assert contract["activation"]["explicit_operator"] is True
    assert contract["provider_policy"]["cloud_allowlist"] == [
        "yandexgpt",
        "gigachat",
    ]
    assert contract["provider_policy"]["implicit_cloud_local_fallback"] is False
    assert contract["provider_policy"]["openai_approved"] is False
    assert contract["scope_stop"]["no_application_wiring"] is True
    assert contract["scope_stop"]["no_live_traffic"] is True
    assert contract["scope_stop"]["no_openai"] is True


def test_ai_end_to_end_contract_is_bounded() -> None:
    contract = loads(read("architecture/ai_end_to_end_contract.json"))

    assert contract["version"] == "1.0"
    assert contract["frozen_kernel_impact"] is False
    assert contract["proofs"]["canonical_airun_persistence"] is True
    assert contract["proofs"]["canonical_audit_persistence"] is True
    assert contract["proofs"]["correlation_propagation"] is True
    assert contract["proofs"]["server_side_trust_resolution"] is True
    assert contract["proofs"]["expired_evidence_fails_closed"] is True
    assert contract["proofs"]["provider_not_invoked_on_trust_failure"] is True
    assert contract["test_transport"]["production_provider_added"] is False
    assert contract["test_transport"]["network_dependency"] is False
    assert contract["scope_stop"]["no_kernel_semantic_change"] is True
    assert contract["scope_stop"]["no_database_schema_change"] is True
    assert contract["scope_stop"]["no_live_traffic"] is True
    assert contract["scope_stop"]["no_openai"] is True


def test_ai_runtime_assembly_contract_is_bounded() -> None:
    contract = loads(read("architecture/ai_runtime_assembly_contract.json"))

    assert contract["version"] == "1.0"
    assert contract["frozen_kernel_impact"] is False
    assert contract["assembly"]["construction_activates_provider"] is False
    assert contract["activation"]["default_enabled"] is False
    assert contract["activation"]["explicit_operator"] is True
    assert contract["activation"]["automatic_startup_activation"] is False
    assert contract["provider_policy"]["cloud_allowlist"] == ["yandexgpt", "gigachat"]
    assert contract["provider_policy"]["implicit_cloud_local_fallback"] is False
    assert contract["provider_policy"]["openai_approved"] is False
    assert contract["scope_stop"]["no_kernel_semantic_change"] is True
    assert contract["scope_stop"]["no_database_schema_change"] is True
    assert contract["scope_stop"]["no_live_traffic_activation"] is True
    assert contract["scope_stop"]["no_openai"] is True


def test_ai_application_composition_contract_is_bounded() -> None:
    contract = loads(read("architecture/ai_application_composition_contract.json"))

    assert contract["version"] == "1.0"
    assert contract["frozen_kernel_impact"] is False
    assert contract["trust_resolution"]["resource_source"] == "identity.state"
    assert contract["trust_resolution"]["evidence_source"] == "evidence"
    assert contract["trust_resolution"]["subject_must_match_resource"] is True
    assert contract["trust_resolution"]["expiry_required"] is True
    assert contract["execution"]["canonical_persistence"] == "frozen_AIGateway"
    assert contract["execution"]["audit"] == "frozen_AIGateway"
    assert contract["activation"]["default_enabled"] is False
    assert contract["activation"]["explicit_operator"] is True
    assert contract["activation"]["implicit_cloud_local_fallback"] is False
    assert contract["scope_stop"]["no_kernel_semantic_change"] is True
    assert contract["scope_stop"]["no_database_schema_change"] is True
    assert contract["scope_stop"]["no_openai"] is True


def test_ai_http_route_contract_is_bounded() -> None:
    route = loads(read("architecture/ai_api_route_contract.json"))

    assert route["version"] == "1.0"
    assert route["route"]["path"] == "/v1/ai/run"
    assert route["route"]["client_cannot_control"] == [
        "provider_id",
        "model",
        "model_version",
        "actor_trust_level",
        "resource_trust_level",
        "evidence_level",
        "production_activation_state",
        "provider_credentials",
    ]
    assert (
        route["composition_boundary"]["frozen_AIGateway_semantics_unchanged"]
        is True
    )
    assert (
        route["production_behavior"][
            "production_provider_activation_still_requires_P28_gate"
        ]
        is True
    )
