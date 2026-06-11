"""Tests fuer die CoinGecko-Datenquelle (respx-Mock + JSON-Fixture)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.coingecko import CoinGeckoSource


@respx.mock
async def test_fetch_happy_path(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    respx.get(url__startswith=f"{settings.coingecko_base_url}/coins/bitcoin").mock(
        return_value=httpx.Response(200, text=load_fixture("coingecko_bitcoin.json"))
    )
    source = CoinGeckoSource(settings, client)

    series = await source.fetch("bitcoin")

    # 6 Punkte, davon 2 am selben Tag -> 5 eindeutige Tage
    assert len(series) == 5
    assert series.index.is_monotonic_increasing
    assert series.index.is_unique


@respx.mock
async def test_free_tier_caps_days_at_365(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    # history_years=10 -> ~3653 Tage, ohne Key aber auf 365 begrenzt (sonst HTTP 401).
    route = respx.get(url__startswith=settings.coingecko_base_url).mock(
        return_value=httpx.Response(200, text=load_fixture("coingecko_bitcoin.json"))
    )
    source = CoinGeckoSource(settings, client)

    await source.fetch("bitcoin")

    assert route.calls.last.request.url.params["days"] == "365"


@respx.mock
async def test_missing_prices_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.coingecko_base_url).mock(
        return_value=httpx.Response(200, json={"foo": "bar"})
    )
    source = CoinGeckoSource(settings, client)
    with pytest.raises(DataSourceError, match="keine 'prices'"):
        await source.fetch("bitcoin")
