# 📊 Investor Dashboard

Lokales, **stateless** Web-Dashboard mit den wichtigsten globalen Marktindikatoren —
asset-übergreifend (Credit, Rates, Inflation, Vola, FX, Commodities, Equities, Breadth,
Valuation, Liquidity, Crypto). Jeder Indikator wird mit aktuellem Wert dargestellt,
**statistisch eingeordnet** (10-Jahres-Percentil, Z-Score, Ampel), mit Sparkline +
Verteilungshistogramm visualisiert und **auf Deutsch didaktisch erklärt**.

Keine Datenbank, kein Scheduler: Bei jedem Page-Load werden die Zeitreihen frisch gezogen
und im Memory gecached (60 min für tägliche Quellen, 24 h für niederfrequente). Die
Einordnung erfolgt on-the-fly aus der gezogenen Historie.

> **Implementierungsstand:** Alle **39 Indikatoren in 12 Kategorien** über 9 Datenquellen
> sind fertig, getestet und live verifiziert (86 Tests, ~92 % Coverage).

---

## 🚀 Quickstart

```powershell
# 1. Abhängigkeiten installieren (legt .venv an)
uv sync

# 2. FRED-API-Key eintragen (kostenlos)
Copy-Item .env.example .env
#   -> FRED_API_KEY in .env eintragen

# 3. Starten
.\tasks.ps1 run        # bzw.:  uv run python -m dashboard
#   -> http://localhost:8000
```

