"""Tests fuer die Shiller-Datenquelle (CAPE-Parsing + Datums-Logik)."""

from __future__ import annotations

import httpx
import pandas as pd
import pytest
import respx

from dashboard.config import Settings
from dashboard.data_sources import shiller
from dashboard.data_sources.shiller import ShillerSource, _find_cape_column, _shiller_date


def test_shiller_date_parsing() -> None:
    assert _shiller_date(1871.01) == pd.Timestamp("1871-01-01")
    assert _shiller_date(2024.1) == pd.Timestamp("2024-10-01")  # .10 -> Oktober
    assert _shiller_date(2024.12) == pd.Timestamp("2024-12-01")


def test_find_cape_column_by_header() -> None:
    frame = pd.DataFrame([[None, None, "CAPE"], [1871.01, 1.0, 30.0]])
    assert _find_cape_column(frame) == 2


def _synthetic_shiller_frame() -> pd.DataFrame:
    header = [None] * 13
    header[12] = "CAPE"
    return pd.DataFrame(
        [
            header,
            [2024.01, *([None] * 11), 30.0],
            [2024.02, *([None] * 11), 31.5],
        ]
    )


@respx.mock
async def test_fetch_parses_cape(
    settings: Settings,
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Discovery-Seite liefert Link; Download liefert (egal welche) Bytes.
    respx.get(url__startswith=settings.shiller_page_url).mock(
        return_value=httpx.Response(
            200, text='<a href="//x.test/downloads/ie_data.xls?ver=1">x</a>'
        )
    )
    respx.get(url__startswith="https://x.test").mock(
        return_value=httpx.Response(200, content=b"fake-xls-bytes")
    )
    # pd.read_excel umgehen (echtes .xls laesst sich nicht leicht erzeugen).
    monkeypatch.setattr(shiller.pd, "read_excel", lambda *a, **k: _synthetic_shiller_frame())

    series = await ShillerSource(settings, client).fetch("cape")

    assert len(series) == 2
    assert series.index[-1] == pd.Timestamp("2024-02-01")
    assert series.iloc[-1] == pytest.approx(31.5)


@respx.mock
async def test_fetch_uses_fallback_url_when_discovery_fails(
    settings: Settings,
    client: httpx.AsyncClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Discovery-Seite ohne passenden Link -> Fallback auf konfigurierte Direkt-URL.
    respx.get(url__startswith=settings.shiller_page_url).mock(
        return_value=httpx.Response(200, text="<html>kein Link</html>")
    )
    respx.get(url__startswith="https://img1.wsimg.com").mock(
        return_value=httpx.Response(200, content=b"fake")
    )
    monkeypatch.setattr(shiller.pd, "read_excel", lambda *a, **k: _synthetic_shiller_frame())

    series = await ShillerSource(settings, client).fetch("cape")
    assert series.iloc[-1] == pytest.approx(31.5)
