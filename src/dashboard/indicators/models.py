"""Pydantic-Datenmodelle fuer Indikatoren, Snapshots und statistische Einordnung."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Category(StrEnum):
    """Die 12 Indikator-Kategorien."""

    CREDIT = "credit"
    RATES = "rates"
    INFLATION = "inflation"
    VOLATILITY = "volatility"
    FX = "fx"
    COMMODITIES = "commodities"
    EQUITIES = "equities"
    BREADTH = "breadth"
    SENTIMENT = "sentiment"
    VALUATION = "valuation"
    LIQUIDITY = "liquidity"
    CRYPTO = "crypto"


class SourceKind(StrEnum):
    """Unterstuetzte Datenquellen-Typen."""

    FRED = "fred"
    STOOQ = "stooq"
    COINGECKO = "coingecko"
    SHILLER = "shiller"
    NAAIM = "naaim"
    CFTC = "cftc"
    CBOE = "cboe"
    CNN = "cnn"
    COMPUTED = "computed"


class Direction(StrEnum):
    """Richtungs-Semantik fuer die Ampel-Logik."""

    HIGHER_IS_STRESS = "higher_is_stress"
    LOWER_IS_STRESS = "lower_is_stress"
    HIGHER_IS_SUPPORTIVE = "higher_is_supportive"
    NEUTRAL = "neutral"


class Band(StrEnum):
    """Ampel-Einordnung eines aktuellen Werts."""

    LOW = "low"
    NORMAL = "normal"
    ELEVATED = "elevated"
    STRESS = "stress"


class SnapshotStatus(StrEnum):
    """Lade-Status einer Indikator-Karte (Card-Level-Degradation)."""

    OK = "ok"
    ERROR = "error"


class Thresholds(BaseModel):
    """Harte Schwellen (in Anzeige-Einheiten). Haben Vorrang vor Percentilen."""

    model_config = ConfigDict(extra="forbid")

    low: float | None = None
    elevated: float | None = None
    stress: float | None = None


class Indicator(BaseModel):
    """Deklarative Indikator-Definition aus dem Manifest."""

    model_config = ConfigDict(extra="forbid")

    id: str
    name: str
    category: Category
    source: SourceKind
    unit: str
    direction: Direction = Direction.NEUTRAL
    decimals: int = 2
    display_multiplier: float = 1.0
    cache_ttl_minutes: int | None = None
    # Wichtigkeit: hoeher = wichtiger. 0 = normal. Steuert Reihenfolge, Stern, Filter.
    priority: int = 0

    # Quellen-spezifische Referenz (genau eine ist je nach `source` relevant)
    series_id: str | None = None
    symbol: str | None = None
    formula: str | None = None

    thresholds: Thresholds | None = None

    # Didaktik (Deutsch)
    what: str = ""
    why: str = ""
    example: str = ""
    rules: str = ""  # optionale Faustregeln fuer Investoren

    @model_validator(mode="after")
    def _check_source_ref(self) -> Indicator:
        """Stellt sicher, dass die zur Quelle passende Referenz gesetzt ist."""
        ref_field = {
            SourceKind.FRED: "series_id",
            SourceKind.COMPUTED: "formula",
        }.get(self.source, "symbol")

        # CFTC/Shiller/NAAIM/CBOE/CNN identifizieren sich ueber `symbol` (frei nutzbar)
        # bzw. brauchen keine Referenz; FRED/computed sind strikt.
        if self.source in (SourceKind.FRED, SourceKind.COMPUTED) and not getattr(self, ref_field):
            raise ValueError(
                f"Indikator '{self.id}' (source={self.source.value}) "
                f"benoetigt das Feld '{ref_field}'."
            )
        return self

    @property
    def source_ref(self) -> str:
        """Die fuer die Quelle relevante Referenz (series_id | symbol | formula)."""
        return self.series_id or self.symbol or self.formula or self.id


class Change(BaseModel):
    """Absolute und relative Veraenderung ueber einen Zeitraum."""

    absolute: float | None = None
    percent: float | None = None


class SnapshotStats(BaseModel):
    """Statistische Einordnung eines Indikators (alles in Anzeige-Einheiten)."""

    current: float
    as_of: str  # ISO-Datum des letzten Werts
    percentile_10y: float
    z_score_5y: float | None
    median_10y: float
    min_10y: float
    max_10y: float
    band: Band
    changes: dict[str, Change] = Field(default_factory=dict)


class IndicatorSnapshot(BaseModel):
    """Vollstaendiger Snapshot inkl. Zeitreihe fuer Sparkline/Histogramm."""

    indicator: Indicator
    status: SnapshotStatus
    error: str | None = None
    stats: SnapshotStats | None = None

    # Zeitreihe in Anzeige-Einheiten (parallele Listen, JSON-serialisierbar)
    series_dates: list[str] = Field(default_factory=list)
    series_values: list[float] = Field(default_factory=list)
