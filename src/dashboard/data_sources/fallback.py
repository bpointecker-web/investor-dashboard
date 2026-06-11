"""Generischer Fallback-Wrapper: primaere Quelle, bei Fehler sekundaere Quelle.

Haelt die DataSource-Schnittstelle ein und ist daher transparent im Service
einsetzbar (z.B. stooq -> Yahoo). Der ``name`` entspricht der primaeren Quelle,
damit Cache-Keys stabil bleiben.
"""

from __future__ import annotations

import pandas as pd

from dashboard.data_sources.base import DataSource, DataSourceError
from dashboard.logging_setup import get_logger

_log = get_logger("fallback")


class FallbackSource:
    """Versucht ``primary``; bei ``DataSourceError`` wird ``secondary`` genutzt."""

    def __init__(self, name: str, primary: DataSource, secondary: DataSource) -> None:
        self.name = name
        self._primary = primary
        self._secondary = secondary

    async def fetch(self, ref: str) -> pd.Series:
        try:
            return await self._primary.fetch(ref)
        except DataSourceError as primary_error:
            _log.warning(
                "fallback_triggered",
                primary=self._primary.name,
                secondary=self._secondary.name,
                ref=ref,
                error=str(primary_error),
            )
            return await self._secondary.fetch(ref)
