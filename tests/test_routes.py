"""Smoke-Tests fuer die HTTP-Routen (Pages + API) ohne echtes Netzwerk."""

from __future__ import annotations

from collections.abc import Iterator

import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient

from dashboard.app import create_app
from dashboard.config import Settings
from dashboard.dependencies import get_service
from dashboard.indicators import stats
from dashboard.indicators.models import Indicator, IndicatorSnapshot, SnapshotStatus
from dashboard.indicators.registry import IndicatorRegistry, get_registry
from dashboard.routes.pages import _grouped

_BROKEN_ID = "atx"


def _ok_snapshot(indicator: Indicator) -> IndicatorSnapshot:
    idx = pd.date_range("2016-01-01", periods=400, freq="D")
    values = np.sin(np.linspace(0, 20, 400)) * 10 + 100
    series = pd.Series(values, index=idx, dtype="float64")
    snapshot_stats = stats.build_snapshot_stats(
        series, direction=indicator.direction, thresholds=indicator.thresholds
    )
    return IndicatorSnapshot(
        indicator=indicator,
        status=SnapshotStatus.OK,
        stats=snapshot_stats,
        series_dates=[d.strftime("%Y-%m-%d") for d in series.index],
        series_values=[float(v) for v in series.to_numpy()],
    )


class FakeService:
    """Liefert deterministische Snapshots fuer alle Indikatoren (einer als Fehler)."""

    def __init__(self, registry: IndicatorRegistry) -> None:
        self._registry = registry

    def _snapshot(self, indicator: Indicator) -> IndicatorSnapshot:
        if indicator.id == _BROKEN_ID:
            return IndicatorSnapshot(
                indicator=indicator, status=SnapshotStatus.ERROR, error="Quelle down"
            )
        return _ok_snapshot(indicator)

    async def get_all_snapshots(self) -> list[IndicatorSnapshot]:
        return [self._snapshot(ind) for ind in self._registry.all()]

    async def get_snapshot_by_id(self, indicator_id: str) -> IndicatorSnapshot:
        return self._snapshot(self._registry.get(indicator_id))


@pytest.fixture
def test_client() -> Iterator[TestClient]:
    settings = Settings(_env_file=None, fred_api_key="test-key")  # type: ignore[call-arg,arg-type]
    app = create_app(settings)
    fake = FakeService(get_registry())
    app.dependency_overrides[get_service] = lambda: fake
    with TestClient(app) as client:
        yield client


def test_dashboard_renders(test_client: TestClient) -> None:
    resp = test_client.get("/")
    assert resp.status_code == 200
    assert "Investor Dashboard" in resp.text
    assert "S&amp;P 500" in resp.text or "S&P 500" in resp.text
    assert "Credit Spreads" in resp.text  # Kategorie-Label


def test_dashboard_shows_error_card(test_client: TestClient) -> None:
    resp = test_client.get("/")
    assert "Quelle nicht verfügbar" in resp.text


def test_cards_partial(test_client: TestClient) -> None:
    resp = test_client.get("/partials/cards")
    assert resp.status_code == 200
    assert 'id="grid"' in resp.text


def test_indicator_detail_ok(test_client: TestClient) -> None:
    resp = test_client.get("/indicator/vix")
    assert resp.status_code == 200
    assert "Was misst er?" in resp.text
    assert "detail-chart" in resp.text
    assert "histogram" in resp.text


def test_indicator_detail_unknown_404(test_client: TestClient) -> None:
    resp = test_client.get("/indicator/does_not_exist")
    assert resp.status_code == 404


def test_api_list(test_client: TestClient) -> None:
    resp = test_client.get("/api/indicators")
    assert resp.status_code == 200
    data = resp.json()
    assert len(data) == len(get_registry().ids)
    assert data[0]["indicator"]["id"]


def test_api_single(test_client: TestClient) -> None:
    resp = test_client.get("/api/indicator/sp500")
    assert resp.status_code == 200
    assert resp.json()["indicator"]["id"] == "sp500"


def test_api_unknown_404(test_client: TestClient) -> None:
    assert test_client.get("/api/indicator/nope").status_code == 404


def test_healthz(test_client: TestClient) -> None:
    resp = test_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


def test_priority_sorts_first_within_category() -> None:
    low = Indicator(id="a", name="A", category="rates", source="fred", series_id="X", unit="%")
    high = Indicator(
        id="b", name="B", category="rates", source="fred", series_id="Y", unit="%", priority=3
    )
    registry = IndicatorRegistry([low, high])
    snaps = [_ok_snapshot(low), _ok_snapshot(high)]

    sections = _grouped(snaps, registry)
    rates = dict(sections)["rates"]
    assert [s.indicator.id for s in rates] == ["b", "a"]  # Prio 3 vor Prio 0
