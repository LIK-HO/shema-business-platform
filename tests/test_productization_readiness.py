from shema_platform.platform import productization_readiness


def repo_root():
    from pathlib import Path

    return Path(__file__).resolve().parents[1]


def test_v15_productization_readiness_is_blocked_only_by_provider_side_max_gap() -> None:
    report = productization_readiness.assess_v15_productization_readiness(repo_root())

    assert report.status == "blocked"
    assert report.production_ready is False
    assert report.scope_safe is True

    assert {
        "MAX provider-side idempotency contract is not documented/certified",
        "MAX provider-side reconciliation contract is not documented/certified",
    } == set(report.blockers)

    passed = {check.key for check in report.checks if check.passed}
    assert {
        "frozen_kernel",
        "release_contract_baseline",
        "ai_promotion",
        "ai_activation_rehearsal",
        "max_platform_effect_safety",
        "max_ambiguous_fail_closed",
        "quarantine_read_model",
        "scope_safety",
    } <= passed


def test_v15_readiness_does_not_claim_production_when_max_provider_gap_exists(
    monkeypatch,
) -> None:
    module = productization_readiness

    original = module._read_json

    def fake_read_json(root, relative_path):
        value = original(root, relative_path)
        if relative_path == "architecture/max_provider_evidence_contract.json":
            value["external_effect_safety"][
                "provider_side_idempotency_contract_documented"
            ] = True
            value["external_effect_safety"][
                "provider_side_reconciliation_contract_documented"
            ] = True
        return value

    monkeypatch.setattr(module, "_read_json", fake_read_json)

    report = module.assess_v15_productization_readiness(repo_root())
    assert report.production_ready is True
