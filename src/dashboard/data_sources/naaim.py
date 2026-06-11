"""NAAIM-Datenquelle: Manager Exposure Index (woechentlich, Excel).

Die Datei traegt einen datierten Namen; wir ermitteln den aktuellen Link per
Discovery von der NAAIM-Programmseite (Fallback: konfigurierte Direkt-URL).
"""

from __future__ import annotations

import io

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._discovery import discover_file_url
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

_DATE_COL = "Date"
_VALUE_COL = "Mean/Average"
_VALUE_COL_FALLBACK = 1
_LINK_PATTERN = r"https?://[^\"'<>\s]+\.xlsx"


class NaaimSource:
    """Laedt die NAAIM-Exposure-Index-Datei und extrahiert die Mittelwert-Serie."""

    name = "naaim"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def _resolve_url(self) -> str:
        discovered = await discover_file_url(
            self._client, self._settings.naaim_page_url, _LINK_PATTERN, self._settings
        )
        url = discovered or self._settings.naaim_xls_url
        if not url:
            raise DataSourceError(self.name, "exposure", "Keine NAAIM-URL ermittelbar.")
        return url

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` ist hier konventionell 'exposure' (nur eine Serie verfuegbar)."""
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

        return _parse_exposure(content, source=self.name, ref=ref)


def _parse_exposure(content: bytes, *, source: str, ref: str) -> pd.Series:
    """Extrahiert die Exposure-Serie (Mean/Average) aus dem NAAIM-Excel."""
    try:
        frame = pd.read_excel(io.BytesIO(content), sheet_name=0, header=0, engine="openpyxl")
    except (ValueError, OSError) as exc:
        raise DataSourceError(source, ref, f"Excel nicht parsebar: {exc}") from exc

    if _DATE_COL not in frame.columns:
        raise DataSourceError(source, ref, f"Spalte '{_DATE_COL}' fehlt.")
    value_col = _VALUE_COL if _VALUE_COL in frame.columns else frame.columns[_VALUE_COL_FALLBACK]

    dates = pd.to_datetime(frame[_DATE_COL], errors="coerce")
    values = pd.to_numeric(frame[value_col], errors="coerce")
    mask = dates.notna() & values.notna()
    if not mask.any():
        raise DataSourceError(source, ref, "Keine gueltigen Exposure-Werte.")

    series = pd.Series(values[mask].to_numpy(), index=pd.DatetimeIndex(dates[mask]))
    series = series[~series.index.duplicated(keep="last")]
    return series.sort_index()
