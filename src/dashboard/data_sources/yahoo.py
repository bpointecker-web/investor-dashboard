"""Yahoo-Finance-Datenquelle (Chart-JSON-API) - Fallback fuer stooq.

Genutzt wird die stabile ``/v8/finance/chart``-API (JSON, kein Crumb/Cookie noetig),
nicht die fragile yfinance-HTML-Schicht. Die Quelle uebersetzt stooq-Symbole in
Yahoo-Symbole und ist damit ein Drop-in-Fallback (gleiche ``ref``-Eingabe).
"""

from __future__ import annotations

from urllib.parse import quote

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

# stooq-Symbol -> Yahoo-Symbol (nur die im Manifest genutzten stooq-Symbole).
_SYMBOL_MAP: dict[str, str] = {
    "^spx": "^GSPC",
    "^stoxx": "^STOXX",
    "^dax": "^GDAXI",
    "^atx": "^ATX",
    "eem.us": "EEM",
    "^rut": "^RUT",
    "rsp.us": "RSP",
    "spy.us": "SPY",
    "hg.f": "HG=F",
    "xauusd": "GC=F",
    "^dxy": "DX-Y.NYB",
    "eurusd": "EURUSD=X",
    "eurchf": "EURCHF=X",
    "^move": "^MOVE",
}


class YahooSource:
    """Laedt taegliche Schlusskurse ueber die Yahoo-Chart-API."""

    name = "yahoo"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` ist das stooq-Symbol; wird intern auf Yahoo gemappt."""
        yahoo_symbol = _SYMBOL_MAP.get(ref)
        if yahoo_symbol is None:
            raise DataSourceError(self.name, ref, "Kein Yahoo-Symbol-Mapping vorhanden.")

        url = f"{self._settings.yahoo_base_url}/v8/finance/chart/{quote(yahoo_symbol, safe='')}"
        params = {"range": f"{self._settings.history_years}y", "interval": "1d"}
        headers = {"User-Agent": self._settings.user_agent}
        try:
            response = await get_with_retry(
                self._client,
                url,
                params=params,
                headers=headers,
                timeout=self._settings.http_timeout_seconds,
                retries=self._settings.http_retries,
            )
            payload = response.json()
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, ref, f"HTTP-Fehler: {exc}") from exc
        except ValueError as exc:
            raise DataSourceError(self.name, ref, f"Ungueltiges JSON: {exc}") from exc

        return _parse_chart(payload, source=self.name, ref=ref)


def _parse_chart(payload: object, *, source: str, ref: str) -> pd.Series:
    """Extrahiert (timestamp, close) aus der Yahoo-Chart-Antwort."""
    if not isinstance(payload, dict) or "chart" not in payload:
        raise DataSourceError(source, ref, "Antwort enthaelt kein 'chart'.")
    chart = payload["chart"]
    results = chart.get("result") if isinstance(chart, dict) else None
    if not results:
        raise DataSourceError(source, ref, "Leeres 'result' in Yahoo-Antwort.")

    result = results[0]
    timestamps = result.get("timestamp")
    try:
        closes = result["indicators"]["quote"][0]["close"]
    except (KeyError, IndexError, TypeError) as exc:
        raise DataSourceError(source, ref, f"Unerwartete Struktur: {exc}") from exc
    if not timestamps or closes is None:
        raise DataSourceError(source, ref, "Keine Kursdaten enthalten.")

    index = pd.to_datetime(timestamps, unit="s").normalize()
    series = pd.Series(closes, index=index, dtype="float64").dropna()
    series = series[~series.index.duplicated(keep="last")]
    if series.empty:
        raise DataSourceError(source, ref, "Keine gueltigen Schlusskurse.")
    return series.sort_index()
