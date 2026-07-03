# Value-Radar — „Vor die Welle kommen"

Ein modulares Python-System zum Screenen, Scoren und Bewerten von (Value-)Aktien
inkl. News-/Katalysator-Layer. Begleitend zum `MASTER_RUNBOOK.md`.

> **Kein Anlageberatungs-Tool.** Eigenrecherche-Werkzeug. Daten aus kostenlosen
> Quellen können fehlerhaft sein – immer gegen Originalquellen prüfen.

## Installation
```bash
cd value_radar
python -m venv .venv && source .venv/bin/activate    # optional
pip install -r requirements.txt
```

## Optionale API-Keys (für reichere Daten)
Ohne Keys läuft alles über **yfinance** (kostenlos). Für News, Peers,
Supply-Chain, Insider, Revisionen:
```bash
export FINNHUB_API_KEY="dein_key"     # finnhub.io (Free-Tier vorhanden)
export FMP_API_KEY="dein_key"         # financialmodelingprep.com
export ALPHAVANTAGE_API_KEY="dein_key"
```

## Befehle
```bash
# Universum screenen + ranken (branchenrelatives Scoring)
python main.py screen --universe watchlist.txt --preset inflection

# Einzeltitel: Scoring
python main.py score --ticker MU --preset cyclical

# Einzeltitel: Bewertung (FairValue / 12M-Target / Einstieg + MoS)
python main.py value --ticker NVDA --preset inflection

# Einzeltitel: Intel (News, Peers, Supply-Chain, Insider, Revisionen)
python main.py intel --ticker NVDA

# Voller Einzelbericht (alles kombiniert) — die Hauptansicht
python main.py report --ticker MU --preset cyclical
```

## Web-Dashboard (Terminal-Look, lokal über localhost)
```bash
pip install -r requirements.txt          # enthält jetzt streamlit
streamlit run dashboard.py               # Standard-Port 8501
streamlit run dashboard.py --server.port 8765   # eigener Port
```
Danach im Browser öffnen: **http://localhost:8501** (bzw. dein Port).
Läuft komplett lokal; nur die Datenabfragen gehen ins Netz (wie im CLI).
Den Standard-Port kannst du dauerhaft in `.streamlit/config.toml` setzen.

Das Dashboard hat zwei Reiter:
- **Einzelanalyse** — Ticker + Playbook wählen → Composite-Score, Fair Value,
  12M-Target, Einstiegspreis, Score-Balken, Kurschart und Intel/News.
- **Screener** — Tickerliste einfügen → branchenrelatives Ranking als Tabelle.

## Presets (Playbooks aus dem Runbook)
- `quality`    — solides Unternehmen, fair/günstig (Compounder)
- `cyclical`   — Micron-Typ: am Zyklustief, P/B + mid-cycle-Multiples
- `inflection` — Nvidia-Typ: Wachstums-/Margen-Beschleunigung

## Anpassen
Alle Schwellen, Gewichte, MoS und Bewertungsannahmen stehen in `config.py`.

## Module
| Datei | Aufgabe |
|---|---|
| `config.py` | Schwellen, Gewichte, Presets, Keys |
| `providers.py` | Datenzugriff (yfinance + optional Finnhub/FMP) |
| `screener.py`-Logik in `main.py` | Filter auf Schwellen |
| `scoring.py` | branchenrelative Perzentil-Scores + Composite + Value-Trap |
| `valuation.py` | DCF, Reverse-DCF, Multiples, Graham → FairValue/Target/Einstieg |
| `intel.py` | News, Peers, Supply-Chain, Insider, Catalyst-Score |
| `main.py` | CLI-Orchestrierung |

## Grenzen (ehrlich)
- **Supply-Chain (echte Kunden/Lieferanten):** institutionelle Premiumdaten
  (Bloomberg SPLC/FactSet). Hier nur Best-Effort über Finnhub-Premium; sonst „n/a".
- News-Sentiment ist eine simple Schlagwort-Heuristik – als Frühindikator-Proxy,
  nicht als Wahrheit.
- yfinance-`.info` ist manchmal lückenhaft; das System degradiert dann sauber.

## Nächste sinnvolle Ausbaustufen
- Echte ROIC-Berechnung aus Bilanz/GuV (statt ROE-Proxy)
- Mehrjährige Margen für saubere mid-cycle-Normalisierung (Zykliker)
- Estimate-Revisions-Momentum (Δ über Zeit) statt Snapshot
- Backtest-Modul für die Scoring-Gewichte
- Optionales Web-Dashboard (Streamlit) statt CLI