**Voraussetzungen:** Python 3.12+, [uv](https://docs.astral.sh/uv/),
ein kostenloser [FRED API Key](https://fred.stlouisfed.org/docs/api/api_key.html).

### Task-Runner

`make` ist auf Windows meist nicht installiert — daher liegt ein gleichwertiges
PowerShell-Skript bei. Beide Wege funktionieren:

| Aufgabe | PowerShell | Make |
|---|---|---|
| Installieren | `.\tasks.ps1 install` | `make install` |
| Starten | `.\tasks.ps1 run` | `make run` |
| Tests + Coverage | `.\tasks.ps1 test` | `make test` |
| Linting | `.\tasks.ps1 lint` | `make lint` |
| Typecheck | `.\tasks.ps1 typecheck` | `make typecheck` |
| Formatieren | `.\tasks.ps1 format` | `make format` |
| Alles (CI-Gate) | `.\tasks.ps1 check` | `make check` |

> **Hinweis:** Wegen einer Windows-Application-Control-Richtlinie werden die venv-Konsolen-
> Skripte (`pytest.exe`, `ruff.exe` …) ggf. blockiert. Die Tasks rufen die Tools daher als
> Module auf (`uv run python -m pytest`), was diese Blockade umgeht.

---

## 🏗️ Architektur

Saubere Schichtung mit Dependency Inversion — Datenquellen sind über ein `DataSource`-
Protocol austauschbar, die Statistik ist rein (kein I/O), die Routen lesen alles per
FastAPI-`Depends` aus dem App-State (keine Globals).

```
                    ┌──────────────────────────────────────────┐
   HTTP-Request ───▶│  routes/  (pages.py · api.py)             │
                    │  Jinja2-Templates + HTMX + Plotly (JSON)  │
                    └───────────────────┬──────────────────────┘
                                        │ Depends()
                    ┌───────────────────▼──────────────────────┐
                    │  indicators/service.py                    │
                    │  Orchestrierung · Cache · Skalierung      │
                    └───┬───────────────┬───────────────────┬──┘
            ┌───────────▼──┐   ┌────────▼────────┐   ┌──────▼──────────┐
            │ data_sources │   │ indicators/     │   │ indicators/     │
            │  fred/stooq/ │   │ stats.py (rein) │   │ registry.py     │
            │  coingecko/  │   │ Percentil·Z·Band│   │ manifest.yaml   │
            │  computed    │   └─────────────────┘   └─────────────────┘
            └──────┬───────┘
                   │  In-Memory-TTL-Cache (cache.py)
            externe APIs (FRED, stooq, CoinGecko …)
```

**Datenfluss:** Manifest (YAML) → Registry → Service zieht je Indikator die native
Zeitreihe (Cache → Quelle), skaliert sie mit `display_multiplier`, berechnet die
Einordnung in `stats.py` und liefert einen `IndicatorSnapshot`. Fehler einzelner
Quellen degradieren nur die betroffene Karte (Card-Level-Degradation).

**Computed-Indikatoren** nutzen einen sicheren Formel-Parser (Tokenizer + Shunting-Yard,
**kein `eval`/`exec`**) und beziehen ihre Komponenten über den Service-Layer.

---

## 📈 Indikatoren

39 Indikatoren in 12 Kategorien:

| Kategorie | Indikatoren |
|---|---|
| **Credit** | US HY / US IG / EU HY Spread (OAS) |
| **Rates** | US 10Y · 10Y-2Y · 10Y-3M · DE 10Y Bund · Fed Funds |
| **Inflation** | US 5Y Breakeven · 5Y5Y Forward |
| **Volatility** | VIX |
| **FX** | DXY · EUR/USD · EUR/CHF |
| **Commodities** | Gold · Brent · Copper |
| **Equities** | S&P 500 · Stoxx 600 · DAX · ATX · MSCI EM (EEM) |
| **Breadth** | Russell 2000 · R2K/S&P-Ratio · RSP/SPY-Ratio |
| **Sentiment** | CNN Fear & Greed · NAAIM Exposure · CBOE Put/Call · CFTC Spec Net (S&P E-mini) |
| **Valuation** | Buffett Indicator · Shiller CAPE · Equity Risk Premium |
| **Liquidity** | Fed Assets · M2 · Reverse Repo · TGA · **Net Liquidity** |
| **Crypto** | Bitcoin · Ethereum |

Der vollständige Katalog inkl. didaktischer Texte und Schwellen steht in
[`src/dashboard/indicators/manifest.yaml`](src/dashboard/indicators/manifest.yaml).

### Ampel-Logik (`band`)

- **Harte Schwellen** (`thresholds` im Manifest) haben Vorrang (z.B. VIX, Credit Spreads).
- Sonst **Percentil-basiert** je nach `direction`:
  `higher_is_stress` · `lower_is_stress` · `higher_is_supportive` · `neutral` (|Z-Score|).

---

## 🔌 Datenquellen & Wartungsrisiko

| Quelle | Indikatoren | Key nötig | Stabilität | Anmerkung |
|---|---|---|---|---|
| **FRED** | 18 | ✅ kostenlos | 🟢 sehr hoch | Offizielle Behörden-API |
| **stooq** | 10 | ❌ | 🟡 mittel | CSV-Download; **bei Ausfall automatisch Yahoo-Fallback** |
| **Yahoo** | (Fallback) | ❌ | 🟢 hoch | Chart-JSON-API; springt ein, wenn stooq 404t |
| **CoinGecko** | 2 | ❌ (optional) | 🟡 mittel | **Free-Tier: max. 365 Tage Historie** |
| **CFTC** | 1 | ❌ | 🟢 hoch | Public Reporting API (Socrata, Legacy Futures-Only) |
| **CNN** | 1 | ❌ | 🔴 niedrig | Inoffizieller JSON-Endpoint (Fear & Greed) |
| **CBOE** | 1 | ❌ | 🟡 mittel | CBOE-Feed eingestellt → Put/Call via CNN-Datensatz |
| **Shiller** | 1 | ❌ | 🟡 mittel | Yale-Excel, Link-Discovery von shillerdata.com |
| **NAAIM** | 1 | ❌ | 🟡 mittel | Excel, Link-Discovery (datierter Dateiname) |
| **computed** | 5 | – | 🟢 | Net Liquidity, Buffett, ERP, 2× Breadth-Ratio |

**Bekannte Free-Tier-/Umgebungs-Eigenheiten (beim Bau live verifiziert):**

- **CoinGecko** liefert ohne (Pro-)Key maximal **365 Tage**; die Quelle kappt `days`
  entsprechend automatisch (sonst HTTP 401). Crypto-Percentile beziehen sich daher
  ohne Key auf ~1 Jahr.
- **stooq** sperrt den CSV-Download (`/q/d/l/`) für manche IPs (Soft-404) oder limitiert
  pro Tag. Deshalb gibt es einen **automatischen Yahoo-Fallback**: schlägt stooq fehl,
  wird dasselbe Symbol über Yahoos Chart-JSON-API geladen (`FallbackSource`-Wrapper,
  stooq → Yahoo). Die 10 betroffenen Karten bleiben so auch bei stooq-Ausfall verfügbar.
- **CBOE** hat den freien programmatischen Zugang zu den Put/Call-Statistiken
  eingestellt (alle CDN-Endpoints liefern 403). Die CBOE-Total-Put/Call-Ratio wird daher
  über den öffentlichen CNN-Datensatz bezogen (dieselbe CBOE-Quelle, von CNN aufbereitet).
- **Shiller & NAAIM** nutzen datierte/versionierte Dateinamen; die Quellen ermitteln den
  aktuellen Link automatisch von der jeweiligen Seite (Fallback: konfigurierte Direkt-URL).
- **Net Liquidity** korrigiert eine Einheiten-Falle: `WALCL`/`WTREGEN` stehen in Mio USD,
  `RRPONTSYD` in Mrd USD. Die Formel rechnet daher `… - RRPONTSYD * 1000`.

Fällt eine Quelle aus, bleibt das Dashboard funktional — nur die betroffene Karte zeigt
einen klar markierten Fehlerstatus.

---

## ➕ Einen Indikator hinzufügen

**Bestehende Quelle (FRED/stooq/CoinGecko/computed)** — nur ein Manifest-Eintrag, kein Code:

```yaml
- id: us_30y                       # eindeutige ID
  name: "US 30Y Treasury Yield"
  category: rates
  source: fred
  series_id: DGS30                 # series_id (FRED) | symbol (stooq/cg) | formula (computed)
  unit: "%"
  decimals: 2
  direction: neutral               # higher_is_stress | lower_is_stress | higher_is_supportive | neutral
  priority: 0                      # optional: höher = wichtiger (Stern ★, oben in Kategorie, Filter "⭐ Wichtigste")
  display_multiplier: 1.0          # native -> Anzeige-Einheit
  cache_ttl_minutes: 60            # optional (default 60; 1440 für wöchentl./monatl.)
  thresholds:                      # optional; sonst Percentil-Fallback
    elevated: 5.0
    stress: 6.0
  what: "Was misst der Indikator? …"
  why: "Warum bewegt er sich? (mechanistisch) …"
  example: "Historische Einordnung (2008/2020/2022) …"
```

Computed-Beispiel: `source: computed` + `formula: "fred:DGS10 - fred:DGS2"`.
Erlaubt sind `source:ref`-Operanden, Zahlen, `+ - * /`, Klammern sowie die Funktionen
`norm100(…)` (Normierung auf Startwert 100) und `invert(…)`.

**Neue Quelle:** `DataSource`-Protocol in `data_sources/` implementieren, in der
Source-Factory in [`service.py`](src/dashboard/indicators/service.py) registrieren,
Manifest-Eintrag ergänzen.

---

## 🧪 Entwicklung

```powershell
.\tasks.ps1 check      # ruff + mypy --strict + pytest (Coverage)
```

- **Tests:** pytest + respx (HTTP-Mocking), je Quelle ein Happy-Path-Test mit Fixture.
  Aktuell **92 Tests, ~92 % Coverage**.
- **Linting:** ruff (`E,F,I,N,UP,B,SIM,RUF,PL`), **mypy --strict** clean.
- **Pre-commit:** `uv run pre-commit install` aktiviert ruff/mypy/pytest-Hooks.

### Projektstruktur (Auszug)

```
src/dashboard/
├── app.py                 # FastAPI-Factory + Lifespan
├── config.py              # Pydantic Settings (Fail-Fast ohne FRED-Key)
├── charts.py              # Plotly: Sparkline · Detail · Histogramm
├── formatting.py          # Zahlen-/Label-Formatierung (DE)
├── data_sources/          # fred · stooq · coingecko · cftc · cnn · cboe · shiller · naaim · computed · cache
├── indicators/            # models · stats · registry · service · manifest.yaml
├── routes/                # pages · api
├── templates/             # base · dashboard · _grid · _card · indicator
└── static/                # style.css · htmx.min.js
```

---

## 📡 JSON-API

| Endpoint | Beschreibung |
|---|---|
| `GET /api/indicators` | Snapshots aller Indikatoren |
| `GET /api/indicator/{id}` | Einzelner Snapshot |
| `GET /healthz` | Health-Check (für Hoster) |
| `GET /docs` | Interaktive OpenAPI-Doku |

---

## 🌐 Öffentlich deployen (Cloud, 24/7)

Das Projekt ist deploybar: [`Dockerfile`](Dockerfile) (läuft auf jedem Container-Hoster)
plus [`render.yaml`](render.yaml) als Ein-Klick-Blueprint für **Render**.

**Wichtig:** Der `FRED_API_KEY` bleibt serverseitig und wird als **Umgebungsvariable**
beim Hoster gesetzt — niemals committen (`.env` ist via `.gitignore`/`.dockerignore`
ausgeschlossen). Der Port kommt vom Hoster über `$PORT`, der Host bindet auf `0.0.0.0`.

### Weg über Render (empfohlen, Gratis-Tarif)

1. Projekt zu GitHub pushen (einmalig):
   ```powershell
   git add -A
   git commit -m "Investor Dashboard"
   git branch -M main
   git remote add origin https://github.com/<dein-user>/investor-dashboard.git
   git push -u origin main
   ```
2. Auf [render.com](https://render.com) → **New → Blueprint** → dein Repo wählen.
   Render liest `render.yaml` und legt den Docker-Web-Service an.
3. Im Service unter **Environment** den `FRED_API_KEY` eintragen → **Deploy**.
4. Nach ein paar Minuten läuft das Dashboard unter
   `https://investor-dashboard-xyz.onrender.com`.

> **Alternativen:** **Railway** (Repo importieren, erkennt das `Dockerfile` automatisch,
> `FRED_API_KEY` als Variable setzen) oder **Fly.io** (`fly launch` nutzt den Dockerfile,
> `fly secrets set FRED_API_KEY=…`). Beide funktionieren ohne Änderung.

### Lokal mit Docker testen

```powershell
docker build -t investor-dashboard .
docker run -p 8000:8000 -e FRED_API_KEY=dein_key investor-dashboard
```

### Gut zu wissen

- **Cold Start:** Auf Gratis-Tarifen schläft der Dienst bei Inaktivität ein und braucht
  beim ersten Aufruf ~30–60 s (danach plus ~10 s für die Live-Abrufe). Warm ist er schnell.
- **Offen zugänglich:** Wie gewählt ohne Login. Inhaltlich unkritisch (nur öffentliche
  Marktdaten). Ein Passwortschutz lässt sich später additiv ergänzen.
- **Rate-Limits:** Der 60-Minuten-Cache schützt die Gratis-Quellen. Bei *viel* öffentlichem
  Traffic können CoinGecko/stooq trotzdem limitieren — dann degradieren nur einzelne Karten.

---

## ⚠️ Hinweis

Reines Analyse-/Bildungs-Tool. **Keine Anlageberatung**, kein Trading, keine
Gewähr für Datenrichtigkeit oder -verfügbarkeit der externen Quellen.
