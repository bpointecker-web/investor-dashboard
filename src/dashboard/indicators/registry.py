"""Laedt und validiert den Indikator-Katalog aus dem Manifest-YAML."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import TypeAdapter

from dashboard.indicators.models import Category, Indicator

_MANIFEST_PATH = Path(__file__).parent / "manifest.yaml"
_LIST_ADAPTER = TypeAdapter(list[Indicator])


class IndicatorRegistry:
    """Liefert validierte Indikatoren aus dem Manifest (id-Lookup, Kategorien)."""

    def __init__(self, indicators: list[Indicator]) -> None:
        ids = [ind.id for ind in indicators]
        duplicates = {i for i in ids if ids.count(i) > 1}
        if duplicates:
            raise ValueError(f"Doppelte Indikator-IDs im Manifest: {sorted(duplicates)}")
        self._by_id: dict[str, Indicator] = {ind.id: ind for ind in indicators}

    @property
    def ids(self) -> list[str]:
        """Alle bekannten Indikator-IDs (Manifest-Reihenfolge)."""
        return list(self._by_id.keys())

    def all(self) -> list[Indicator]:
        """Alle Indikatoren in Manifest-Reihenfolge."""
        return list(self._by_id.values())

    def get(self, indicator_id: str) -> Indicator:
        """Liefert einen Indikator per ID oder wirft KeyError."""
        if indicator_id not in self._by_id:
            raise KeyError(f"Unbekannter Indikator: {indicator_id}")
        return self._by_id[indicator_id]

    def has(self, indicator_id: str) -> bool:
        """Pruefung gegen die Whitelist bekannter IDs (fuer URL-Validierung)."""
        return indicator_id in self._by_id

    def by_category(self) -> dict[Category, list[Indicator]]:
        """Gruppiert Indikatoren nach Kategorie (Manifest-Reihenfolge erhalten)."""
        grouped: dict[Category, list[Indicator]] = {}
        for indicator in self._by_id.values():
            grouped.setdefault(indicator.category, []).append(indicator)
        return grouped


def load_indicators(path: Path = _MANIFEST_PATH) -> list[Indicator]:
    """Parst und validiert das Manifest-YAML zu einer Indikator-Liste."""
    raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("Manifest muss eine YAML-Liste sein.")
    return _LIST_ADAPTER.validate_python(raw)


@lru_cache(maxsize=1)
def get_registry() -> IndicatorRegistry:
    """Gecachte Registry aus dem Standard-Manifest."""
    return IndicatorRegistry(load_indicators())
