"""Tests fuer die EZB-Datenquelle (respx-Mock + CSV-Antwort)."""

from __future__ import annotations

import httpx
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.ecb import EcbSource

_CSV = (
    "KEY,FREQ,TIME_PERIOD,OBS_VALUE,TITLE\n"
    "YC...SR_10Y,B,2026-06-16,2.95,AAA yield curve\n"
    "YC...SR_10Y,B,2026-06-17,2.98,AAA yield curve\n"
    "YC...SR_10Y,B,2026-06-18,2.99,AAA yield curve\n"
)


@respx.mock
async def test_fetch_happy_path(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.ecb_base_url).mock(
        return_value=httpx.Response(200, text=_CSV)
    )
    source = EcbSource(settings, client)

    series = await source.fetch("B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y")

    assert len(series) == 3
    assert series.iloc[-1] == pytest.approx(2.99)
    assert series.index.is_monotonic_increasing


@respx.mock
async def test_missing_columns_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.ecb_base_url).mock(
        return_value=httpx.Response(200, text="FOO,BAR\n1,2\n")
    )
    source = EcbSource(settings, client)
    with pytest.raises(DataSourceError, match="fehlen"):
        await source.fetch("irgendwas")


@respx.mock
async def test_empty_observations_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.ecb_base_url).mock(
        return_value=httpx.Response(200, text="TIME_PERIOD,OBS_VALUE\n2026-06-18,\n")
    )
    source = EcbSource(settings, client)
    with pytest.raises(DataSourceError, match="Keine gueltigen"):
        await source.fetch("irgendwas")
