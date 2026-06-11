"""Tests fuer den TTL-Cache."""

from __future__ import annotations

import pandas as pd

from dashboard.data_sources.cache import TTLCache, make_key


def _series() -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=3, freq="D")
    return pd.Series([1.0, 2.0, 3.0], index=idx)


def test_make_key() -> None:
    assert make_key("fred", "DGS10") == "fred:DGS10"


def test_set_then_get_returns_series() -> None:
    cache = TTLCache(default_ttl_minutes=60)
    cache.set("fred:DGS10", _series())
    result = cache.get("fred:DGS10")
    assert result is not None
    assert list(result) == [1.0, 2.0, 3.0]


def test_miss_returns_none() -> None:
    assert TTLCache().get("nope:x") is None


def test_expired_entry_is_evicted(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cache = TTLCache(default_ttl_minutes=60)
    times = iter([0.0, 4000.0])  # set@0s, get@4000s (>60min) -> abgelaufen
    monkeypatch.setattr("dashboard.data_sources.cache.time.monotonic", lambda: next(times))
    cache.set("fred:X", _series())
    assert cache.get("fred:X") is None
    assert len(cache) == 0


def test_ttl_override_per_lookup(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    cache = TTLCache(default_ttl_minutes=60)
    times = iter([0.0, 120.0])  # 2 Minuten vergangen
    monkeypatch.setattr("dashboard.data_sources.cache.time.monotonic", lambda: next(times))
    cache.set("fred:X", _series())
    # TTL 1 Minute -> abgelaufen
    assert cache.get("fred:X", ttl_minutes=1) is None


def test_clear() -> None:
    cache = TTLCache()
    cache.set("a:b", _series())
    cache.clear()
    assert len(cache) == 0
