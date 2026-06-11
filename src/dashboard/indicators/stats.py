"""Reine Statistik-Funktionen zur Einordnung von Indikator-Zeitreihen.

Bewusst frei von I/O und Seiteneffekten -> vollstaendig unit-testbar. Alle
Eingabe-Serien werden in Anzeige-Einheiten erwartet (display_multiplier bereits
angewendet), mit aufsteigend sortiertem ``DatetimeIndex`` und ohne NaN.
"""

from __future__ import annotations

import math

import pandas as pd

from dashboard.indicators.models import (
    Band,
    Change,
    Direction,
    SnapshotStats,
    Thresholds,
)

# Zeitfenster-Konstanten (Tage), bewusst grosszuegig fuer asof-Lookups.
_CHANGE_OFFSETS: dict[str, pd.Timedelta] = {
    "1w": pd.Timedelta(days=7),
    "1m": pd.Timedelta(days=30),
    "1y": pd.Timedelta(days=365),
}

# Mindestanzahl Beobachtungen fuer Paar-Vergleiche / Z-Score.
_MIN_PAIR = 2

# Percentil-Buckets (Konzept §6) - bezogen auf das Stress-Ende oben.
_PCT_STRESS = 90.0
_PCT_ELEVATED = 75.0
_PCT_LOW = 25.0

# |Z-Score|-Schwellen fuer neutrale Indikatoren.
_Z_STRESS = 2.5
_Z_ELEVATED = 1.5


def percentile_of(series: pd.Series, value: float) -> float:
    """Rangposition (0-100) eines Werts innerhalb der Serie ('mean'-Methode).

    Ergebnis = (Anzahl kleiner + 0.5 * Anzahl gleich) / n * 100. Leere Serie -> NaN.
    """
    n = len(series)
    if n == 0:
        return math.nan
    arr = series.to_numpy()
    less = float((arr < value).sum())
    equal = float((arr == value).sum())
    return (less + 0.5 * equal) / n * 100.0


def z_score(series: pd.Series, value: float) -> float | None:
    """Z-Score von ``value`` relativ zur Serie. None bei <2 Werten oder Std=0."""
    if len(series) < _MIN_PAIR:
        return None
    std = float(series.std(ddof=1))
    if std == 0.0 or math.isnan(std):
        return None
    return (value - float(series.mean())) / std


def slice_last_years(series: pd.Series, years: int) -> pd.Series:
    """Schneidet die Serie auf die letzten ``years`` Jahre ab dem letzten Datum."""
    if series.empty:
        return series
    cutoff = series.index[-1] - pd.DateOffset(years=years)
    sliced: pd.Series = series.loc[series.index >= cutoff]
    return sliced


def _value_asof(series: pd.Series, target: pd.Timestamp) -> float | None:
    """Letzter verfuegbarer Wert am oder vor ``target``; None falls keiner existiert."""
    if series.empty or target < series.index[0]:
        return None
    val = series.asof(target)
    if val is None or pd.isna(val):
        return None
    return float(val)  # type: ignore[arg-type]


def _change(current: float, past: float | None) -> Change:
    """Baut ein Change-Objekt mit Null-/NaN-Schutz fuer den Prozentwert."""
    if past is None:
        return Change(absolute=None, percent=None)
    absolute = current - past
    percent = None if past == 0 else (current / past - 1.0) * 100.0
    return Change(absolute=absolute, percent=percent)


def compute_changes(series: pd.Series) -> dict[str, Change]:
    """Berechnet 1d/1w/1m/1y-Aenderungen (absolut + relativ)."""
    if series.empty:
        return {k: Change() for k in ("1d", "1w", "1m", "1y")}

    current = float(series.iloc[-1])
    last_date = series.index[-1]

    # 1d: vorheriger verfuegbarer Wert (nicht datumsbasiert, da Serien Luecken haben).
    prev = float(series.iloc[-2]) if len(series) >= _MIN_PAIR else None
    changes: dict[str, Change] = {"1d": _change(current, prev)}

    for label, offset in _CHANGE_OFFSETS.items():
        past = _value_asof(series, last_date - offset)
        changes[label] = _change(current, past)
    return changes


def _band_from_percentile(percentile: float, *, stress_at_high: bool) -> Band:
    """Percentil-basierte Einordnung (Buckets gemaess Konzept §6).

    Liegt das Stress-Ende unten (lower_is_stress / higher_is_supportive), wird das
    Percentil gespiegelt, sodass dieselbe Bucket-Logik wiederverwendbar ist.
    """
    p = percentile if stress_at_high else 100.0 - percentile
    if p >= _PCT_STRESS:
        return Band.STRESS
    if p >= _PCT_ELEVATED:
        return Band.ELEVATED
    if p < _PCT_LOW:
        return Band.LOW
    return Band.NORMAL


def _band_from_thresholds(value: float, direction: Direction, t: Thresholds) -> Band:
    """Harte Schwellen. Fuer 'lower'/'supportive' liegt das Stress-Ende unten.

    Per Vorzeichen-Trick werden beide Richtungen mit denselben >=/<=-Vergleichen
    abgehandelt: ``value * sign >= schwelle * sign``.
    """
    stress_at_high = direction in (Direction.HIGHER_IS_STRESS, Direction.NEUTRAL)
    sign = 1.0 if stress_at_high else -1.0
    if t.stress is not None and value * sign >= t.stress * sign:
        return Band.STRESS
    if t.elevated is not None and value * sign >= t.elevated * sign:
        return Band.ELEVATED
    if t.low is not None and value * sign <= t.low * sign:
        return Band.LOW
    return Band.NORMAL


def classify_band(
    *,
    percentile: float,
    z: float | None,
    value: float,
    direction: Direction,
    thresholds: Thresholds | None,
) -> Band:
    """Bestimmt die Ampel-Band. Harte Schwellen haben Vorrang vor Percentilen."""
    if thresholds is not None and (
        thresholds.stress is not None
        or thresholds.elevated is not None
        or thresholds.low is not None
    ):
        return _band_from_thresholds(value, direction, thresholds)

    if direction is Direction.NEUTRAL:
        magnitude = abs(z) if z is not None else 0.0
        if magnitude > _Z_STRESS:
            return Band.STRESS
        if magnitude > _Z_ELEVATED:
            return Band.ELEVATED
        return Band.NORMAL

    stress_at_high = direction is Direction.HIGHER_IS_STRESS
    return _band_from_percentile(percentile, stress_at_high=stress_at_high)


def build_snapshot_stats(
    series: pd.Series,
    *,
    direction: Direction,
    thresholds: Thresholds | None,
    history_years: int = 10,
    z_years: int = 5,
) -> SnapshotStats:
    """Aggregiert alle Einordnungs-Metriken zu einem ``SnapshotStats``."""
    if series.empty:
        raise ValueError("Zeitreihe ist leer - keine Einordnung moeglich.")

    window_10y = slice_last_years(series, history_years)
    window_5y = slice_last_years(series, z_years)

    current = float(series.iloc[-1])
    percentile = percentile_of(window_10y, current)
    z = z_score(window_5y, current)
    band = classify_band(
        percentile=percentile,
        z=z,
        value=current,
        direction=direction,
        thresholds=thresholds,
    )

    return SnapshotStats(
        current=current,
        as_of=series.index[-1].strftime("%Y-%m-%d"),
        percentile_10y=round(percentile, 1),
        z_score_5y=None if z is None else round(z, 2),
        median_10y=float(window_10y.median()),
        min_10y=float(window_10y.min()),
        max_10y=float(window_10y.max()),
        band=band,
        changes=compute_changes(series),
    )
