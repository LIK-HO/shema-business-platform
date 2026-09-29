from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

_WEB_ROOT = Path(__file__).resolve().parent / "web"
_PUBLIC_ROUTES = ("/", "/request", "/operator", "/max", "/system")


def install_web_operator_surface(app: FastAPI) -> None:
    """Install one same-origin Web/PWA surface without adding business authority."""

    app.mount("/web", StaticFiles(directory=_WEB_ROOT), name="web-assets")

    async def serve_index() -> FileResponse:
        return FileResponse(_WEB_ROOT / "index.html")

    for route in _PUBLIC_ROUTES:
        app.add_api_route(
            route,
            serve_index,
            methods=["GET"],
            include_in_schema=False,
        )
