"""Tests fuer die CFTC-Datenquelle (respx-Mock + Fixture)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.cftc import CftcSource


@respx.mock
async def test_fetch_computes_spec_net(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    respx.get(url__startswith=settings.cftc_base_url).mock(
        return_value=httpx.Response(200, text=load_fixture("cftc_sp500.json"))
    )
    source = CftcSource(settings, client)

    series = await source.fetch("13874A")

    assert len(series) == 2
    assert series.index.is_monotonic_increasing
    # Letzter Wert: 269402 - 490170 = -220768 (Non-Comm Long - Short)
    assert series.iloc[-1] == pytest.approx(-220768.0)


@respx.mock
async def test_empty_payload_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.cftc_base_url).mock(
        return_value=httpx.Response(200, json=[])
    )
    source = CftcSource(settings, client)
    with pytest.raises(DataSourceError, match="Keine COT-Daten"):
        await source.fetch("13874A")
