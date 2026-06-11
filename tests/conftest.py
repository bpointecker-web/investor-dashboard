"""Gemeinsame Test-Fixtures: Settings, HTTP-Client, Fixture-Loader, Mock-Sources."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator, Callable
from pathlib import Path

import httpx
import pandas as pd
import pytest

from dashboard.config import Settings
from dashboard.data_sources.base import DataSourceError

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def settings() -> Settings:
    """Settings mit gesetztem FRED-Key (umgeht .env, deterministisch)."""
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        fred_api_key="test-key",  # type: ignore[arg-type]
        history_years=10,
        http_retries=1,
    )


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    """Async-HTTP-Client (von respx gemockt)."""
    async with httpx.AsyncClient() as ac:
        yield ac


@pytest.fixture
def load_fixture() -> Callable[[str], str]:
    """Laedt eine Fixture-Datei als Text."""

    def _load(name: str) -> str:
        return (FIXTURES_DIR / name).read_text(encoding="utf-8")

    return _load


@pytest.fixture
def load_json() -> Callable[[str], object]:
    """Laedt eine JSON-Fixture als Python-Objekt."""

    def _load(name: str) -> object:
        return json.loads((FIXTURES_DIR / name).read_text(encoding="utf-8"))

    return _load


class FakeSource:
    """In-Memory-DataSource fuer Service-/Computed-Tests (kein I/O)."""

    def __init__(self, name: str, data: dict[str, pd.Series]) -> None:
        self.name = name
        self._data = data
        self.calls: list[str] = []

    async def fetch(self, ref: str) -> pd.Series:
        self.calls.append(ref)
        if ref not in self._data:
            raise DataSourceError(self.name, ref, "nicht in FakeSource")
        return self._data[ref]
