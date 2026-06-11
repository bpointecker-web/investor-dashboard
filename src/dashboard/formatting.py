"""Reine Formatierungs-Helfer fuer die Templates (Zahlen, Ampel, Labels)."""

from __future__ import annotations

import re

from markupsafe import Markup, escape

from dashboard.indicators.models import Band, Category, Direction, Indicator, SourceKind

_EMPTY = "–"  # noqa: RUF001  # Gedankenstrich als Platzhalter fuer fehlende Werte

# Markdown-artige Fett-Auszeichnung **so** -> <strong>so</strong>.
_BOLD_RE = re.compile(r"\*\*(.+?)\*\*")

_CATEGORY_LABELS: dict[str, str] = {
    Category.CREDIT.value: "Credit Spreads",
    Category.RATES.value: "Zinsen & Zinskurve",
    Category.INFLATION.value: "Inflationserwartungen",
    Category.VOLATILITY.value: "Volatilitaet",
    Category.FX.value: "Waehrungen (FX)",
    Category.COMMODITIES.value: "Rohstoffe",
    Category.EQUITIES.value: "Aktien",
    Category.BREADTH.value: "Marktbreite & Konzentration",
    Category.SENTIMENT.value: "Sentiment & Positionierung",
    Category.VALUATION.value: "Bewertung",
    Category.LIQUIDITY.value: "Liquiditaet & Geldmenge",
    Category.CRYPTO.value: "Krypto",
}

_BAND_DOT: dict[Band, str] = {
    Band.LOW: "🟢",
    Band.NORMAL: "🔵",
    Band.ELEVATED: "🟠",
    Band.STRESS: "🔴",
}

_BAND_LABEL_DEFAULT: dict[Band, str] = {
    Band.LOW: "Niedrig",
    Band.NORMAL: "Normal",
    Band.ELEVATED: "Erhoeht",
    Band.STRESS: "Stress",
}

# Fuer 'higher_is_supportive' liegt das Stress-Ende unten -> sprechendere Labels.
_BAND_LABEL_SUPPORTIVE: dict[Band, str] = {
    Band.LOW: "Expansiv",
    Band.NORMAL: "Normal",
    Band.ELEVATED: "Knapp",
    Band.STRESS: "Restriktiv",
}


def format_number(value: float | None, decimals: int = 2) -> str:
    """Formatiert eine Zahl im deutschen Stil (1.234,56). None -> Gedankenstrich."""
    if value is None:
        return _EMPTY
    english = f"{value:,.{decimals}f}"  # 1,234.56
    # Trennzeichen tauschen: , <-> .
    return english.replace(",", "\0").replace(".", ",").replace("\0", ".")


def format_percent(value: float | None, decimals: int = 1) -> str:
    """Formatiert einen Prozentwert mit Vorzeichen (z.B. +2,3 %)."""
    if value is None:
        return _EMPTY
    return f"{value:+.{decimals}f} %".replace(".", ",")


def format_signed(value: float | None, decimals: int = 2) -> str:
    """Formatiert eine absolute Aenderung mit Vorzeichen."""
    if value is None:
        return _EMPTY
    sign = "+" if value >= 0 else "-"
    return sign + format_number(abs(value), decimals)


def change_class(value: float | None) -> str:
    """CSS-Klasse fuer Auf-/Abwaerts-Faerbung."""
    if value is None:
        return "flat"
    if value > 0:
        return "pos"
    if value < 0:
        return "neg"
    return "flat"


def band_dot(band: Band) -> str:
    """Ampel-Emoji fuer ein Band."""
    return _BAND_DOT[band]


def band_label(band: Band, direction: Direction) -> str:
    """Sprechendes Band-Label, abhaengig von der Richtungs-Semantik."""
    if direction is Direction.HIGHER_IS_SUPPORTIVE:
        return _BAND_LABEL_SUPPORTIVE[band]
    return _BAND_LABEL_DEFAULT[band]


def format_richtext(text: str) -> Markup:
    """Wandelt einfachen Text in sicheres HTML: Absaetze (Leerzeile) + **fett**.

    Erst wird komplett HTML-escaped (kein Injection-Risiko), danach werden die
    eigenen, kontrollierten Tags (<p>, <strong>) eingefuegt.
    """
    paragraphs = [block.strip() for block in text.strip().split("\n\n") if block.strip()]
    html_parts: list[str] = []
    for block in paragraphs:
        escaped = str(escape(block)).replace("\n", " ")
        bolded = _BOLD_RE.sub(r"<strong>\1</strong>", escaped)
        html_parts.append(f"<p>{bolded}</p>")
    return Markup("".join(html_parts))  # Inhalt wurde zuvor vollstaendig escaped


def category_label(category: str) -> str:
    """Deutsches Anzeige-Label einer Kategorie."""
    return _CATEGORY_LABELS.get(category, category.capitalize())


def source_url(indicator: Indicator) -> str | None:
    """Transparenz-Link zur Datenquelle (None bei computed)."""
    if indicator.source is SourceKind.FRED and indicator.series_id:
        return f"https://fred.stlouisfed.org/series/{indicator.series_id}"
    if indicator.source is SourceKind.STOOQ and indicator.symbol:
        return f"https://stooq.com/q/?s={indicator.symbol}"
    if indicator.source is SourceKind.COINGECKO and indicator.symbol:
        return f"https://www.coingecko.com/en/coins/{indicator.symbol}"
    return None
