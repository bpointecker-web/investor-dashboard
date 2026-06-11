"""CBOE Total Put/Call Ratio.

CBOE hat den freien programmatischen Zugang zu den Put/Call-Statistiken eingestellt
(alle CDN-Endpoints liefern 403). Die CBOE-Total-Put/Call-Ratio wird daher ueber den
oeffentlich zugaenglichen CNN-Datensatz bezogen (dieselbe CBOE-Quelle, von CNN
aufbereitet). Bei Ausfall degradiert nur diese Karte.
"""

from __future__ import annotations

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources.cnn import fetch_cnn_series


class CboeSource:
    """Liefert die CBOE Total Put/Call Ratio (via CNN-Datensatz)."""

    name = "cboe"

    def __init__(self, settings: Settings, client: httpx.AsyncClient) -> None:
        self._settings = settings
        self._client = client

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` wird ignoriert; geliefert wird stets die Total-Put/Call-Ratio."""
        return await fetch_cnn_series(self._client, self._settings, "put_call", source=self.name)
