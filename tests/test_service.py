"""Tests fuer den Service-Layer mit Mock-Datenquellen (kein echtes I/O)."""

from __future__ import annotations

import httpx
import pandas as pd
import pytest

from dashboard.config import Settings
from dashboard.data_sources.cache import TTLCache
from dashboard.data_sources.computed import ComputedSource
from dashboard.indicators.models import (
    Direction,
    Indicator,
    SnapshotStatus,
    SourceKind,
)
from dashboard.indicators.registry import IndicatorRegistry
from dashboard.indicators.service import IndicatorService
from tests.conftest import FakeSource


def _series(values: list[float], start: str = "2015-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype="float64")


@pytest.fixture
def indicators() -> list[Indicator]:
    return [
        Indicator(
            id="vix",
            name="VIX",
            category="volatility",
            source="fred",
            series_id="VIXCLS",
            unit="Index",
            direction=Direction.HIGHER_IS_STRESS,
        ),
        Indicator(
            id="hy",
            name="HY",
            category="credit",
            source="fred",
            series_id="BAMLH0A0HYM2",
            unit="bp",
            display_multiplier=100,
            decimals=0,
        ),
        Indicator(
            id="net_liq",
            name="Net Liq",
            category="liquidity",
            source="computed",
            formula="fred:WALCL - fred:WTREGEN",
            unit="Mrd USD",
        ),
        Indicator(
            id="broken",
            name="Broken",
            category="rates",
            source="fred",
            series_id="DOES_NOT_EXIST",
            unit="%",
        ),
    ]


@pytest.fixture
def service(
    settings: Settings,
    client: httpx.AsyncClient,
    indicators: list[Indicator],
) -> IndicatorService:
    registry = IndicatorRegistry(indicators)
    svc = IndicatorService(settings, registry, client, cache=TTLCache(60))
    fred = FakeSource(
        "fred",
        {
            "VIXCLS": _series([10, 12, 15, 40, 18, 20, 22]),
            "BAMLH0A0HYM2": _series([3.0, 3.5, 4.0, 8.0, 5.0]),  # in %, *100 -> bp
            "WALCL": _series([100.0, 110.0, 120.0]),
            "WTREGEN": _series([10.0, 10.0, 10.0]),
        },
    )
    # Fake-Quellen injizieren; Computed bleibt mit Service-Resolver verdrahtet.
    svc._sources = {
        SourceKind.FRED: fred,
        SourceKind.COMPUTED: ComputedSource(svc._resolve),
    }
    svc._fred = fred  # type: ignore[attr-defined]  # fuer Assertions
    return svc


async def test_happy_path_snapshot(service: IndicatorService) -> None:
    snap = await service.get_snapshot_by_id("vix")
    assert snap.status is SnapshotStatus.OK
    assert snap.stats is not None
    assert snap.stats.current == 22.0
    assert len(snap.series_values) == 7


async def test_display_multiplier_applied(service: IndicatorService) -> None:
    snap = await service.get_snapshot_by_id("hy")
    assert snap.status is SnapshotStatus.OK
    assert snap.stats is not None
    assert snap.stats.current == 500.0  # 5.0 * 100


async def test_computed_uses_resolver(service: IndicatorService) -> None:
    snap = await service.get_snapshot_by_id("net_liq")
    assert snap.status is SnapshotStatus.OK
    assert snap.stats is not None
    assert snap.stats.current == 110.0  # 120 - 10


async def test_error_is_card_level(service: IndicatorService) -> None:
    snap = await service.get_snapshot_by_id("broken")
    assert snap.status is SnapshotStatus.ERROR
    assert snap.error is not None
    assert snap.stats is None


async def test_get_all_one_error_does_not_break_others(
    service: IndicatorService,
) -> None:
    snaps = await service.get_all_snapshots()
    by_id = {s.indicator.id: s for s in snaps}
    assert by_id["vix"].status is SnapshotStatus.OK
    assert by_id["broken"].status is SnapshotStatus.ERROR
    assert sum(s.status is SnapshotStatus.OK for s in snaps) == 3


async def test_caching_avoids_refetch(service: IndicatorService) -> None:
    await service.get_snapshot_by_id("vix")
    await service.get_snapshot_by_id("vix")
    # FakeSource zaehlt jeden fetch -> trotz 2 Snapshots nur 1 echter Abruf
    assert service._fred.calls.count("VIXCLS") == 1  # type: ignore[attr-defined]
