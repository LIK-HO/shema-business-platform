import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load() -> dict:
    return json.loads(
        (ROOT / "architecture" / "counterparty_monitoring_contract.json").read_text(
            encoding="utf-8"
        )
    )


def test_exact_identifier_uses_counterparty_mode() -> None:
    p = load()
    assert p["search_mode_detection"]["exact_identifier_auto_detection"] is True
    assert "Проверить контрагента" in p["operator_flow"]["primary_actions"]


def test_monitoring_and_favorites_are_separate_and_daily() -> None:
    p = load()
    assert p["operator_flow"]["monitoring_is_visually_distinct"] is True
    assert p["operator_flow"]["favorites_scope"] == "operator_personal"
    assert p["monitoring"]["default_frequency"] == "daily"
    assert p["monitoring"]["deterministic_change_detection"] is True


def test_monitoring_is_checkpointed_and_duplicate_safe() -> None:
    p = load()
    assert p["monitoring"]["checkpointed_batch"] is True
    assert p["monitoring"]["duplicate_change_suppression"] is True
    assert p["monitoring"]["unavailable_source_is_not_a_change"] is True
