"""Tests fuer die reinen Statistik-Funktionen (keine I/O)."""

from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from dashboard.indicators import stats
from dashboard.indicators.models import Band, Direction, Thresholds


def _series(values: list[float], *, end: str = "2024-12-31", freq: str = "D") -> pd.Series:
    """Hilfsfunktion: Serie mit taeglichem DatetimeIndex, aufsteigend sortiert."""
    idx = pd.date_range(end=end, periods=len(values), freq=freq)
    return pd.Series(values, index=idx, dtype="float64")


class TestPercentileOf:
    def test_value_above_all_is_100(self) -> None:
        series = _series([1, 2, 3, 4, 5])
        assert stats.percentile_of(series, 10.0) == pytest.approx(100.0)

    def test_value_below_all_is_0(self) -> None:
        series = _series([10, 20, 30])
        assert stats.percentile_of(series, 1.0) == pytest.approx(0.0)

    def test_median_value_is_50(self) -> None:
        series = _series([1, 2, 3, 4, 5])
        # 'mean'-Rang: 2 kleiner, 1 gleich -> (2 + 0.5)/5 * 100 = 50
        assert stats.percentile_of(series, 3.0) == pytest.approx(50.0)

    def test_empty_series_returns_nan(self) -> None:
        assert np.isnan(stats.percentile_of(pd.Series([], dtype="float64"), 1.0))


class TestZScore:
    def test_basic_z_score(self) -> None:
        series = _series([2, 4, 4, 4, 5, 5, 7, 9])  # mean 5, std(ddof=1)=2.138...
        z = stats.z_score(series, 9.0)
        assert z is not None
        assert z == pytest.approx((9 - 5) / series.std(ddof=1))

    def test_zero_variance_returns_none(self) -> None:
        series = _series([3, 3, 3, 3])
        assert stats.z_score(series, 3.0) is None

    def test_single_value_returns_none(self) -> None:
        assert stats.z_score(_series([5]), 5.0) is None


class TestSliceLastYears:
    def test_keeps_only_window(self) -> None:
        series = _series(list(range(4000)))  # ~11 Jahre taeglich
        sliced = stats.slice_last_years(series, 5)
        span_days = (sliced.index[-1] - sliced.index[0]).days
        assert span_days <= 5 * 366 + 1
        assert sliced.index[-1] == series.index[-1]


class TestComputeChanges:
    def test_one_day_change(self) -> None:
        series = _series([100, 101, 103])
        changes = stats.compute_changes(series)
        assert changes["1d"].absolute == pytest.approx(2.0)
        assert changes["1d"].percent == pytest.approx(2.0 / 101 * 100)

    def test_missing_history_yields_none(self) -> None:
        series = _series([100, 102], freq="D")
        changes = stats.compute_changes(series)
        # 1-Jahres-Vergleich nicht moeglich -> None statt Crash
        assert changes["1y"].absolute is None

    def test_zero_base_percent_is_none(self) -> None:
        series = _series([0.0, 5.0])
        changes = stats.compute_changes(series)
        assert changes["1d"].absolute == pytest.approx(5.0)
        assert changes["1d"].percent is None


class TestClassifyBandThresholds:
    def test_higher_is_stress_stress(self) -> None:
        band = stats.classify_band(
            percentile=50.0,
            z=0.0,
            value=800.0,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=Thresholds(elevated=500, stress=700),
        )
        assert band is Band.STRESS

    def test_higher_is_stress_elevated(self) -> None:
        band = stats.classify_band(
            percentile=50.0,
            z=0.0,
            value=600.0,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=Thresholds(elevated=500, stress=700),
        )
        assert band is Band.ELEVATED

    def test_higher_is_stress_normal(self) -> None:
        band = stats.classify_band(
            percentile=50.0,
            z=0.0,
            value=350.0,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=Thresholds(elevated=500, stress=700),
        )
        assert band is Band.NORMAL

    def test_thresholds_take_priority_over_percentile(self) -> None:
        # Percentil waere "stress" (95), aber harte Schwelle sagt normal.
        band = stats.classify_band(
            percentile=95.0,
            z=3.0,
            value=100.0,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=Thresholds(elevated=500, stress=700),
        )
        assert band is Band.NORMAL


class TestClassifyBandPercentile:
    def test_higher_is_stress_high_percentile(self) -> None:
        band = stats.classify_band(
            percentile=95.0,
            z=2.0,
            value=1.0,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=None,
        )
        assert band is Band.STRESS

    def test_higher_is_stress_low_percentile(self) -> None:
        band = stats.classify_band(
            percentile=10.0,
            z=-1.0,
            value=1.0,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=None,
        )
        assert band is Band.LOW

    def test_supportive_low_value_is_stress(self) -> None:
        # higher_is_supportive: niedriger Wert (niedriges Percentil) = Stress-Ende
        band = stats.classify_band(
            percentile=5.0,
            z=-2.0,
            value=1.0,
            direction=Direction.HIGHER_IS_SUPPORTIVE,
            thresholds=None,
        )
        assert band is Band.STRESS

    def test_lower_is_stress_inverted(self) -> None:
        band = stats.classify_band(
            percentile=5.0,
            z=-2.0,
            value=1.0,
            direction=Direction.LOWER_IS_STRESS,
            thresholds=None,
        )
        assert band is Band.STRESS

    def test_neutral_uses_abs_z(self) -> None:
        assert (
            stats.classify_band(
                percentile=99.0,
                z=2.6,
                value=1.0,
                direction=Direction.NEUTRAL,
                thresholds=None,
            )
            is Band.STRESS
        )
        assert (
            stats.classify_band(
                percentile=99.0,
                z=0.5,
                value=1.0,
                direction=Direction.NEUTRAL,
                thresholds=None,
            )
            is Band.NORMAL
        )


class TestBuildSnapshotStats:
    def test_full_snapshot(self) -> None:
        rng = np.random.default_rng(42)
        values = rng.normal(400, 50, size=2600).tolist()  # ~10 Jahre taeglich
        series = _series(values)
        result = stats.build_snapshot_stats(
            series,
            direction=Direction.HIGHER_IS_STRESS,
            thresholds=None,
        )
        assert result.current == pytest.approx(series.iloc[-1])
        assert result.as_of == "2024-12-31"
        assert 0.0 <= result.percentile_10y <= 100.0
        assert result.min_10y <= result.median_10y <= result.max_10y
        assert "1d" in result.changes and "1y" in result.changes

    def test_raises_on_empty(self) -> None:
        with pytest.raises(ValueError, match="leer"):
            stats.build_snapshot_stats(
                pd.Series([], dtype="float64"),
                direction=Direction.NEUTRAL,
                thresholds=None,
            )
