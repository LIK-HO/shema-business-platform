import json
from pathlib import Path


def test_openai_provider_contract_is_fail_closed_and_external() -> None:
    contract = json.loads(
        (
            Path(__file__).resolve().parents[1]
            / "architecture/openai_provider_contract.json"
        ).read_text()
    )

    assert contract["provider_id"] == "openai"
    assert contract["api"]["base_url"] == "https://api.openai.com"
    assert contract["api"]["responses_endpoint"] == "/v1/responses"
    assert contract["api"]["store"] is False
    assert contract["activation"]["production_auto_activation"] is False
    assert contract["activation"]["missing_secret_behavior"] == "fail"
    assert contract["output_integrity"]["require_usage"] is True
    assert contract["retry_policy"]["automatic_provider_retry"] is False
    assert contract["persistence"]["canonical_business_truth"] is False
