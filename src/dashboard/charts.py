"""Plotly-Helfer: erzeugt Sparkline-, Detail- und Histogramm-Figuren als JSON.

Die Figuren werden als JSON eingebettet und clientseitig via plotly.js gerendert.
"""

from __future__ import annotations

import numpy as np
import plotly.graph_objects as go

from dashboard.indicators.models import Band, IndicatorSnapshot

# Farbzuordnung der Ampel-Baender (auch in CSS gespiegelt).
BAND_COLORS: dict[Band, str] = {
    Band.LOW: "#2e7d32",
    Band.NORMAL: "#1565c0",
    Band.ELEVATED: "#ef6c00",
    Band.STRESS: "#c62828",
}

_TRANSPARENT = "rgba(0,0,0,0)"
_SPARKLINE_MAX_POINTS = 200
_QUANTILES = (10, 25, 50, 75, 90)


def _band_color(snapshot: IndicatorSnapshot) -> str:
    if snapshot.stats is None:
        return BAND_COLORS[Band.NORMAL]
    return BAND_COLORS[snapshot.stats.band]


def _downsample(
    dates: list[str], values: list[float], max_points: int
) -> tuple[list[str], list[float]]:
    """Reduziert Punkte gleichmaessig (letzter Punkt bleibt erhalten)."""
    n = len(values)
    if n <= max_points:
        return dates, values
    step = n // max_points
    idx = list(range(0, n, step))
    if idx[-1] != n - 1:
        idx.append(n - 1)
    return [dates[i] for i in idx], [values[i] for i in idx]


def sparkline_json(snapshot: IndicatorSnapshot) -> str:
    """Achsenlose Mini-Sparkline (10 Jahre) eingefaerbt nach Ampel-Band."""
    dates, values = _downsample(
        snapshot.series_dates, snapshot.series_values, _SPARKLINE_MAX_POINTS
    )
    fig = go.Figure(
        go.Scatter(
            x=dates,
            y=values,
            mode="lines",
            line={"width": 1.6, "color": _band_color(snapshot)},
            hoverinfo="skip",
        )
    )
    fig.update_layout(
        height=48,
        margin={"l": 0, "r": 0, "t": 0, "b": 0},
        paper_bgcolor=_TRANSPARENT,
        plot_bgcolor=_TRANSPARENT,
        showlegend=False,
        xaxis={"visible": False, "fixedrange": True},
        yaxis={"visible": False, "fixedrange": True},
    )
    return str(fig.to_json())


def detail_chart_json(snapshot: IndicatorSnapshot) -> str:
    """Grosser interaktiver Verlaufschart mit Range-Slider."""
    fig = go.Figure(
        go.Scatter(
            x=snapshot.series_dates,
            y=snapshot.series_values,
            mode="lines",
            line={"width": 1.8, "color": _band_color(snapshot)},
            name=snapshot.indicator.name,
        )
    )
    fig.update_layout(
        height=440,
        margin={"l": 50, "r": 20, "t": 20, "b": 30},
        paper_bgcolor=_TRANSPARENT,
        plot_bgcolor=_TRANSPARENT,
        showlegend=False,
        hovermode="x unified",
        xaxis={"rangeslider": {"visible": True}, "type": "date"},
        yaxis={"title": {"text": snapshot.indicator.unit}, "fixedrange": False},
    )
    return str(fig.to_json())


def histogram_json(snapshot: IndicatorSnapshot) -> str:
    """Verteilungs-Histogramm mit Quantil-Linien und aktuellem Wert."""
    values = np.asarray(snapshot.series_values, dtype="float64")
    fig = go.Figure(
        go.Histogram(
            x=values,
            nbinsx=40,
            marker={"color": "#90a4ae"},
            opacity=0.75,
            hovertemplate="%{x}<br>n=%{y}<extra></extra>",
        )
    )

    for q in _QUANTILES:
        qv = float(np.percentile(values, q))
        fig.add_vline(
            x=qv,
            line={"color": "#607d8b", "width": 1, "dash": "dot"},
            annotation_text=f"P{q}",
            annotation_position="top",
        )

    if snapshot.stats is not None:
        fig.add_vline(
            x=snapshot.stats.current,
            line={"color": _band_color(snapshot), "width": 2.5},
            annotation_text="aktuell",
            annotation_position="top right",
        )

    fig.update_layout(
        height=360,
        margin={"l": 50, "r": 20, "t": 30, "b": 30},
        paper_bgcolor=_TRANSPARENT,
        plot_bgcolor=_TRANSPARENT,
        showlegend=False,
        bargap=0.02,
        xaxis={"title": {"text": snapshot.indicator.unit}},
        yaxis={"title": {"text": "Haeufigkeit"}},
    )
    return str(fig.to_json())
