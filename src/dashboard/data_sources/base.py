"""Abstraktion fuer Datenquellen (Dependency Inversion).

Jede Quelle liefert eine ``pd.Series`` mit aufsteigend sortiertem ``DatetimeIndex``
in *nativen* Einheiten (Skalierung via ``display_multiplier`` passiert spaeter im
Service). Implementierungen sind ueber das ``DataSource``-Protocol austauschbar.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

import pandas as pd


class DataSourceError(RuntimeError):
    """Fehler beim Abruf/Parsen einer Datenquelle (mit Quellenkontext)."""

    def __init__(self, source: str, ref: str, message: str) -> None:
        self.source = source
        self.ref = ref
        super().__init__(f"[{source}:{ref}] {message}")


@runtime_checkable
class DataSource(Protocol):
    """Protokoll fuer eine abrufbare Zeitreihen-Quelle."""

    name: str

    async def fetch(self, ref: str) -> pd.Series:
        """Laedt die Zeitreihe fuer ``ref`` (series_id | symbol | coin-id).

        Returns:
            ``pd.Series`` (float) mit ``DatetimeIndex``, aufsteigend, ohne NaN.

        Raises:
            DataSourceError: bei Netzwerk-/Parsing-/Leerdaten-Problemen.
        """
        ...
