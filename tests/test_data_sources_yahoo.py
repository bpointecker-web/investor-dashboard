"""Tests fuer die Yahoo-Datenquelle (Chart-API, respx-Mock + Fixture)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.yahoo import YahooSource


@respx.mock
async def test_fetch_maps_symbol_and_parses(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    route = respx.get(url__startswith=f"{settings.yahoo_base_url}/v8/finance/chart").mock(
        return_value=httpx.Response(200, text=load_fixture("yahoo_gspc.json"))
    )
    source = YahooSource(settings, client)

    series = await source.fetch("^spx")  # stooq-Symbol -> Yahoo ^GSPC

    assert route.called
    assert "%5EGSPC" in str(route.calls.last.request.url)  # ^GSPC korrekt encodiert
    assert len(series) == 2  # null-Close wurde verworfen
    assert series.iloc[-1] == pytest.approx(6040.04)
    assert series.index.is_monotonic_increasing


async def test_unknown_symbol_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    source = YahooSource(settings, client)
    with pytest.raises(DataSourceError, match="Kein Yahoo-Symbol-Mapping"):
        await source.fetch("nicht_gemappt")


@respx.mock
async def test_missing_chart_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.yahoo_base_url).mock(
        return_value=httpx.Response(200, json={"foo": "bar"})
    )
    source = YahooSource(settings, client)
    with pytest.raises(DataSourceError, match="kein 'chart'"):
        await source.fetch("^spx")
