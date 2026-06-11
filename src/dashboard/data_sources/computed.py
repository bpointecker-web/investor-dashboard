"""Berechnete Indikatoren ueber einen sicheren Formel-Parser (KEIN eval/exec).

Eine Formel kombiniert andere Quellen-Serien arithmetisch, z.B.::

    fred:WALCL - fred:WTREGEN - fred:RRPONTSYD
    norm100(stooq:^rut / stooq:^spx)
    fred:WILL5000PRFC / fred:GDP * 100

Unterstuetzt: Operanden ``source:ref``, Zahlen, ``+ - * /``, Klammern sowie die
Funktionen ``norm100`` (Normierung auf Startwert 100) und ``invert`` (1/x).
Komponenten werden ueber einen Resolver (Service-Layer) geladen und per
``reindex().ffill()`` auf einen gemeinsamen taeglichen Index gebracht.
"""

from __future__ import annotations

import re
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

import numpy as np
import pandas as pd

from dashboard.data_sources.base import DataSourceError

# Resolver: (source, ref) -> native Zeitreihe. Vom Service injiziert.
Resolver = Callable[[str, str], Awaitable[pd.Series]]

_FUNCTIONS = frozenset({"norm100", "invert"})
_PRECEDENCE = {"+": 1, "-": 1, "*": 2, "/": 2}
_BINARY_ARITY = 2

_TOKEN_RE = re.compile(
    r"""
      (?P<WS>\s+)
    | (?P<FUNC>norm100|invert)
    | (?P<OPERAND>[a-z]+:[A-Za-z0-9^._]+)
    | (?P<NUMBER>\d+(?:\.\d+)?)
    | (?P<OP>[+\-*/])
    | (?P<LP>\()
    | (?P<RP>\))
    """,
    re.VERBOSE,
)


@dataclass(frozen=True)
class Token:
    """Ein lexikalisches Token der Formel."""

    kind: str
    text: str


def tokenize(formula: str) -> list[Token]:
    """Zerlegt eine Formel in Tokens; wirft bei unbekannten Zeichen."""
    tokens: list[Token] = []
    pos = 0
    for match in _TOKEN_RE.finditer(formula):
        if match.start() != pos:
            bad = formula[pos : match.start()]
            raise ValueError(f"Ungueltiges Zeichen in Formel: {bad!r}")
        pos = match.end()
        kind = match.lastgroup or ""
        if kind == "WS":
            continue
        tokens.append(Token(kind, match.group()))
    if pos != len(formula):
        raise ValueError(f"Formel-Rest nicht parsebar: {formula[pos:]!r}")
    if not tokens:
        raise ValueError("Leere Formel.")
    return tokens


def to_rpn(tokens: list[Token]) -> list[Token]:
    """Shunting-Yard: Infix-Tokens -> Reverse Polish Notation."""
    output: list[Token] = []
    stack: list[Token] = []
    for token in tokens:
        if token.kind in ("OPERAND", "NUMBER"):
            output.append(token)
        elif token.kind == "FUNC":
            stack.append(token)
        elif token.kind == "OP":
            while (
                stack
                and stack[-1].kind == "OP"
                and _PRECEDENCE[stack[-1].text] >= _PRECEDENCE[token.text]
            ):
                output.append(stack.pop())
            stack.append(token)
        elif token.kind == "LP":
            stack.append(token)
        elif token.kind == "RP":
            while stack and stack[-1].kind != "LP":
                output.append(stack.pop())
            if not stack:
                raise ValueError("Unbalancierte Klammern (zu viele ')').")
            stack.pop()  # LP verwerfen
            if stack and stack[-1].kind == "FUNC":
                output.append(stack.pop())
    while stack:
        top = stack.pop()
        if top.kind in ("LP", "RP"):
            raise ValueError("Unbalancierte Klammern.")
        output.append(top)
    return output


