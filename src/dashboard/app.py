"""FastAPI App-Factory: Lifespan, Dependency-Injection, Templates, Routing."""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import httpx
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from dashboard import formatting
from dashboard.config import Settings, get_settings
from dashboard.indicators.registry import IndicatorRegistry, get_registry
from dashboard.indicators.service import IndicatorService
from dashboard.logging_setup import configure_logging, get_logger
from dashboard.routes import api, pages

_BASE_DIR = Path(__file__).parent
_TEMPLATES_DIR = _BASE_DIR / "templates"
_STATIC_DIR = _BASE_DIR / "static"

_log = get_logger("app")


def _build_templates(settings: Settings) -> Jinja2Templates:
    """Erstellt die Jinja2-Umgebung und registriert Formatierungs-Helfer."""
    templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))
    templates.env.globals.update(
        format_number=formatting.format_number,
        format_percent=formatting.format_percent,
        format_signed=formatting.format_signed,
        change_class=formatting.change_class,
        band_dot=formatting.band_dot,
        band_label=formatting.band_label,
        category_label=formatting.category_label,
        source_url=formatting.source_url,
        format_richtext=formatting.format_richtext,
        # Statischer Export (GitHub Pages): URL-Praefix + Feature-Ausblendung.
        base_path=settings.base_path,
        static_build=settings.static_build,
    )
    return templates


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Erzeugt den geteilten HTTP-Client und den Service; raeumt am Ende auf."""
    settings: Settings = app.state.settings
    registry: IndicatorRegistry = app.state.registry
    headers = {"User-Agent": settings.user_agent}
    async with httpx.AsyncClient(headers=headers) as client:
        app.state.service = IndicatorService(settings, registry, client)
        _log.info("startup", indicators=len(registry.ids))
        yield
    _log.info("shutdown")


def create_app(settings: Settings | None = None) -> FastAPI:
    """Baut die FastAPI-App. Fail-Fast ohne FRED-API-Key."""
    settings = settings or get_settings()
    configure_logging(level=settings.log_level, json_logs=settings.log_json)
    settings.require_fred_key()  # Fail-Fast mit klarer Fehlermeldung

    app = FastAPI(title="Investor Dashboard", version="0.1.0", lifespan=_lifespan)
    app.state.settings = settings
    app.state.registry = get_registry()
    app.state.templates = _build_templates(settings)

    app.mount("/static", StaticFiles(directory=str(_STATIC_DIR)), name="static")
    app.include_router(pages.router)
    app.include_router(api.router)
    return app
