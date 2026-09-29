from __future__ import annotations

from shema_platform.foundation.safe_errors import safe_error_detail


def test_safe_error_detail_redacts_common_credentials_and_tokens() -> None:
    raw = (
        "Authorization: Bearer super-secret-token "
        "url=https://user:password@example.test/api "
        "api_key=deadbeef secret=top-secret"
    )

    safe = safe_error_detail(raw)

    assert "super-secret-token" not in safe
    assert "password@" not in safe
    assert "deadbeef" not in safe
    assert "top-secret" not in safe
    assert "<redacted>" in safe


def test_safe_error_detail_is_bounded() -> None:
    safe = safe_error_detail("x" * 10_000)

    assert len(safe) == 1_024
    assert safe.endswith("...")
