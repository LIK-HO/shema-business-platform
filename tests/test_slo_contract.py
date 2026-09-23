import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def test_slo_contract_is_explicit_and_bounded() -> None:
    contract = json.loads(
        (ROOT / "architecture" / "slo_contract.json").read_text(encoding="utf-8")
    )
    assert contract["version"] == "1.5-slo-baseline"
    assert contract["measurement_window"] == "30d"
    assert contract["policy"]["targets_are_initial_and_must_be_recalibrated_from_real_traffic"]
    assert {item["id"] for item in contract["slis"]} == {
        "api_availability",
        "critical_mutation_success",
        "job_recovery",
        "outbox_lag",
        "external_effect_completion",
        "api_latency",
    }
    for item in contract["slis"]:
        assert 0 < item["target"] <= 1
        assert item["window"] == "30d"
        assert item["good_events"] and item["total_events"] and item["source"]
    assert contract["error_budget"]["calculation"] == "1 - target"
    assert len(contract["error_budget"]["burn_policy"]) == 2


def test_slo_contract_does_not_change_kernel_authority() -> None:
    contract = json.loads(
        (ROOT / "architecture" / "slo_contract.json").read_text(encoding="utf-8")
    )
    assert contract["policy"]["no_slo_target_changes_kernel_semantics"] is True
