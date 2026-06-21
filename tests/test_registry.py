"""Tests fuer das Manifest-Laden und die Registry."""

from __future__ import annotations

import pytest

from dashboard.indicators.models import Category, Direction, SourceKind
from dashboard.indicators.registry import (
    IndicatorRegistry,
    get_registry,
    load_indicators,
)


def test_manifest_loads_and_validates() -> None:
    indicators = load_indicators()
    assert len(indicators) >= 30  # Slice umfasst ~33 Indikatoren


def test_all_ids_unique() -> None:
    registry = get_registry()
    assert len(registry.ids) == len(set(registry.ids))


def test_get_known_indicator() -> None:
    registry = get_registry()
    vix = registry.get("vix")
    assert vix.source is SourceKind.FRED
    assert vix.direction is Direction.HIGHER_IS_STRESS
    assert vix.thresholds is not None
    assert vix.thresholds.stress == 30


def test_get_unknown_raises() -> None:
    with pytest.raises(KeyError, match="Unbekannter"):
        get_registry().get("does_not_exist")


def test_has_whitelist() -> None:
    registry = get_registry()
    assert registry.has("sp500")
    assert not registry.has("'; DROP TABLE")


def test_by_category_groups() -> None:
    grouped = get_registry().by_category()
    assert Category.CREDIT in grouped
    assert Category.LIQUIDITY in grouped
    assert {ind.id for ind in grouped[Category.CREDIT]} == {
        "us_hy_spread",
        "us_ig_spread",
        "eu_hy_spread",
        "btp_bund_spread",
    }


def test_computed_net_liquidity_formula_present() -> None:
    net_liq = get_registry().get("net_liquidity")
    assert net_liq.source is SourceKind.COMPUTED
    assert net_liq.formula is not None
    # Unit-Korrektur fuer RRP (Mrd -> Mio) muss in der Formel stehen.
    assert "RRPONTSYD * 1000" in net_liq.formula


def test_duplicate_ids_raise() -> None:
    indicators = load_indicators()
    with pytest.raises(ValueError, match="Doppelte"):
        IndicatorRegistry([indicators[0], indicators[0]])
