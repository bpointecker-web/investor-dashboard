"""JSON-API: maschinenlesbarer Zugriff auf Indikator-Snapshots."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException

from dashboard.dependencies import get_registry_dep, get_service
from dashboard.indicators.models import IndicatorSnapshot
from dashboard.indicators.registry import IndicatorRegistry
from dashboard.indicators.service import IndicatorService

router = APIRouter(prefix="/api")


@router.get("/indicators")
async def list_indicators(
    service: Annotated[IndicatorService, Depends(get_service)],
) -> list[IndicatorSnapshot]:
    """Liefert Snapshots aller Indikatoren als JSON."""
    return await service.get_all_snapshots()


@router.get("/indicator/{indicator_id}")
async def get_indicator(
    indicator_id: str,
    service: Annotated[IndicatorService, Depends(get_service)],
    registry: Annotated[IndicatorRegistry, Depends(get_registry_dep)],
) -> IndicatorSnapshot:
    """Liefert den Snapshot eines einzelnen Indikators (ID via Whitelist geprueft)."""
    if not registry.has(indicator_id):
        raise HTTPException(status_code=404, detail=f"Unbekannter Indikator: {indicator_id}")
    return await service.get_snapshot_by_id(indicator_id)
