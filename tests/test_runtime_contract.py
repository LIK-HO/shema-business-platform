from json import loads
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_v1_5_runtime_contract_preserves_frozen_kernel_boundary() -> None:
    contract = loads((ROOT / "architecture/runtime_contract.json").read_text())

    assert contract["version"] == "1.5.0"
    assert contract["baseline_kernel_contract"] == "1.4"
    assert contract["iam"]["authentication_boundary"] == "oidc_jwt_adapter"
    assert contract["iam"]["issuer_must_use_https"] is True
    assert contract["iam"]["jwks_must_use_https"] is True
    assert contract["iam"]["permission_materialization"] is True
    assert contract["iam"]["unknown_permissions_fail_closed"] is True
    assert contract["frozen_kernel_authority"] == [
        "postgresql",
        "domain_semantics",
        "authorization_policy",
        "evidence",
        "idempotency",
        "audit",
        "outbox",
    ]
