"""Tests fuer die stooq-Datenquelle (respx-Mock + CSV-Fixture)."""

from __future__ import annotations

from collections.abc import Callable

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.stooq import StooqSource


@respx.mock
async def test_fetch_happy_path(
    settings: Settings,
    client: httpx.AsyncClient,
    load_fixture: Callable[[str], str],
) -> None:
    respx.get(url__startswith=settings.stooq_base_url).mock(
        return_value=httpx.Response(200, text=load_fixture("stooq_spx.csv"))
    )
    source = StooqSource(settings, client)

    series = await source.fetch("^spx")

    assert len(series) == 5
    assert series.iloc[-1] == pytest.approx(5906.94)
    assert series.index.is_monotonic_increasing


@respx.mock
async def test_no_data_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.stooq_base_url).mock(
        return_value=httpx.Response(200, text="No data")
    )
    source = StooqSource(settings, client)
    with pytest.raises(DataSourceError, match="keine Daten"):
        await source.fetch("invalid")


@respx.mock
async def test_missing_close_column_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.stooq_base_url).mock(
        return_value=httpx.Response(200, text="Date,Open\n2024-01-01,1.0\n")
    )
    source = StooqSource(settings, client)
    with pytest.raises(DataSourceError, match="Spalten fehlen"):
        await source.fetch("^spx")
