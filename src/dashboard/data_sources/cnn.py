"""CNN-Datenquelle: Fear & Greed Index (inoffizieller JSON-Endpoint).

Der Endpoint liefert mehrere Teil-Serien. Wir nutzen zwei davon:
  - ``fear_greed`` -> Gesamtindex (0-100)
  - ``put_call``   -> CBOE Total Put/Call Ratio (von CBOE abgeleitet)

Wartungsrisiko: CNN kann den Endpoint aendern; bei Ausfall faellt nur die
betroffene Karte aus (Card-Level-Degradation).
"""

from __future__ import annotations

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

# ref -> JSON-Schluessel im graphdata-Payload.
_SERIES_KEYS: dict[str, str] = {
    "fear_greed": "fear_and_greed_historical",
    "put_call": "put_call_options",
}


async def fetch_cnn_series(
    client: httpx.AsyncClient, settings: Settings, ref: str, *, source: str = "cnn"
) -> pd.Series:
    """Laedt eine CNN-Teilserie. Von CnnSource und CboeSource gemeinsam genutzt."""
    if ref not in _SERIES_KEYS:
        raise DataSourceError(source, ref, f"Unbekannte CNN-Serie: {ref}")

    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "application/json, text/plain, */*",
        "Referer": settings.cnn_referer,
        "Origin": settings.cnn_referer.rstrip("/"),
    }
    try:
        response = await get_with_retry(
            client,
            settings.cnn_fear_greed_url,
            headers=headers,
            timeout=settings.http_timeout_seconds,
            retries=settings.http_retries,
        )
        payload = response.json()
    except httpx.HTTPError as exc:
        raise DataSourceError(source, ref, f"HTTP-Fehler: {exc}") from exc
    except ValueError as exc:
        raise DataSourceError(source, ref, f"Ungueltiges JSON: {exc}") from exc

    return _parse_graphdata(payload, key=_SERIES_KEYS[ref], source=source, ref=ref)


def _parse_graphdata(payload: object, *, key: str, source: str, ref: str) -> pd.Series:
    """Extrahiert die ``data``-Punkte (x=ms-Timestamp, y=Wert) einer Teilserie."""
    if not isinstance(payload, dict) or key not in payload:
        raise DataSourceError(source, ref, f"Antwort enthaelt '{key}' nicht.")
    block = payload[key]
    points = block.get("data") if isinstance(block, dict) else None
    if not isinstance(points, list) or not points:
        raise DataSourceError(source, ref, "Leere Datenpunkte.")

    timestamps_ms = [p["x"] for p in points]
    values = [float(p["y"]) for p in points]
    index = pd.to_datetime(timestamps_ms, unit="ms").normalize()
    series = pd.Series(values, index=index, dtype="float64")
    series = series[~series.index.duplicated(keep="last")]
    return series.sort_index()


class CnnSource:
    """CNN Fear & Greed Index (Teilserien via ``ref``)."""

    name = "cnn"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` in {'fear_greed', 'put_call'}."""
        return await fetch_cnn_series(self._client, self._settings, ref, source=self.name)
