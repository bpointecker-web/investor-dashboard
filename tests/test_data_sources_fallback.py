"""Tests fuer den generischen FallbackSource-Wrapper."""

from __future__ import annotations

import pandas as pd

from dashboard.data_sources.fallback import FallbackSource
from tests.conftest import FakeSource


def _series(value: float) -> pd.Series:
    return pd.Series([value], index=pd.to_datetime(["2024-01-01"]))


async def test_primary_success_skips_secondary() -> None:
    primary = FakeSource("stooq", {"^spx": _series(1.0)})
    secondary = FakeSource("yahoo", {"^spx": _series(2.0)})
    source = FallbackSource("stooq", primary, secondary)

    result = await source.fetch("^spx")

    assert result.iloc[-1] == 1.0
    assert secondary.calls == []  # Fallback nicht ausgeloest


async def test_primary_failure_uses_secondary() -> None:
    primary = FakeSource("stooq", {})  # kennt das Symbol nicht -> DataSourceError
    secondary = FakeSource("yahoo", {"^spx": _series(2.0)})
    source = FallbackSource("stooq", primary, secondary)

    result = await source.fetch("^spx")

    assert result.iloc[-1] == 2.0
    assert secondary.calls == ["^spx"]


def test_name_is_primary_for_stable_cache_keys() -> None:
    source = FallbackSource("stooq", FakeSource("stooq", {}), FakeSource("yahoo", {}))
    assert source.name == "stooq"
