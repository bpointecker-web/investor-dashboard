"""stooq.com-Datenquelle (CSV-Download fuer FX, Indizes, Commodities)."""

from __future__ import annotations

import io
from datetime import date, timedelta

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

_CLOSE_COLUMN = "Close"
_DATE_COLUMN = "Date"


class StooqSource:
    """Laedt taegliche Schlusskurse als CSV (`/q/d/l/?s=SYMBOL&i=d`)."""

    name = "stooq"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """Laedt ``history_years`` Jahre Schlusskurse fuer das Symbol ``ref``."""
        today = date.today()
        start = today - timedelta(days=round(365.25 * self._settings.history_years))
        params = {
            "s": ref,
            "i": "d",
            "d1": start.strftime("%Y%m%d"),
            "d2": today.strftime("%Y%m%d"),
        }
        headers = {"User-Agent": self._settings.user_agent}

        try:
            response = await get_with_retry(
                self._client,
                self._settings.stooq_base_url,
                params=params,
                headers=headers,
                timeout=self._settings.http_timeout_seconds,
                retries=self._settings.http_retries,
            )
        except httpx.HTTPError as exc:
            raise DataSourceError(self.name, ref, f"HTTP-Fehler: {exc}") from exc

        return _parse_csv(response.text, source=self.name, ref=ref)


def _parse_csv(text: str, *, source: str, ref: str) -> pd.Series:
    """Parst stooq-CSV (Date,Open,High,Low,Close,Volume) zur Close-Serie."""
    stripped = text.strip()
    if not stripped or stripped.lower().startswith("no data"):
        raise DataSourceError(source, ref, "stooq lieferte keine Daten.")

    try:
        frame = pd.read_csv(io.StringIO(text))
    except (pd.errors.ParserError, ValueError) as exc:
        raise DataSourceError(source, ref, f"CSV nicht parsebar: {exc}") from exc

    if _CLOSE_COLUMN not in frame.columns or _DATE_COLUMN not in frame.columns:
        raise DataSourceError(source, ref, f"Spalten fehlen: {list(frame.columns)}")

    frame = frame[[_DATE_COLUMN, _CLOSE_COLUMN]].dropna()
    close = pd.to_numeric(frame[_CLOSE_COLUMN], errors="coerce")
    series = pd.Series(
        close.to_numpy(),
        index=pd.to_datetime(frame[_DATE_COLUMN]),
        dtype="float64",
    ).dropna()

    if series.empty:
        raise DataSourceError(source, ref, "Keine gueltigen Schlusskurse.")
    return series.sort_index()
