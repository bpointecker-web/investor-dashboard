"""Tests fuer CNN- und CBOE-Datenquellen (CBOE bezieht Put/Call ueber CNN)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.cboe import CboeSource
from dashboard.data_sources.cnn import CnnSource


@respx.mock
async def test_cnn_fear_greed(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    respx.get(url__startswith=settings.cnn_fear_greed_url).mock(
        return_value=httpx.Response(200, text=load_fixture("cnn_graphdata.json"))
    )
    series = await CnnSource(settings, client).fetch("fear_greed")
    assert len(series) == 2
    assert series.iloc[-1] == pytest.approx(28.7)


@respx.mock
async def test_cboe_put_call_via_cnn(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    respx.get(url__startswith=settings.cnn_fear_greed_url).mock(
        return_value=httpx.Response(200, text=load_fixture("cnn_graphdata.json"))
    )
    series = await CboeSource(settings, client).fetch("total")
    assert len(series) == 2
    assert series.iloc[-1] == pytest.approx(0.78)


@respx.mock
async def test_cnn_unknown_series_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    source = CnnSource(settings, client)
    with pytest.raises(DataSourceError, match="Unbekannte CNN-Serie"):
        await source.fetch("nonsense")


@respx.mock
async def test_cnn_missing_key_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.cnn_fear_greed_url).mock(
        return_value=httpx.Response(200, json={"foo": "bar"})
    )
    source = CnnSource(settings, client)
    with pytest.raises(DataSourceError, match="enthaelt"):
        await source.fetch("fear_greed")
