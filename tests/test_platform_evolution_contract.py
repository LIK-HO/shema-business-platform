import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load() -> dict:
    return json.loads(
        (ROOT / "architecture" / "platform_evolution_contract.json").read_text(
            encoding="utf-8"
        )
    )


def test_platform_evolution_has_explicit_change_classes() -> None:
    payload = load()

    assert payload["change_classes"] == {
        "E0": "documentation_or_operator_guidance_only",
        "E1": "local_application_behavior_without_new_authority",
        "E2": "external_provider_public_ingress_or_new_security_boundary",
        "E3": "new_persistence_authority_cross_system_ownership_or_migration",
        "E4": "frozen_kernel_semantic_change",
    }


def test_platform_evolution_requires_threat_resource_and_recovery_gates() -> None:
    payload = load()

    pipeline = payload["evolution_pipeline"]
    assert "GLOBAL_IMPACT_REVIEW" in pipeline
    assert "THREAT_AND_ABUSE_MODEL" in pipeline
    assert "RESOURCE_AND_COST_MODEL" in pipeline
    assert "NEGATIVE_AND_RECOVERY_TESTS" in pipeline
    assert "ADVERSARIAL_SURVIVABILITY_GATE" in pipeline
    assert "CONTROLLED_RELEASE" in pipeline


def test_platform_evolution_forbids_hidden_authority_and_requires_exit_path() -> None:
    payload = load()

    gates = payload["admission_gates"]
    assert gates["canonical_owner_is_explicit"] is True
    assert gates["no_duplicate_authority_is_created"] is True
    assert gates["provider_exit_or_replacement_path_exists"] is True
    assert gates["rollback_or_safe_deactivation_exists"] is True


def test_platform_evolution_release_states_are_explicit() -> None:
    payload = load()

    assert payload["release_states"] == [
        "DRAFT",
        "SHADOW",
        "BOUNDED",
        "CANARY",
        "LIVE",
        "RETIRED",
    ]


def test_platform_evolution_closure_requires_full_evidence() -> None:
    payload = load()

    required = {
        "contract",
        "implementation",
        "negative_paths",
        "integration",
        "security",
        "observability",
        "global_adversarial_review",
        "full_current_head_ci",
        "development_state_update",
    }
    assert required.issubset(set(payload["closure_evidence"]))
