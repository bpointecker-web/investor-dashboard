"""Shiller-Datenquelle: CAPE-Ratio aus Robert Shillers Excel (`ie_data.xls`).

Die Datei liegt unter einer versionierten URL; wir ermitteln sie per Link-Discovery
von shillerdata.com (Fallback: konfigurierte Direkt-URL).
"""

from __future__ import annotations

import io

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._discovery import discover_file_url
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

_DATA_SHEET = "Data"
_DEFAULT_CAPE_COL = 12
_MIN_YEAR = 1871
_MAX_MONTH = 12
_LINK_PATTERN = r"(?:https?:)?//[^\"'<>\s]+ie_data\.xls(?:\?[^\"'<>\s]*)?"


class ShillerSource:
    """Laedt das Shiller-Excel und extrahiert die CAPE-Zeitreihe (monatlich)."""

    name = "shiller"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def _resolve_url(self) -> str:
        discovered = await discover_file_url(
            self._client, self._settings.shiller_page_url, _LINK_PATTERN, self._settings
        )
        url = discovered or self._settings.shiller_xls_url
        if not url:
            raise DataSourceError(self.name, "cape", "Keine Shiller-URL ermittelbar.")
        return url

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` ist hier konventionell 'cape' (nur eine Serie verfuegbar)."""
        url = await self._resolve_url()
        headers = {"User-Agent": self._settings.user_agent}
        try:
            response = await get_with_retry(
                self._client,
                url,
                headers=headers,
                timeout=self._settings.http_timeout_seconds,
                retries=self._settings.http_retries,
            )
            content = response.content
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, ref, f"HTTP-Fehler: {exc}") from exc

        return _parse_cape(content, source=self.name, ref=ref)


def _find_cape_column(frame: pd.DataFrame) -> int:
    """Sucht die CAPE-Spalte ueber den Header-Text; faellt auf Spalte 12 zurueck."""
    head = frame.head(10)
    for col in frame.columns:
        for cell in head[col]:
            if isinstance(cell, str) and cell.strip().upper() == "CAPE":
                return int(col)
    return _DEFAULT_CAPE_COL


def _shiller_date(value: float) -> pd.Timestamp:
    """Wandelt das Shiller-Datumsformat ``YYYY.MM`` in einen Monatsanfang."""
    year = int(value)
    month = min(max(round((value - year) * 100), 1), _MAX_MONTH)
    return pd.Timestamp(year=year, month=month, day=1)


def _parse_cape(content: bytes, *, source: str, ref: str) -> pd.Series:
    """Extrahiert die CAPE-Serie aus dem Shiller-Excel."""
    try:
        frame = pd.read_excel(
            io.BytesIO(content), sheet_name=_DATA_SHEET, header=None, engine="xlrd"
        )
    except (ValueError, OSError) as exc:
        raise DataSourceError(source, ref, f"Excel nicht parsebar: {exc}") from exc

    cape_col = _find_cape_column(frame)
    dates_raw = pd.to_numeric(frame[0], errors="coerce")
    cape = pd.to_numeric(frame[cape_col], errors="coerce")
    mask = dates_raw.notna() & (dates_raw >= _MIN_YEAR) & cape.notna()
    if not mask.any():
        raise DataSourceError(source, ref, "Keine gueltigen CAPE-Werte gefunden.")

    index = pd.DatetimeIndex([_shiller_date(v) for v in dates_raw[mask]])
    series = pd.Series(cape[mask].to_numpy(), index=index, dtype="float64")
    series = series[~series.index.duplicated(keep="last")]
    return series.sort_index()
