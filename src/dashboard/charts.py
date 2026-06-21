"""Plotly-Helfer: erzeugt Sparkline- und Detail-Figuren als JSON.

Die Figuren werden als JSON eingebettet und clientseitig via plotly.js gerendert.
"""

from __future__ import annotations

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
