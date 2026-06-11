"""Anwendungs-Konfiguration via Pydantic Settings (aus `.env` + Umgebungsvariablen)."""

from __future__ import annotations

from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Zentrale, typisierte Konfiguration.

    Secrets (FRED-Key) werden als ``SecretStr`` gehalten, damit sie nicht
    versehentlich in Logs landen. Alle Nicht-Secret-Werte haben sichere Defaults.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        # utf-8-sig statt utf-8: entfernt ein evtl. BOM, das PowerShell beim
        # Schreiben der .env voranstellt (sonst wird der erste Key unlesbar).
        env_file_encoding="utf-8-sig",
        extra="ignore",
        env_prefix="",
    )

    # ---- Secrets ------------------------------------------------------------
    fred_api_key: SecretStr = Field(
        default=SecretStr(""),
        description="FRED API Key (kostenlos). Pflicht fuer FRED-Quellen.",
    )
    coingecko_api_key: SecretStr | None = Field(
        default=None,
        description="Optionaler CoinGecko-Key (Free-Tier funktioniert ohne).",
    )

    # ---- Server -------------------------------------------------------------
    dashboard_host: str = "127.0.0.1"
    dashboard_port: int = 8000

    # ---- Logging ------------------------------------------------------------
    log_level: str = "INFO"
    log_json: bool = False

    # ---- Historie & Cache ---------------------------------------------------
    history_years: int = 10
    default_cache_ttl_minutes: int = 60
    http_timeout_seconds: float = 10.0
    http_retries: int = 1

    # ---- User-Agent fuer externe Calls (manche Quellen blocken ohne) --------
    user_agent: str = "investor-dashboard/0.1 (+https://localhost)"

    # ---- Quellen-URLs (selten zu aendern) -----------------------------------
    fred_base_url: str = "https://api.stlouisfed.org/fred"
    stooq_base_url: str = "https://stooq.com/q/d/l/"
    # Yahoo Finance Chart-API als Fallback fuer stooq (stooq blockt teils ganze IPs).
    yahoo_base_url: str = "https://query1.finance.yahoo.com"
    coingecko_base_url: str = "https://api.coingecko.com/api/v3"
    # Shiller/NAAIM nutzen datierte/versionierte Dateinamen -> Link-Discovery von der
    # jeweiligen Seite (Fallback: direkte URL, falls Discovery scheitert).
    shiller_page_url: str = "https://shillerdata.com/"
    shiller_xls_url: str = (
        "https://img1.wsimg.com/blobby/go/e5e77e0b-59d1-44d9-ab25-4763ac982e53/"
        "downloads/c9b8cf0f-f01a-49f5-9ea5-d19443390ab2/ie_data.xls"
    )
    naaim_page_url: str = "https://naaim.org/programs/naaim-exposure-index/"
    naaim_xls_url: str = ""  # leer -> ausschliesslich Discovery

    # CFTC Public Reporting (Socrata): Legacy "Futures Only" Dataset.
    cftc_base_url: str = "https://publicreporting.cftc.gov/resource"
    cftc_dataset: str = "6dca-aqww"

    # CNN Fear & Greed (inoffiziell) - liefert auch die CBOE-Put/Call-Ratio.
    cnn_fear_greed_url: str = "https://production.dataviz.cnn.io/index/fearandgreed/graphdata"
    cnn_referer: str = "https://edition.cnn.com/"

    def require_fred_key(self) -> str:
        """Gibt den FRED-Key zurueck oder wirft Fail-Fast, wenn er fehlt."""
        key = self.fred_api_key.get_secret_value().strip()
        if not key:
            raise RuntimeError(
                "FRED_API_KEY fehlt. Bitte in `.env` eintragen "
                "(kostenlos: https://fred.stlouisfed.org/docs/api/api_key.html)."
            )
        return key


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Liefert eine gecachte Settings-Instanz (einmalig aus Env geladen)."""
    return Settings()
