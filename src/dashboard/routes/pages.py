"""Serverseitig gerenderte Seiten (Dashboard + Detail) inkl. HTMX-Partial."""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from dashboard import charts
from dashboard.dependencies import get_registry_dep, get_service, get_templates
from dashboard.indicators.models import IndicatorSnapshot, SnapshotStatus
from dashboard.indicators.registry import IndicatorRegistry
from dashboard.indicators.service import IndicatorService

router = APIRouter()


@router.get("/healthz")
async def healthz() -> dict[str, str]:
    """Leichtgewichtiger Health-Check fuer den Hoster (kein Daten-Abruf)."""
    return {"status": "ok"}


def _sparklines(snapshots: list[IndicatorSnapshot]) -> dict[str, str]:
    """Baut Sparkline-JSON nur fuer erfolgreiche Snapshots."""
    return {
        snap.indicator.id: charts.sparkline_json(snap)
        for snap in snapshots
        if snap.status is SnapshotStatus.OK
    }


def _grouped(
    snapshots: list[IndicatorSnapshot], registry: IndicatorRegistry
) -> list[tuple[str, list[IndicatorSnapshot]]]:
    """Gruppiert Snapshots nach Kategorie (Manifest-Reihenfolge)."""
    order = [cat for cat in registry.by_category()]
    buckets: dict[str, list[IndicatorSnapshot]] = {cat.value: [] for cat in order}
    for snap in snapshots:
        buckets[snap.indicator.category.value].append(snap)
    # Innerhalb jeder Kategorie wichtige Indikatoren zuerst (stabil -> Manifest-Reihenfolge
    # bleibt bei gleicher Prioritaet erhalten).
    for cards in buckets.values():
        cards.sort(key=lambda s: -s.indicator.priority)
    return [(cat.value, buckets[cat.value]) for cat in order]


@router.get("/", response_class=HTMLResponse)
async def dashboard(
    request: Request,
    service: Annotated[IndicatorService, Depends(get_service)],
    registry: Annotated[IndicatorRegistry, Depends(get_registry_dep)],
    templates: Annotated[Jinja2Templates, Depends(get_templates)],
) -> HTMLResponse:
    """Rendert das vollstaendige Dashboard."""
    snapshots = await service.get_all_snapshots()
    return templates.TemplateResponse(
        request,
        "dashboard.html",
        {
            "sections": _grouped(snapshots, registry),
            "sparklines": _sparklines(snapshots),
            "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@router.get("/partials/cards", response_class=HTMLResponse)
async def cards_partial(
    request: Request,
    service: Annotated[IndicatorService, Depends(get_service)],
    registry: Annotated[IndicatorRegistry, Depends(get_registry_dep)],
    templates: Annotated[Jinja2Templates, Depends(get_templates)],
) -> HTMLResponse:
    """HTMX-Endpoint: rendert nur das Karten-Grid (Refresh-Button)."""
    snapshots = await service.get_all_snapshots()
    return templates.TemplateResponse(
        request,
        "_grid.html",
        {
            "sections": _grouped(snapshots, registry),
            "sparklines": _sparklines(snapshots),
            "last_refresh": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        },
    )


@router.get("/indicator/{indicator_id}", response_class=HTMLResponse)
async def indicator_detail(
    request: Request,
    indicator_id: str,
    service: Annotated[IndicatorService, Depends(get_service)],
    registry: Annotated[IndicatorRegistry, Depends(get_registry_dep)],
    templates: Annotated[Jinja2Templates, Depends(get_templates)],
) -> HTMLResponse:
    """Detail-Seite eines Indikators (ID gegen Whitelist geprueft)."""
    if not registry.has(indicator_id):
        raise HTTPException(status_code=404, detail=f"Unbekannter Indikator: {indicator_id}")

    snapshot = await service.get_snapshot_by_id(indicator_id)
    context: dict[str, object] = {"snapshot": snapshot}
    if snapshot.status is SnapshotStatus.OK:
        context["detail_chart"] = charts.detail_chart_json(snapshot)
    return templates.TemplateResponse(request, "indicator.html", context)
