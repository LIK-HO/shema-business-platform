from __future__ import annotations

from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener
from urllib.response import addinfourl


class _NoRedirectHandler(HTTPRedirectHandler):
    def redirect_request(
        self,
        req: Request,
        fp: addinfourl,
        code: int,
        msg: str,
        headers,
        newurl: str,
    ):
        raise HTTPError(
            req.full_url,
            code,
            "HTTP redirects are forbidden at the security boundary",
            headers,
            fp,
        )


_NO_REDIRECT_OPENER = build_opener(_NoRedirectHandler)


def secure_urlopen(request: Request, *, timeout: float):
    """Open an outbound request without following HTTP redirects."""

    return _NO_REDIRECT_OPENER.open(request, timeout=timeout)
