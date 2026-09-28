import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load(name: str) -> dict:
    return json.loads((ROOT / "architecture" / name).read_text(encoding="utf-8"))


def test_global_gate_is_mandatory_for_strategy_changes() -> None:
    payload = load("global_adversarial_survivability_gate_contract.json")

    assert payload["core_principle"].startswith(
        "Every material strategy change and every element completion"
    )
    assert payload["closure_policy"]["blocks_verified_state"] is True
    assert payload["closure_policy"]["blocks_closed_state"] is True
    assert payload["closure_policy"]["current_head_required"] is True
    assert "strategy_change" in payload["triggers"]
    assert "element_completion" in payload["triggers"]
    assert "operator_causal_chain_check" in payload["required_outputs"]
    assert "legal_document_change_resilience_check" in payload["required_outputs"]


def test_global_adversarial_gate_covers_the_actual_system_failure_boundaries() -> None:
    payload = load("global_adversarial_survivability_gate_contract.json")

    required = {
        "frozen_v1_4_kernel",
        "data_plane_and_persistence",
        "external_effects_idempotency_and_reconciliation",
        "operator_causal_continuity",
        "multi_operator_assignment_permissions_and_concurrency",
        "migration_cutover_backup_restore_and_rollback",
        "operator_interface_and_capability_visibility",
    }
    assert required.issubset(set(payload["scope"]))

    questions = set(payload["mandatory_questions"])
    assert any("two authoritative values" in q for q in questions)
    assert any("two operators" in q for q in questions)
    assert any("legal or EDO rule changes" in q for q in questions)
    assert any("ambiguous external result" in q for q in questions)
    assert any("operator interface expose" in q for q in questions)
    assert (
        "operator_interface_authority_and_causal_continuity_check"
        in payload["required_outputs"]
    )


def test_work_protocol_cannot_close_an_element_without_the_global_gate() -> None:
    payload = load("development_work_protocol.json")

    assert "global_adversarial_survivability_review" in payload["integrity_requirements"]
    assert (
        "global_adversarial_survivability_gate_passed_for_current_head"
        in payload["element_completion"]["close_only_when"]
    )
