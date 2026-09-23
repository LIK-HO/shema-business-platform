import json
from pathlib import Path

from shema_platform.platform.release import validate_release_tree


ROOT = Path(__file__).resolve().parents[1]


def test_release_candidate_contract_is_complete() -> None:
    contract = json.loads(
        (ROOT / "architecture/release_candidate_contract.json").read_text(
            encoding="utf-8"
        )
    )

    assert contract["version"] == "1.5-release-candidate-contract"
    assert contract["release_version"] == "1.5.0"
    assert contract["frozen_kernel_contract_version"] == "1.4"
    assert contract["core_maturity_contract_version"] == "1.5-core-maturity"
    assert set(contract["required_certification_elements"]) == {
        "B1",
        "B2",
        "B3",
        "B4",
        "B5",
        "B6",
        "B7",
        "B8",
        "B9",
    }
    assert contract["final_freeze_policy"][
        "kernel_semantics_frozen_after_green_release_candidate"
    ] is True
    assert contract["final_freeze_policy"]["new_features_stay_outside_core"] is True
    assert contract["no_production_deployment_or_merge_authorization"] is True


def test_release_tree_accepts_candidate_contract() -> None:
    manifest = validate_release_tree(ROOT)

    assert manifest.application_version == "1.5.0"
    assert manifest.kernel_contract_version == "1.4"
    assert manifest.core_maturity_contract_version == "1.5-core-maturity"
    assert manifest.release_candidate_contract_version == "1.5-release-candidate-contract"
    assert manifest.latest_migration_version == 9
