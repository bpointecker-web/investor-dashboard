"""Thread-sicherer In-Memory-TTL-Cache fuer abgerufene Zeitreihen.

Schluessel: ``f"{source}:{ref}"``. Wert: ``(monotonic_timestamp, pd.Series)``.
Per-Source-TTL kann pro Lookup ueberschrieben werden (Manifest ``cache_ttl_minutes``).
"""

from __future__ import annotations

import threading
import time

import pandas as pd

from dashboard.logging_setup import get_logger

_log = get_logger("cache")


def make_key(source: str, ref: str) -> str:
    """Baut den Cache-Schluessel aus Quelle und Referenz."""
    return f"{source}:{ref}"


class TTLCache:
    """Einfacher TTL-Cache mit ``threading.Lock`` fuer Nebenlaeufigkeit."""

    def __init__(self, default_ttl_minutes: int = 60) -> None:
        self._store: dict[str, tuple[float, pd.Series]] = {}
        self._lock = threading.Lock()
        self._default_ttl_minutes = default_ttl_minutes

    def get(self, key: str, ttl_minutes: int | None = None) -> pd.Series | None:
        """Liefert die gecachte Serie oder None (bei Miss/Ablauf)."""
        ttl_seconds = (ttl_minutes or self._default_ttl_minutes) * 60
        now = time.monotonic()
        with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            stored_at, series = entry
            age = now - stored_at
            if age > ttl_seconds:
                del self._store[key]
                _log.debug("cache_expired", key=key, age_s=round(age, 1))
                return None
        _log.debug("cache_hit", key=key, age_s=round(age, 1))
        return series

    def set(self, key: str, series: pd.Series) -> None:
        """Legt eine Serie unter ``key`` ab (mit aktuellem Zeitstempel)."""
        with self._lock:
            self._store[key] = (time.monotonic(), series)

    def clear(self) -> None:
        """Leert den gesamten Cache (v.a. fuer Tests/Force-Refresh)."""
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)
