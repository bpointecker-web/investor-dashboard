"""Tests fuer die NAAIM-Datenquelle (xlsx-Parsing + Link-Discovery)."""

from __future__ import annotations

import io

import httpx
import pandas as pd
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.naaim import NaaimSource

_FILE_URL = "https://naaim.org/files/USE_Data-since-Inception_2026-06-03.xlsx"


def _naaim_xlsx_bytes() -> bytes:
    frame = pd.DataFrame(
        {
            "Date": ["2026-05-27", "2026-06-03"],
            "Mean/Average": [98.39, 86.82],
            "S&P 500": [7520.36, 7553.68],
        }
    )
    buffer = io.BytesIO()
    frame.to_excel(buffer, index=False, engine="openpyxl")
    return buffer.getvalue()


@respx.mock
async def test_fetch_discovers_and_parses(settings: Settings, client: httpx.AsyncClient) -> None:
    respx.get(url__startswith=settings.naaim_page_url).mock(
        return_value=httpx.Response(200, text=f'<a href="{_FILE_URL}">Download</a>')
    )
    respx.get(url=_FILE_URL).mock(return_value=httpx.Response(200, content=_naaim_xlsx_bytes()))

    series = await NaaimSource(settings, client).fetch("exposure")

    assert len(series) == 2
    assert series.index.is_monotonic_increasing
    assert series.iloc[-1] == pytest.approx(86.82)  # neuester Wert (2026-06-03)


@respx.mock
async def test_fetch_no_url_raises(settings: Settings, client: httpx.AsyncClient) -> None:
    # Discovery scheitert und keine Fallback-URL gesetzt (naaim_xls_url == "").
    respx.get(url__startswith=settings.naaim_page_url).mock(
        return_value=httpx.Response(200, text="<html>kein Link</html>")
    )
    with pytest.raises(DataSourceError, match="Keine NAAIM-URL"):
        await NaaimSource(settings, client).fetch("exposure")
