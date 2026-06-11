"""Tests fuer die Formatierungs-Helfer (Zahlen, Rich-Text)."""

from __future__ import annotations

from dashboard.formatting import format_number, format_richtext


def test_format_number_german_style() -> None:
    assert format_number(1234.5, 1) == "1.234,5"
    assert format_number(None, 2) == "–"  # noqa: RUF001


def test_richtext_splits_paragraphs() -> None:
    out = str(format_richtext("Absatz eins.\n\nAbsatz zwei."))
    assert out == "<p>Absatz eins.</p><p>Absatz zwei.</p>"


def test_richtext_converts_bold() -> None:
    out = str(format_richtext("**Fett:** normal."))
    assert "<strong>Fett:</strong> normal." in out


def test_richtext_joins_wrapped_lines_with_space() -> None:
    out = str(format_richtext("Zeile eins\nZeile zwei."))
    assert out == "<p>Zeile eins Zeile zwei.</p>"


def test_richtext_escapes_html() -> None:
    out = str(format_richtext("<script>alert(1)</script>"))
    assert "<script>" not in out
    assert "&lt;script&gt;" in out
