import json
from pathlib import Path

ROOT = Path(__file__).parents[1]


def load() -> dict:
    return json.loads(
        (ROOT / "architecture" / "public_intake_data_plane_contract.json").read_text(
            encoding="utf-8"
        )
    )


def test_intake_is_separate_and_durable() -> None:
    p = load()
    assert p["storage"]["physical_boundary"] == "dedicated_postgresql_database"
    assert p["storage"]["shema_canonical_db_direct_write"] is False
    assert p["notification_policy"]["durable_in_intake_db"] is True
    assert "atomic_intake_request_plus_outbox_commit" in p["write_flow"]


def test_intake_recovery_and_prompt_injection_boundaries_are_explicit() -> None:
    p = load()
    assert p["recovery"]["shema_unavailable_does_not_lose_accepted_intake"] is True
    assert p["recovery"]["outbox_replay_is_idempotent"] is True
    assert p["untrusted_text"]["client_text_is_data_not_instruction"] is True
    assert p["untrusted_text"]["prompt_injection_must_not_become_system_instruction"] is True
