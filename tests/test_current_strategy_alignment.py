import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def read_text(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def load_json(path: str) -> dict:
    return json.loads(read_text(path))


def test_current_strategy_uses_live_repeat_order_and_canonical_ui_model() -> None:
    manifest = read_text("docs/DEVELOPMENT_MANIFEST.md").splitlines()[:190]
    roadmap = read_text("docs/ROADMAP.md")
    state = read_text("docs/DEVELOPMENT_STATE.md")
    growth = read_text("docs/PLATFORM_GROWTH_STRATEGY_2026_09_28.md")

    assert any("Repeat Orders & Business Continuity" in line for line in manifest)
    assert any(
        "architecture/operator_interface_contract.json" in line for line in manifest
    )
    assert "Phase 3A — Repeat Orders & Business Continuity" in roadmap
    assert "architecture/operator_interface_contract.json" in roadmap
    assert "Repeat Orders & Business Continuity" in state
    assert "architecture/operator_interface_contract.json" in state
    assert "Repeat Orders & Business Continuity" in growth
    assert "architecture/operator_interface_contract.json" in growth


def test_public_experience_and_adversarial_gate_reference_ui_boundary() -> None:
    public = load_json("architecture/public_client_experience_contract.json")
    gate = load_json("architecture/global_adversarial_survivability_gate_contract.json")

    assert (
        public["experience_surfaces"]["operator_web"]["interface_contract"]
        == "architecture/operator_interface_contract.json"
    )
    assert "operator_interface_and_capability_visibility" in gate["scope"]
    assert "operator_interface_authority_and_causal_continuity_check" in gate[
        "required_outputs"
    ]


def test_ui_contract_is_referenced_by_the_business_plane_boundaries() -> None:
    interface = load_json("architecture/operator_interface_contract.json")
    business = load_json("architecture/business_plane_boundary_contract.json")
    growth_contract = load_json("architecture/platform_growth_strategy_contract.json")
    repeat = load_json("architecture/repeat_order_transition_contract.json")

    assert (
        interface["specialized_workspaces"]["repeat_orders"][
            "bitrix_recurring_engine_is_not_reimplemented"
        ]
        is True
    )
    assert business["repeat_business"]["no_dual_live_ownership"] is True
    assert business["operator_continuity"]["interface_contract"] == (
        "architecture/operator_interface_contract.json"
    )
    assert (
        growth_contract["experience_surfaces"]["operator_web"]["interface_contract"]
        == "architecture/operator_interface_contract.json"
    )
    assert repeat["purge_policy"]["never_purge_before_readback_verification"] is True
