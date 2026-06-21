"""EZB-Datenquelle (Statistical Data Warehouse, Euro-Zinskurve).

Liefert taegliche Spot-Rates der Euro-Raum-Zinskurve (AAA-Staatsanleihen,
Svensson-Modell) - der risikofreie Euro-Referenzzins, an dem sich Banken bei
der Ableitung von Fixzinsen orientieren. ``ref`` ist der volle SDW-Series-Key,
z.B. ``B.U2.EUR.4F.G_N_A.SV_C_YM.SR_10Y`` (Dataflow ``YC``).
"""

from __future__ import annotations

import io
from datetime import date, timedelta

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

_DATAFLOW = "YC"
_DATE_COL = "TIME_PERIOD"
_VALUE_COL = "OBS_VALUE"


class EcbSource:
    """Laedt Euro-Zinskurven-Zeitreihen ueber die EZB-SDW-REST-API (CSV)."""

    name = "ecb"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """Laedt ``history_years`` Jahre Spot-Rates fuer den Series-Key ``ref``."""
        start = date.today() - timedelta(days=round(365.25 * self._settings.history_years))
        url = f"{self._settings.ecb_base_url}/data/{_DATAFLOW}/{ref}"
        params = {"format": "csvdata", "startPeriod": start.isoformat()}
        headers = {"User-Agent": self._settings.user_agent, "Accept": "text/csv"}

        try:
            response = await get_with_retry(
                self._client,
                url,
                params=params,
                headers=headers,
                timeout=self._settings.http_timeout_seconds,
                retries=self._settings.http_retries,
            )
            content = response.text
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, ref, f"HTTP-Fehler: {exc}") from exc

        return _parse_csv(content, source=self.name, ref=ref)


def _parse_csv(content: str, *, source: str, ref: str) -> pd.Series:
    """Extrahiert (TIME_PERIOD, OBS_VALUE) aus der EZB-CSV-Antwort."""
    try:
        frame = pd.read_csv(io.StringIO(content))
    except (ValueError, pd.errors.ParserError) as exc:
        raise DataSourceError(source, ref, f"CSV nicht parsebar: {exc}") from exc

    if _DATE_COL not in frame.columns or _VALUE_COL not in frame.columns:
        raise DataSourceError(source, ref, f"Spalten '{_DATE_COL}'/'{_VALUE_COL}' fehlen.")

    values = pd.to_numeric(frame[_VALUE_COL], errors="coerce")
    dates = pd.to_datetime(frame[_DATE_COL], errors="coerce")
    series = pd.Series(values.to_numpy(), index=dates).dropna()
    if series.empty:
        raise DataSourceError(source, ref, "Keine gueltigen Beobachtungen.")

    return series.sort_index()
