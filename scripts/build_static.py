"""Baut das Dashboard als statische Site fuer GitHub Pages.

Rendert alle Seiten ueber die bestehende FastAPI-App (TestClient) nach ``dist/``:
  - /                      -> dist/index.html
  - /indicator/{id}        -> dist/indicator/<id>/index.html  (alle IDs aus Registry)
  - /api/indicators        -> dist/api/indicators.json
  - static-Assets          -> dist/static/
  - .nojekyll              -> verhindert Jekyll-Verarbeitung auf Pages

Aufruf (lokal oder in GitHub Actions):
    uv run python scripts/build_static.py
Erwartet ``FRED_API_KEY`` in der Umgebung (oder .env). ``BASE_PATH`` und
``STATIC_BUILD`` werden gesetzt, falls nicht vorhanden.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

# Muss VOR dem Settings-Import gesetzt sein (Pydantic liest Env beim Instanziieren).
os.environ.setdefault("BASE_PATH", "/investor-dashboard")
os.environ.setdefault("STATIC_BUILD", "1")

from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.config import Settings
from dashboard.indicators.registry import get_registry
from dashboard.logging_setup import get_logger

_log = get_logger("build_static")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DIST_DIR = PROJECT_ROOT / "dist"
STATIC_SRC = PROJECT_ROOT / "src" / "dashboard" / "static"


def _write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def build() -> int:
    """Rendert die komplette Site. Rueckgabe: Anzahl der OK-Karten."""
    if DIST_DIR.exists():
        shutil.rmtree(DIST_DIR)
    DIST_DIR.mkdir(parents=True)

    settings = Settings()
    app = create_app(settings)
    registry = get_registry()

    with TestClient(app) as client:
        # Startseite (loest alle 39 Abrufe aus; danach bedienen sich die
        # Detailseiten aus dem warmen In-Memory-Cache).
        response = client.get("/")
        response.raise_for_status()
        _write(DIST_DIR / "index.html", response.text)
        _log.info("page_built", page="index")

        for indicator_id in registry.ids:
            detail = client.get(f"/indicator/{indicator_id}")
            detail.raise_for_status()
            _write(DIST_DIR / "indicator" / indicator_id / "index.html", detail.text)
        _log.info("pages_built", detail_pages=len(registry.ids))

        api = client.get("/api/indicators")
        api.raise_for_status()
        _write(DIST_DIR / "api" / "indicators.json", api.text)

    shutil.copytree(STATIC_SRC, DIST_DIR / "static")
    (DIST_DIR / ".nojekyll").touch()

    snapshots = api.json()
    ok = sum(1 for snap in snapshots if snap["status"] == "ok")
    failed = [snap["indicator"]["id"] for snap in snapshots if snap["status"] != "ok"]
    _log.info("build_done", cards_ok=ok, cards_total=len(snapshots), failed=failed)
    return ok


def main() -> None:
    ok = build()
    if ok == 0:
        # Komplett leeres Dashboard deutet auf ein strukturelles Problem
        # (z.B. fehlender Key) -> Build scheitern lassen statt leere Site deployen.
        _log.error("build_failed", reason="Keine einzige Karte konnte geladen werden.")
        sys.exit(1)


if __name__ == "__main__":
    main()
