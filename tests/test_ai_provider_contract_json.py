from json import loads
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def read_json(path: str) -> dict:
    return loads((ROOT / path).read_text())


def test_ai_provider_adapter_machine_contract_is_bounded() -> None:
    contract = read_json("architecture/ai_provider_adapter_contract.json")

    assert contract["gateway"] == "shema_platform.application.ai.AIGateway"
    assert contract["adapter_interface"]["name"] == (
        "shema_platform.application.ai_provider.AIProviderAdapter"
    )
    assert contract["adapter_interface"]["methods"] == [
        "describe",
        "readiness",
        "execute",
    ]
    assert contract["adapter_interface"]["provider_kinds"] == ["cloud", "local"]
    assert contract["adapter_interface"]["local_free_commercial_use_required"] is True
    assert contract["failure_semantics"]["adapter_owned_retries"] is False
    assert contract["failure_semantics"]["implicit_cloud_to_local_fallback"] is False
    assert contract["failure_semantics"]["implicit_local_to_cloud_fallback"] is False
    assert contract["security_and_authority"]["adapter_has_no_persistence_port"] is True
    assert contract["security_and_authority"]["adapter_has_no_canonical_business_state_authority"] is True
    assert contract["scope"]["concrete_provider_implementation"] is False
    assert contract["scope"]["kernel_semantic_change"] is False
