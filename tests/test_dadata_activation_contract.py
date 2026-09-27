from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_dadata_activation_contract_is_fail_closed() -> None:
    payload = json.loads(
        (
            ROOT
            / "architecture"
            / "dadata_activation_contract.json"
        ).read_text(encoding="utf-8")
    )
    assert payload["network_execution_enabled"] is False
    assert payload["automatic_activation"] is False
    assert payload["live_ci_traffic"] is False
    assert payload["provider_id"] == "dadata_organization_api"
    assert payload["execution_kind"] == "counterparty_lookup"
    assert "full_release_ci" in payload["required_gates"]
    assert "explicit_operator_authorization" in payload["required_gates"]
    assert payload["authority_rules"]["provider_output_is_canonical_truth"] is False
    assert payload["fallback_provider"] == "none"
