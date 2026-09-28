from __future__ import annotations

from urllib.error import HTTPError
from urllib.request import Request

import pytest

from shema_platform.foundation.secure_http import _NoRedirectHandler, secure_urlopen


def test_redirect_handler_fails_closed() -> None:
    handler = _NoRedirectHandler()
    request = Request("https://allowed.example/")
    error = HTTPError(
        request.full_url,
        302,
        "redirect",
        {"Location": "http://169.254.169.254/latest/meta-data/"},
        None,
    )

    with pytest.raises(HTTPError, match="redirects are forbidden"):
        handler.redirect_request(
            request,
            None,  # type: ignore[arg-type]
            302,
            "redirect",
            error.headers,
            "http://169.254.169.254/latest/meta-data/",
        )


def test_secure_urlopen_does_not_follow_redirects(monkeypatch) -> None:
    class RedirectResponse:
        status = 302

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def read(self, size: int = -1) -> bytes:
            return b""

        @property
        def headers(self):
            return {"Location": "http://127.0.0.1:9/"}

    def fail_open(*args, **kwargs):
        raise HTTPError(
            "https://allowed.example/",
            302,
            "redirect",
            {"Location": "http://127.0.0.1:9/"},
            None,
        )

    monkeypatch.setattr(
        "shema_platform.foundation.secure_http._NO_REDIRECT_OPENER.open",
        fail_open,
    )

    with pytest.raises(HTTPError, match="redirect"):
        secure_urlopen(Request("https://allowed.example/"), timeout=1)
