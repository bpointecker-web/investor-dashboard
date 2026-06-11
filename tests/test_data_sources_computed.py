"""Tests fuer den Formel-Parser und die ComputedSource."""

from __future__ import annotations

import pandas as pd
import pytest

from dashboard.data_sources.base import DataSourceError
from dashboard.data_sources.computed import (
    ComputedSource,
    evaluate_rpn,
    extract_operands,
    to_rpn,
    tokenize,
)


def _series(values: list[float], start: str = "2024-01-01") -> pd.Series:
    idx = pd.date_range(start, periods=len(values), freq="D")
    return pd.Series(values, index=idx, dtype="float64")


class TestTokenize:
    def test_simple(self) -> None:
        tokens = tokenize("fred:WALCL - fred:WTREGEN")
        kinds = [t.kind for t in tokens]
        assert kinds == ["OPERAND", "OP", "OPERAND"]

    def test_func_and_parens(self) -> None:
        tokens = tokenize("norm100(stooq:^rut / stooq:^spx)")
        assert tokens[0].kind == "FUNC"
        assert tokens[1].kind == "LP"
        assert any(t.kind == "OPERAND" and t.text == "stooq:^rut" for t in tokens)

    def test_invalid_char_raises(self) -> None:
        with pytest.raises(ValueError, match="Ungueltiges Zeichen"):
            tokenize("fred:WALCL & fred:GDP")

    def test_empty_raises(self) -> None:
        with pytest.raises(ValueError, match="Leere Formel"):
            tokenize("   ")


class TestExtractOperands:
    def test_dedup(self) -> None:
        tokens = tokenize("fred:A / fred:A + fred:B")
        assert extract_operands(tokens) == [("fred", "A"), ("fred", "B")]


class TestRpnEvaluation:
    def test_precedence(self) -> None:
        # 100 + WILL/GDP*100 -> Multiplikation/Division vor Addition
        operands = {"fred:WILL5000PRFC": _series([2.0, 2.0]), "fred:GDP": _series([4.0, 4.0])}
        rpn = to_rpn(tokenize("fred:WILL5000PRFC / fred:GDP * 100"))
        result = evaluate_rpn(rpn, operands)
        assert list(result) == [50.0, 50.0]

    def test_subtraction_chain(self) -> None:
        operands = {
            "fred:WALCL": _series([100.0, 110.0]),
            "fred:WTREGEN": _series([10.0, 10.0]),
            "fred:RRPONTSYD": _series([5.0, 5.0]),
        }
        rpn = to_rpn(tokenize("fred:WALCL - fred:WTREGEN - fred:RRPONTSYD"))
        result = evaluate_rpn(rpn, operands)
        assert list(result) == [85.0, 95.0]

    def test_norm100(self) -> None:
        operands = {"stooq:^rut": _series([2.0, 3.0, 4.0]), "stooq:^spx": _series([2.0, 2.0, 2.0])}
        rpn = to_rpn(tokenize("norm100(stooq:^rut / stooq:^spx)"))
        result = evaluate_rpn(rpn, operands)
        # Ratio = [1, 1.5, 2] -> norm100 -> [100, 150, 200]
        assert list(result) == [100.0, 150.0, 200.0]

    def test_invert(self) -> None:
        operands = {"fred:X": _series([2.0, 4.0])}
        rpn = to_rpn(tokenize("invert(fred:X)"))
        result = evaluate_rpn(rpn, operands)
        assert list(result) == [0.5, 0.25]

    def test_unbalanced_parens_raises(self) -> None:
        with pytest.raises(ValueError, match="Unbalancierte"):
            to_rpn(tokenize("norm100(fred:X"))


class TestComputedSourceFetch:
    async def test_net_liquidity_alignment_and_ffill(self) -> None:
        # Unterschiedliche Frequenzen -> Union-Index + ffill
        data = {
            ("fred", "WALCL"): _series([100.0, 110.0, 120.0], start="2024-01-01"),
            ("fred", "WTREGEN"): pd.Series(
                [10.0], index=pd.to_datetime(["2024-01-02"]), dtype="float64"
            ),
            ("fred", "RRPONTSYD"): pd.Series(
                [5.0], index=pd.to_datetime(["2024-01-01"]), dtype="float64"
            ),
        }

        async def resolver(source: str, ref: str) -> pd.Series:
            return data[(source, ref)]

        source = ComputedSource(resolver)
        result = await source.fetch("fred:WALCL - fred:WTREGEN - fred:RRPONTSYD")

        # 2024-01-01: WTREGEN noch NaN -> dropna entfernt diese Zeile
        # 2024-01-02: 110 - 10 - 5 = 95 ; 2024-01-03: 120 - 10 - 5 = 105
        assert list(result) == [95.0, 105.0]

    async def test_missing_component_raises(self) -> None:
        async def resolver(source: str, ref: str) -> pd.Series:
            raise DataSourceError(source, ref, "down")

        source = ComputedSource(resolver)
        with pytest.raises(DataSourceError):
            await source.fetch("fred:WALCL - fred:WTREGEN")

    async def test_division_by_zero_dropped(self) -> None:
        data = {
            ("fred", "A"): _series([1.0, 2.0]),
            ("fred", "B"): _series([0.0, 2.0]),
        }

        async def resolver(source: str, ref: str) -> pd.Series:
            return data[(source, ref)]

        source = ComputedSource(resolver)
        result = await source.fetch("fred:A / fred:B")
        # 1/0 -> inf -> NaN -> dropped ; 2/2 -> 1.0
        assert list(result) == [1.0]

    async def test_bad_formula_raises(self) -> None:
        async def resolver(source: str, ref: str) -> pd.Series:
            return _series([1.0])

        source = ComputedSource(resolver)
        with pytest.raises(DataSourceError, match="Formel-Fehler"):
            await source.fetch("fred:A %% fred:B")
