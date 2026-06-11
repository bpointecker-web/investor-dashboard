"""CoinGecko-Datenquelle (Krypto-Preise, Free-Tier ohne Key)."""

from __future__ import annotations

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError


class CoinGeckoSource:
    """Laedt taegliche USD-Preise ueber `/coins/{id}/market_chart`."""

    name = "coingecko"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    # CoinGecko Free-/Demo-Tier erlaubt max. 365 Tage Historie (366+ -> HTTP 401).
    _FREE_TIER_MAX_DAYS = 365

    async def fetch(self, ref: str) -> pd.Series:
        """Laedt die Preis-Historie fuer die Coin-ID ``ref`` (z.B. 'bitcoin')."""
        days = round(365.25 * self._settings.history_years)
        has_key = self._settings.coingecko_api_key is not None
        if not has_key:
            days = min(days, self._FREE_TIER_MAX_DAYS)
        params = {
            "vs_currency": "usd",
            "days": str(days),
            "interval": "daily",
        }
        headers = {"User-Agent": self._settings.user_agent}
        if has_key and self._settings.coingecko_api_key is not None:
            headers["x-cg-demo-api-key"] = self._settings.coingecko_api_key.get_secret_value()
        url = f"{self._settings.coingecko_base_url}/coins/{ref}/market_chart"

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

        return _parse_market_chart(payload, source=self.name, ref=ref)


def _parse_market_chart(payload: object, *, source: str, ref: str) -> pd.Series:
    """Wandelt `prices`: [[ms_timestamp, price], ...] in eine ``pd.Series``."""
    if not isinstance(payload, dict) or "prices" not in payload:
        raise DataSourceError(source, ref, "Antwort enthaelt keine 'prices'.")

    prices = payload["prices"]
    if not isinstance(prices, list) or not prices:
        raise DataSourceError(source, ref, "Leere Preis-Liste.")

    timestamps_ms = [row[0] for row in prices]
    values = [float(row[1]) for row in prices]
    index = pd.to_datetime(timestamps_ms, unit="ms").normalize()
    series = pd.Series(values, index=index, dtype="float64")
    # Tagesduplikate (CoinGecko liefert teils 2 Punkte/Tag) -> letzten behalten.
    series = series[~series.index.duplicated(keep="last")]
    return series.sort_index()
