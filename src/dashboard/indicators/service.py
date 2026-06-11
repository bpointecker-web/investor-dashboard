"""Service-Layer: orchestriert Datenquellen, Cache, Skalierung und Einordnung."""

from __future__ import annotations

import asyncio
import time

import httpx
import pandas as pd

from dashboard.config import Settings
from dashboard.data_sources.base import DataSource, DataSourceError
from dashboard.data_sources.cache import TTLCache, make_key
from dashboard.data_sources.cboe import CboeSource
from dashboard.data_sources.cftc import CftcSource
from dashboard.data_sources.cnn import CnnSource
from dashboard.data_sources.coingecko import CoinGeckoSource
from dashboard.data_sources.computed import ComputedSource
from dashboard.data_sources.fallback import FallbackSource
from dashboard.data_sources.fred import FredSource
from dashboard.data_sources.naaim import NaaimSource
from dashboard.data_sources.shiller import ShillerSource
from dashboard.data_sources.stooq import StooqSource
from dashboard.data_sources.yahoo import YahooSource
from dashboard.indicators import stats
from dashboard.indicators.models import (
    Indicator,
    IndicatorSnapshot,
    SnapshotStatus,
    SourceKind,
)
from dashboard.indicators.registry import IndicatorRegistry
from dashboard.logging_setup import get_logger

_log = get_logger("service")


class IndicatorService:
    """Laedt Indikatoren, ordnet sie ein und erzeugt Snapshots (card-level degradiert)."""

    def __init__(
        self,
        settings: Settings,
        registry: IndicatorRegistry,
        client: httpx.AsyncClient,
        cache: TTLCache | None = None,
    ) -> None:
        self._settings = settings
        self._registry = registry
        self._cache = cache or TTLCache(settings.default_cache_ttl_minutes)
        self._sources: dict[SourceKind, DataSource] = self._build_sources(settings, client)

    def _build_sources(
        self, settings: Settings, client: httpx.AsyncClient
    ) -> dict[SourceKind, DataSource]:
        """Source-Factory. Computed nutzt andere Quellen ueber den Service-Resolver."""
        return {
            SourceKind.FRED: FredSource(settings, client),
            # stooq blockt teils ganze IPs -> Yahoo-Chart-API als Fallback.
            SourceKind.STOOQ: FallbackSource(
                SourceKind.STOOQ.value,
                StooqSource(settings, client),
                YahooSource(settings, client),
            ),
            SourceKind.COINGECKO: CoinGeckoSource(settings, client),
            SourceKind.SHILLER: ShillerSource(settings, client),
            SourceKind.NAAIM: NaaimSource(settings, client),
            SourceKind.CFTC: CftcSource(settings, client),
            SourceKind.CBOE: CboeSource(settings, client),
            SourceKind.CNN: CnnSource(settings, client),
            SourceKind.COMPUTED: ComputedSource(self._resolve),
        }

    async def _resolve(self, source: str, ref: str) -> pd.Series:
        """Resolver fuer ComputedSource: laedt Sub-Komponenten (mit Default-TTL)."""
        return await self._fetch_cached(
            SourceKind(source), ref, self._settings.default_cache_ttl_minutes
        )

    async def _fetch_cached(self, kind: SourceKind, ref: str, ttl_minutes: int) -> pd.Series:
        """Holt eine native Zeitreihe aus Cache oder Quelle (mit Logging)."""
        key = make_key(kind.value, ref)
        cached = self._cache.get(key, ttl_minutes)
        if cached is not None:
            _log.debug("fetch", source=kind.value, ref=ref, cache_hit=True)
            return cached

        source = self._sources.get(kind)
        if source is None:
            raise DataSourceError(kind.value, ref, "Quelle nicht konfiguriert.")

        start = time.perf_counter()
        series = await source.fetch(ref)
        duration_ms = round((time.perf_counter() - start) * 1000, 1)
        self._cache.set(key, series)
        _log.info(
            "fetch",
            source=kind.value,
            ref=ref,
            cache_hit=False,
            duration_ms=duration_ms,
            n_points=len(series),
        )
        return series

    async def get_snapshot(self, indicator: Indicator) -> IndicatorSnapshot:
        """Erzeugt einen vollstaendigen Snapshot; Fehler werden zur Card-Degradation."""
        ttl = indicator.cache_ttl_minutes or self._settings.default_cache_ttl_minutes
        try:
            raw = await self._fetch_cached(indicator.source, indicator.source_ref, ttl)
            scaled = (raw * indicator.display_multiplier).dropna().sort_index()
            if scaled.empty:
                raise DataSourceError(indicator.source.value, indicator.id, "Serie leer.")

            snapshot_stats = stats.build_snapshot_stats(
                scaled,
                direction=indicator.direction,
                thresholds=indicator.thresholds,
                history_years=self._settings.history_years,
            )
            return IndicatorSnapshot(
                indicator=indicator,
                status=SnapshotStatus.OK,
                stats=snapshot_stats,
                series_dates=[d.strftime("%Y-%m-%d") for d in scaled.index],
                series_values=[float(v) for v in scaled.to_numpy()],
            )
        except (DataSourceError, ValueError, KeyError) as exc:
            _log.warning("snapshot_error", indicator_id=indicator.id, error=str(exc))
            return IndicatorSnapshot(
                indicator=indicator,
                status=SnapshotStatus.ERROR,
                error=str(exc),
            )

    async def get_all_snapshots(self) -> list[IndicatorSnapshot]:
        """Laedt alle Indikatoren parallel (Reihenfolge wie im Manifest)."""
        tasks = [self.get_snapshot(ind) for ind in self._registry.all()]
        return await asyncio.gather(*tasks)

    async def get_snapshot_by_id(self, indicator_id: str) -> IndicatorSnapshot:
        """Snapshot fuer eine einzelne, per Whitelist gepruefte ID."""
        return await self.get_snapshot(self._registry.get(indicator_id))
