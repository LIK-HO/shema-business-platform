import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load() -> dict:
    return json.loads(
        (ROOT / "architecture" / "repeat_order_transition_contract.json").read_text(
            encoding="utf-8"
        )
    )


def test_local_repeat_order_mode_is_bounded() -> None:
    p = load()
    assert "SHEMA_LOCAL_LIVE" in p["modes"]
    assert p["interim_authority"]["before_bitrix_handoff"] == (
        "shema_order_and_limited_economics"
    )
    assert p["local_repeat_tool"]["past_order_is_immutable"] is True


def test_cutover_never_purges_before_verified_bitrix_readback() -> None:
    p = load()
    assert "READBACK_VERIFIED" in p["migration_state_machine"]
    assert "PURGED_FROZEN" in p["migration_state_machine"]
    assert p["purge_policy"]["never_purge_before_bitrix_ack"] is True
    assert p["purge_policy"]["never_purge_before_readback_verification"] is True
    assert p["purge_policy"]["frozen_lineage_fields"]


def test_ui_hides_transferred_order_cleanly() -> None:
    p = load()
    assert p["ui_behavior"]["after_purged_frozen"] == (
        "remove_order_and_economics_tabs_without_layout_reflow"
    )
    assert p["ui_behavior"]["no_empty_broken_tabs"] is True
