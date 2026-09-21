import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_runtime_contract_declares_production_gates_without_mutating_kernel_contract() -> None:
    runtime = json.loads((ROOT / "architecture/runtime_contract.json").read_text())
    kernel = json.loads((ROOT / "architecture/contract.json").read_text())

    assert runtime["version"] == "1.5.0"
    assert runtime["baseline_kernel_contract"] == "1.4"
    assert runtime["observability"]["telemetry_allowlist_based_redaction"] is True
    assert runtime["observability"]["telemetry_does_not_store_authorization_headers"] is True
    assert runtime["security"]["production_docs_disabled"] is True
    assert runtime["security"]["production_oidc_https_required"] is True
    assert runtime["supply_chain"]["dependency_audit"] == "pip-audit"
    assert runtime["recovery"]["durable_jobs"] is True
    assert kernel["version"] == "1.4"