def extract_operands(tokens: list[Token]) -> list[tuple[str, str]]:
    """Liefert die eindeutigen ``(source, ref)``-Paare der Formel."""
    seen: dict[str, tuple[str, str]] = {}
    for token in tokens:
        if token.kind == "OPERAND":
            source, ref = token.text.split(":", 1)
            seen[token.text] = (source, ref)
    return list(seen.values())


def _align(series_map: dict[str, pd.Series]) -> dict[str, pd.Series]:
    """Bringt alle Serien per Vereinigungs-Index + ffill auf gleiche Frequenz."""
    union: pd.Index = pd.Index([])
    for series in series_map.values():
        union = union.union(series.index)
    sorted_index = pd.DatetimeIndex(union).sort_values()
    return {key: series.reindex(sorted_index).ffill() for key, series in series_map.items()}


def _apply_op(left: object, right: object, op: str) -> object:
    """Wendet einen Binaeroperator auf Series/Skalare an."""
    if op == "+":
        return left + right  # type: ignore[operator]
    if op == "-":
        return left - right  # type: ignore[operator]
    if op == "*":
        return left * right  # type: ignore[operator]
    return left / right  # type: ignore[operator]


def _apply_func(name: str, value: object) -> object:
    """Wendet eine unaere Funktion (norm100/invert) an."""
    if name == "invert":
        return 1.0 / value  # type: ignore[operator]
    # norm100: auf ersten gueltigen Wert normieren.
    if not isinstance(value, pd.Series):
        raise ValueError("norm100 erwartet eine Zeitreihe, keinen Skalar.")
    first_valid = value.first_valid_index()
    if first_valid is None:
        raise ValueError("norm100: Serie ohne gueltige Werte.")
    base = float(value.loc[first_valid])
    if base == 0:
        raise ValueError("norm100: Startwert ist 0.")
    return value / base * 100.0


def evaluate_rpn(rpn: list[Token], operands: dict[str, pd.Series]) -> pd.Series:
    """Wertet RPN-Tokens ueber die (ausgerichteten) Operanden-Serien aus."""
    stack: list[object] = []
    for token in rpn:
        if token.kind == "OPERAND":
            stack.append(operands[token.text])
        elif token.kind == "NUMBER":
            stack.append(float(token.text))
        elif token.kind == "OP":
            if len(stack) < _BINARY_ARITY:
                raise ValueError("Formel-Syntaxfehler (Operator ohne Operanden).")
            right = stack.pop()
            left = stack.pop()
            stack.append(_apply_op(left, right, token.text))
        elif token.kind == "FUNC":
            if not stack:
                raise ValueError("Funktion ohne Argument.")
            stack.append(_apply_func(token.text, stack.pop()))
    if len(stack) != 1:
        raise ValueError("Formel-Syntaxfehler (unvollstaendiger Ausdruck).")
    result = stack[0]
    if not isinstance(result, pd.Series):
        raise ValueError("Formel ergibt keinen Zeitreihen-Wert.")
    return result


class ComputedSource:
    """Berechnet Composite-Serien aus Formeln; nutzt andere Quellen via Resolver."""

    name = "computed"

    def __init__(self, resolver: Resolver) -> None:
        self._resolver = resolver

    async def fetch(self, ref: str) -> pd.Series:
        """``ref`` ist hier die Formel selbst (aus dem Manifest)."""
        try:
            tokens = tokenize(ref)
            rpn = to_rpn(tokens)
        except ValueError as exc:
            raise DataSourceError(self.name, ref, f"Formel-Fehler: {exc}") from exc

        series_map: dict[str, pd.Series] = {}
        for source, sub_ref in extract_operands(tokens):
            series_map[f"{source}:{sub_ref}"] = await self._resolver(source, sub_ref)

        aligned = _align(series_map)
        try:
            result = evaluate_rpn(rpn, aligned)
        except (ValueError, ZeroDivisionError) as exc:
            raise DataSourceError(self.name, ref, f"Auswertung fehlgeschlagen: {exc}") from exc

        result = result.replace([np.inf, -np.inf], np.nan).dropna()
        if result.empty:
            raise DataSourceError(self.name, ref, "Composite-Serie ist leer.")
        return result.sort_index()
