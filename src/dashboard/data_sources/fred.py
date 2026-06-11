"""FRED-Datenquelle (Federal Reserve Economic Data, St. Louis Fed)."""

from __future__ import annotations

from datetime import date, timedelta

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

_MISSING_VALUE = "."


class FredSource:
    """Laedt Zeitreihen ueber die FRED-JSON-API (`series/observations`)."""

    name = "fred"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """Laedt ``history_years`` Jahre Beobachtungen fuer die Series-ID ``ref``."""
        start = date.today() - timedelta(days=round(365.25 * self._settings.history_years))
        params = {
            "series_id": ref,
            "api_key": self._settings.require_fred_key(),
            "file_type": "json",
            "observation_start": start.isoformat(),
        }
        headers = {"User-Agent": self._settings.user_agent}
        url = f"{self._settings.fred_base_url}/series/observations"

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

        return _parse_observations(payload, source=self.name, ref=ref)


def _parse_observations(payload: object, *, source: str, ref: str) -> pd.Series:
    """Wandelt die FRED-JSON-Antwort in eine bereinigte ``pd.Series``."""
    if not isinstance(payload, dict) or "observations" not in payload:
        raise DataSourceError(source, ref, "Antwort enthaelt keine 'observations'.")

    observations = payload["observations"]
    dates: list[str] = []
    values: list[float] = []
    for obs in observations:
        raw = obs.get("value")
        if raw is None or raw == _MISSING_VALUE:
            continue
        try:
            values.append(float(raw))
        except (TypeError, ValueError):
            continue
        dates.append(obs["date"])

    if not values:
        raise DataSourceError(source, ref, "Keine gueltigen Beobachtungen.")

    series = pd.Series(values, index=pd.to_datetime(dates), dtype="float64")
    return series.sort_index()
