"""FastAPI-Dependency-Provider (lesen aus app.state, vermeiden Globals/Zyklen)."""

from __future__ import annotations

from fastapi import Request
from fastapi.templating import Jinja2Templates

from dashboard.indicators.registry import IndicatorRegistry
from dashboard.indicators.service import IndicatorService


def get_service(request: Request) -> IndicatorService:
    """Liefert den IndicatorService aus dem App-State."""
    service: IndicatorService = request.app.state.service
    return service


def get_templates(request: Request) -> Jinja2Templates:
    """Liefert die Jinja2Templates aus dem App-State."""
    templates: Jinja2Templates = request.app.state.templates
    return templates


def get_registry_dep(request: Request) -> IndicatorRegistry:
    """Liefert die Registry aus dem App-State."""
    registry: IndicatorRegistry = request.app.state.registry
    return registry
