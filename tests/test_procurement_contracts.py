import json
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load(name: str):
    return json.loads((ROOT / "architecture" / name).read_text(encoding="utf-8"))


def test_gosplan_contract_keeps_live_execution_disabled_and_source_observation_separate():
    payload = load("gosplan_procurement_adapter_contract.json")
    assert payload["execution"]["default_enabled"] is False
    assert payload["execution"]["live_ci_traffic"] is False
    assert payload["data_governance"]["provider_output_is_canonical_truth"] is False
    assert payload["application_controls"]["no_html_scraping_fallback"] is True


def test_monitoring_contract_is_cursor_based_and_deduplicated():
    payload = load("procurement_monitoring_contract.json")
    assert payload["requirements"]["cursor_based"] is True
    assert payload["requirements"]["idempotent_polling"] is True
    assert payload["requirements"]["deduplicate_by_provider_id_and_external_id"] is True
    assert payload["safety"]["no_automatic_tender_submission"] is True
