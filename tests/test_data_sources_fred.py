"""Tests fuer die FRED-Datenquelle (respx-Mock + Fixture)."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.fred import FredSource


@respx.mock
async def test_fetch_happy_path(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    route = respx.get(url__startswith=f"{settings.fred_base_url}/series/observations").mock(
        return_value=httpx.Response(200, text=load_fixture("fred_dgs10.json"))
    )
    source = FredSource(settings, client)

    series = await source.fetch("DGS10")

    assert route.called
    assert len(series) == 5  # eine "." wurde uebersprungen
    assert series.iloc[-1] == pytest.approx(4.55)
    assert series.index.is_monotonic_increasing


@respx.mock
async def test_missing_key_raises(client: httpx.AsyncClient) -> None:
    settings = Settings(_env_file=None)  # type: ignore[call-arg]
    source = FredSource(settings, client)
    with pytest.raises(RuntimeError, match="FRED_API_KEY"):
        await source.fetch("DGS10")


@respx.mock
async def test_server_error_then_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.fred_base_url).mock(return_value=httpx.Response(500))
    source = FredSource(settings, client)
    with pytest.raises(DataSourceError, match="HTTP-Fehler"):
        await source.fetch("DGS10")


@respx.mock
async def test_empty_observations_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.fred_base_url).mock(
        return_value=httpx.Response(200, text=json.dumps({"observations": []}))
    )
    source = FredSource(settings, client)
    with pytest.raises(DataSourceError, match="Keine gueltigen"):
        await source.fetch("DGS10")
