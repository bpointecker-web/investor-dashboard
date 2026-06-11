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
  Aktuell **100 Tests, ~92 % Coverage**.
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

## 🌐 Öffentliche Seite (GitHub Pages, gratis — empfohlen)

Das Dashboard ist read-only → es braucht **keinen laufenden Server**. Ein GitHub-Actions-
Workflow ([`.github/workflows/pages.yml`](.github/workflows/pages.yml)) rendert **stündlich**
alle Seiten mit frischen Daten als statisches HTML ([`scripts/build_static.py`](scripts/build_static.py))
und deployt auf **GitHub Pages**:

- **URL:** `https://<user>.github.io/investor-dashboard/` — immer online, kein Cold Start
- **Gratis** (öffentliches Repo nötig), keine Kreditkarte
- Daten maximal ~60 Min alt (= bisherige Cache-TTL); Quellen liefern eh meist nur 1×/Tag
- Vermeidet das Server-Hosting-Problem, dass Gratis-Quellen (stooq) Rechenzentrums-IPs
  blocken: der Yahoo-Fallback greift auf den GitHub-Runnern (lokal verifiziert: 39/39)

### Einmalige Einrichtung (Repo auf GitHub)

1. **Repo public machen:** Settings → General → Danger Zone → *Change visibility*
   (Pages ist im Gratis-Plan nur für öffentliche Repos; der FRED-Key bleibt als Secret geheim).
2. **Secret anlegen:** Settings → Secrets and variables → **Actions** →
   *New repository secret* → Name `FRED_API_KEY`, Wert = dein Key.
3. **Pages aktivieren:** Settings → **Pages** → Source: **GitHub Actions**.

Danach läuft alles automatisch: jeder Push und jede volle Stunde (Minute 17) baut und
veröffentlicht die Site neu. Manuell anstoßen: Actions → *Build & Deploy Pages* → *Run workflow*.

Lokal testen: `uv run python scripts/build_static.py` → Ergebnis in `dist/`.

### Alternative: eigener Server (Docker)

[`Dockerfile`](Dockerfile) + [`render.yaml`](render.yaml) bleiben für Container-Hosting
erhalten (Render/Railway/Fly). **Achtung:** Gratis-Server-Tarife schlafen ein, und
stooq & Co. blocken Rechenzentrums-IPs → einzelne Karten degradieren. Empfohlen nur
mit bezahltem Tarif oder eigener Infrastruktur. `FRED_API_KEY` immer als Env-Variable
setzen, nie committen.

```powershell
docker build -t investor-dashboard .
docker run -p 8000:8000 -e FRED_API_KEY=dein_key investor-dashboard
```

---

## ⚠️ Hinweis

Reines Analyse-/Bildungs-Tool. **Keine Anlageberatung**, kein Trading, keine
Gewähr für Datenrichtigkeit oder -verfügbarkeit der externen Quellen.
