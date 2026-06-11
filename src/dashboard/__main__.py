"""Einstiegspunkt: startet den uvicorn-Server (`python -m dashboard`)."""

from __future__ import annotations

import os

import uvicorn

from dashboard.app import create_app
from dashboard.config import get_settings


def main() -> None:
    """Startet das Dashboard mit den Einstellungen aus der Umgebung.

    Cloud-Hoster (Render, Railway, Fly.io) injizieren den Port ueber ``$PORT`` -
    dieser hat Vorrang vor ``DASHBOARD_PORT``.
    """
    settings = get_settings()
    app = create_app(settings)
    port = int(os.environ.get("PORT") or settings.dashboard_port)
    uvicorn.run(
        app,
        host=settings.dashboard_host,
        port=port,
        log_config=None,  # structlog uebernimmt das Logging
    )


if __name__ == "__main__":
    main()
