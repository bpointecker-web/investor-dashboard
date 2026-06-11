"""CFTC-Datenquelle: Spekulanten-Netto-Positionierung (Commitments of Traders).

Nutzt die offizielle CFTC Public Reporting API (Socrata, Legacy "Futures Only").
Indikator-Wert = Non-Commercial Long - Non-Commercial Short fuer den gegebenen
Contract Market Code (z.B. 13874A = CME E-MINI S&P 500).
"""

from __future__ import annotations

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources._http import get_with_retry
from dashboard.data_sources.base import DataSourceError

_LONG_FIELD = "noncomm_positions_long_all"
_SHORT_FIELD = "noncomm_positions_short_all"
_DATE_FIELD = "report_date_as_yyyy_mm_dd"


class CftcSource:
    """Laedt woechentliche COT-Daten und berechnet das Spec-Netto."""

    name = "cftc"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` = CFTC Contract Market Code (z.B. '13874A')."""
        url = f"{self._settings.cftc_base_url}/{self._settings.cftc_dataset}.json"
        params = {
            "cftc_contract_market_code": ref,
            "$select": f"{_DATE_FIELD},{_LONG_FIELD},{_SHORT_FIELD}",
            "$order": f"{_DATE_FIELD} DESC",
            "$limit": str(self._settings.history_years * 53 + 10),
        }
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

        return _parse_cot(payload, source=self.name, ref=ref)


def _parse_cot(payload: object, *, source: str, ref: str) -> pd.Series:
    """Baut die Spec-Netto-Serie (Long - Short) aus den COT-Zeilen."""
    if not isinstance(payload, list) or not payload:
        raise DataSourceError(source, ref, "Keine COT-Daten erhalten.")

    dates: list[str] = []
    values: list[float] = []
    for row in payload:
        try:
            net = float(row[_LONG_FIELD]) - float(row[_SHORT_FIELD])
        except (KeyError, TypeError, ValueError):
            continue
        dates.append(row[_DATE_FIELD])
        values.append(net)

    if not values:
        raise DataSourceError(source, ref, "Keine gueltigen Positionsdaten.")

    series = pd.Series(values, index=pd.to_datetime(dates), dtype="float64")
    return series.sort_index()
