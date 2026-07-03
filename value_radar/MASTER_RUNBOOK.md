# Master Runbook — Value & Inflection Stock Screening
### Motto: **„Vor die Welle kommen"**

> **Disclaimer:** Dieses Runbook ist ein Werkzeug- und Methoden-Framework zur strukturierten Eigenrecherche. Es ist **keine Anlageberatung** und keine Kauf-/Verkaufsempfehlung. Kennzahlen aus kostenlosen Datenquellen können fehlerhaft, verspätet oder unvollständig sein – immer gegen die Originalquelle (10-K/10-Q, Geschäftsbericht) prüfen. „Die nächste Nvidia finden" ist von Natur aus unsicher; Risikomanagement und Positionsgrößen schlagen jede Einzelthese.

---

## 0. Die Grundidee (dein „Edge")

Überrenditen entstehen nicht dadurch, dass eine Firma gut ist, sondern dadurch, dass **die Realität besser ist als die im Kurs eingepreiste Erwartung** – und sich diese Lücke schließt. „Vor die Welle kommen" heißt also:

1. **Strukturelle Nachfragewelle früh erkennen** (Sekulärtrend: KI-Compute, Memory-Zyklus, Stromnetz/Grid, Verteidigung, Energiespeicher, …).
2. **Firmen mit operativem Hebel auf diese Welle** finden, die noch zur *alten* Realität bepreist sind (günstiges Multiple auf normalisierte/zukünftige Gewinne).
3. **Den Katalysator antizipieren**, der das Re-Rating erzwingt (Guidance-Anhebung, Schätzungsrevisionen, Design-Wins, Kapazitätsausbau, Angebots-/Nachfrage-Kippen).
4. **Positionieren, bevor der Revisions-Zyklus senkrecht geht** – nicht am Boden raten, sondern auf die Inflektion reagieren.

Wichtig: Es gibt **zwei verschiedene „Wellen-Typen"**, und sie brauchen unterschiedliche Spielbücher.

---

## 1. Die drei Playbooks

| | **A — Quality Value / Compounder** | **B — Cyclical Value (Micron-Typ)** | **C — Secular Inflection (Nvidia-Typ)** |
|---|---|---|---|
| **Wesen** | Gutes Unternehmen, fair/günstig | Zyklischer Wert, am Tief gekauft | Strukturelles Wachstum mit Margen-Inflektion |
| **Kaufsignal** | ROIC > WACC, günstiges FCF-Yield | Tief im Zyklus: niedriges P/B, hohe/neg. KGV, Capex-Cuts, Lager-Peak | Umsatz-/Margen-Beschleunigung + steigende Schätzungen |
| **Bewertung** | DCF, FCF-Yield | **P/B + mid-cycle EV/EBITDA** (NICHT KGV!) | Forward-Multiple, PEG, DCF mit hohem g1 |
| **Falle** | „billig aus gutem Grund" (Value Trap) | Am Peak kaufen (niedriges KGV = Gefahr!) | Zu spät, wenn Revisionen schon eingepreist |
| **Exit** | Fair Value erreicht | Zyklus-Peak (hohe Margen, Euphorie) | Wachstum verlangsamt / Revisionen drehen |

**Die Micron-Lektion:** Bei Zyklikern ist ein *niedriges* KGV oft ein Verkaufssignal (Gewinne am Peak), ein *hohes/negatives* KGV oft ein Kaufsignal (Gewinne am Boden). Deshalb für Zykliker auf **P/B**, **Lagerbestände**, **Branchen-Capex** und **mid-cycle-Gewinne** schauen, nicht aufs aktuelle KGV.

**Die Nvidia-Lektion:** Bei sekulärem Wachstum sieht das trailing-Multiple *immer* teuer aus. Entscheidend ist die **Beschleunigung** (2. Ableitung des Umsatzes), die **Margenausweitung** und das **Hinterherhinken der Analysten-Schätzungen** hinter der Realität. Frühe Käufer kaufen die Inflektion, nicht den günstigen Preis.

---

## 2. Universum

- **Start:** Liste handelbarer Aktien (z. B. S&P 1500, NASDAQ, STOXX 600, oder thematische Listen rund um deine Wellen).
- **Ausschluss:** Mikro-Caps unter Liquiditätsschwelle (z. B. < 100 Mio. USD MktCap oder < 1 Mio. USD Tagesvolumen), je nach Portfoliogröße.
- **Tipp „vor die Welle":** Definiere 3–6 **Themen-Universen** (z. B. „Power & Grid", „Memory & Semis", „AI-Infra", „Defense") und screene innerhalb. So findest du Inflektionen, bevor der breite Markt sie scannt.

---

## 3. Screening-Parameter

Alle Schwellen sind **Startwerte** und in `config.py` anpassbar. **Branchenrelativ** denken (Semis ≠ Versorger).

### 3.1 Bewertung (günstig genug?)
| Kennzahl | Richtwert | Bemerkung |
|---|---|---|
| EV/EBITDA | < 12 (Quality), < mid-cycle (Zykliker) | kapitalstrukturneutral, besser als KGV |
| EV/Sales | < 4 (kontextabhängig) | für (noch) unprofitable Wachstumswerte |
| P/B | < 3 (Quality), nahe zyklischem Tief (Zykliker) | Schlüsselgröße für Zykliker/Asset-heavy |
| FCF-Yield (FCF/EV) | > 5 % | „echte" Cash-Rendite |
| KGV fwd | < 20 (kontextabh.) | bei Zyklikern **ignorieren** |
| PEG (fwd) | < 1,5 | Growth-at-Reasonable-Price |
| Reverse-DCF impl. Wachstum | < realistisch erreichbar | spürt Fehlbepreisung auf |

### 3.2 Qualität / Burggraben
| Kennzahl | Richtwert |
|---|---|
| ROIC | > 10 % **und** > WACC |
| ROIC-Trend | steigend |
| Bruttomarge & Trend | hoch / **steigend** (frühes Wellen-Signal: Pricing Power, Mix-Shift) |
| Operating Margin | positiv, steigend |
| ROE (DuPont zerlegt) | > 12 %, nicht nur durch Leverage |

### 3.3 Wachstum & Inflektion (die Welle)
| Signal | Worauf achten |
|---|---|
| Umsatz-**Beschleunigung** | 2. Ableitung positiv (g steigt) |
| Schätzungsrevisionen | Aufwärtsrevisionen der fwd-Umsätze/EPS (= frühe Bestätigung) |
| Auftragseingang/Backlog | wachsend (wo verfügbar) |
| Bruttomargen-Inflektion | Kipp-Punkt nach oben |
| Neue Produktzyklen / TAM-Ausweitung | qualitativ |

### 3.4 Finanzielle Gesundheit (Welle überleben)
| Kennzahl | Richtwert |
|---|---|
| Net Debt / EBITDA | < 3 |
| Interest Coverage | > 4× |
| Current Ratio | > 1,2 |
| Altman Z-Score | > 3 (Safe Zone) |
| FCF | positiv oder klarer Pfad dorthin |

### 3.5 Markt-Anerkennung / Momentum (nicht zu früh, nicht zu spät)
| Signal | Logik |
|---|---|
| Relative Stärke 6–12M | bestätigt Trend; für „früh" aber Basenbildung bevorzugen |
| Revisions-Momentum | beste Frühindikation |
| Short Interest | Contrarian / Squeeze-Potenzial |

### 3.6 Value-Trap-Filter (Negativ-Screen)
**Aussortieren**, wenn gleichzeitig zutrifft: fallende Bruttomarge **und** fallender Umsatz **und** steigende Verschuldung. Das ist „billig aus gutem Grund".

---

## 4. Scoring-Matrix

**Prinzip:** Jede Kennzahl wird **branchenrelativ in einen Perzentil-Score 0–100** überführt, pro Kategorie gemittelt, dann gewichtet zum **Composite Score** summiert.

### 4.1 Kategorien & Default-Gewichte

| Kategorie | Quality-Preset | Cyclical-Preset | Inflection-Preset |
|---|---|---|---|
| Bewertung | 25 % | 30 % | 15 % |
| Qualität/Moat | 25 % | 15 % | 20 % |
| Wachstum/Inflektion | 20 % | 15 % | **35 %** |
| Finanz. Gesundheit | 15 % | 20 % | 10 % |
| Momentum/Revisionen | 10 % | 15 % | 15 % |
| Katalysator (Intel) | 5 % | 5 % | 5 % |

→ Du wählst pro Kandidat das passende Preset (Programm: `--preset quality|cyclical|inflection`).

### 4.2 Ablauf
1. Rohwerte je Kennzahl einsammeln.
2. Pro Branche zu Perzentil-Rang (0–100) normalisieren (höher = besser; „je-kleiner-desto-besser"-Kennzahlen invertieren).
3. Kategorie-Score = Mittel der Kennzahlen-Scores.
4. **Composite = Σ (Kategorie-Score × Gewicht)**.
5. **Value-Trap-Penalty** abziehen (z. B. −20 Punkte), falls Negativ-Screen greift.
6. Ranking → Top-N kommen in den Deep Dive.

---

## 5. Bewertungs-Engine (Fair Value / Target / Einstieg)

Mehrere Methoden, dann **gewichteter Blend** je nach Playbook.

### 5.1 Methoden
- **2-Stufen-DCF (FCFF):** FCFF = EBIT·(1−t) + D&A − Capex − ΔNWC. Projektion über n Jahre mit g₁, Terminal Value via Gordon-Growth (g_term) **oder** Exit-Multiple. Abzinsung mit **WACC**. → EV → minus Net Debt → / Aktien = innerer Wert/Aktie.
- **Reverse-DCF:** Welches Wachstum ist im aktuellen Kurs eingepreist? Vergleich mit dem realistisch Machbaren (Fehlbepreisungs-Detektor).
- **Multiple-Basiert:** gerechtfertigtes Forward-Multiple (Peer-Median oder historischer mid-cycle) × Forward-EPS/-EBITDA/-FCF. **Bei Zyklikern: normalisierte (mid-cycle) Gewinne, nicht Peak/Trough.**
- **Graham-Number:** √(22,5 × EPS × BVPS) als Schnell-Check; Graham-Formel V = EPS × (8,5 + 2g).
- **Normalisierte Earnings (Zykliker):** Ø-Marge über den Zyklus × aktuellen Umsatz → mid-cycle-EPS → × normalem Multiple.

### 5.2 Outputs
- **Fair Value (intrinsisch):** Blend der anwendbaren Methoden.
- **12M-Target:** Forward-Fundamentaldaten × Ziel-Multiple (12-Monats-Sicht).
- **Einstiegspreis = Fair Value × (1 − Margin of Safety)**.
  - MoS-Presets: Quality **15–20 %**, Cyclical **30–40 %**, Speculative-Growth **35–50 %**.
  - Technischer Overlay: Einstieg an Support/Basenbildung verfeinern; bei Zyklikern an P/B-Tiefband ankern.

---

## 6. Katalysator- & Intel-Layer (das „Portal")

Ziel: **Frühindikatoren** sehen, bevor sie im Kurs sind.

| Baustein | Quelle (Beispiel) | Frei? |
|---|---|---|
| Unternehmens-News | Finnhub, FMP, Alpha Vantage, Marketaux, yfinance | tw. frei |
| News-**Sentiment** | Alpha Vantage News-Sentiment, Finnhub | freemium |
| Peers / Wettbewerber | FMP, yfinance | frei |
| **Supply Chain (Kunden/Lieferanten)** | Finnhub (Premium), Bloomberg SPLC/FactSet (institutionell), 10-K-Parsing | **schwer / teuer** |
| Earnings-Call-Transcripts | FMP, Finnhub (Premium) | freemium |
| Insider-Transaktionen | SEC Form 4, Finnhub, FMP | tw. frei |
| Schätzungsrevisionen | FMP, Finnhub | freemium |

**Ehrliche Grenze:** Echte Kunden-/Lieferanten-Graphen wie bei Bloomberg (SPLC) sind institutionelle Premiumdaten. Auf Retail-Niveau approximierst du sie über (a) Peers, (b) 10-K-„Kundenkonzentration", (c) Finnhub-Supply-Chain (Premium). Das Programm ist so gebaut, dass es diese Quellen einsteckt, sobald du Keys hast – und sonst sauber degradiert.

**Frühindikatoren-Logik („vor die Welle"):**
- Lieferanten-Kommentare/Capex → Signal für nachgelagerte Nachfrage.
- Upstream-Capex-Wellen → Wer liefert die Schaufeln?
- Preisdaten (Spotpreise z. B. DRAM/NAND) → Zyklus-Timing.
- Aufwärts-Revisionen + Insider-Käufe + Margen-Inflektion **gleichzeitig** = starkes Frühsignal.

---

## 7. Workflow / Kadenz

```
Wöchentlich:   Themen-Universen screenen  →  Scoring  →  Top-N Shortlist
Pro Kandidat:  Deep Dive (10-K, Margen-Trend, Intel/Katalysatoren)
               →  Playbook-Typ bestimmen (A/B/C)
               →  Bewertung: Fair Value, 12M-Target, Einstieg + MoS
               →  Watchlist mit Einstiegs-Triggern (Preis + Katalysator)
Bei Trigger:   Positionsgröße festlegen  →  Einstieg gestaffelt
Laufend:       Revisionen & Intel überwachen  →  These-Check  →  Exit-Regeln
```

---

## 8. Risikomanagement & Exits
- **Positionsgröße:** abhängig von Conviction × inverser Unsicherheit (Cyclical/Speculative kleiner als Quality).
- **Staffeln:** in Tranchen kaufen statt All-in.
- **These-Invalidierung (Hard-Exit):** Margen-Inflektion bleibt aus / Revisionen drehen nach unten / Bilanz verschlechtert sich.
- **Cyclical-Exit:** Euphorie + niedriges KGV bei Peak-Margen.
- **Growth-Exit:** Wachstumsverlangsamung + Multiple-Kompression beginnt.

---

## 9. Daten-Quellen-Leiter

| Stufe | Quellen | Kosten | Kann |
|---|---|---|---|
| **Free** | yfinance, SEC EDGAR | 0 € | Fundamentaldaten, Kurse, Basis-News, 10-K |
| **Freemium** | Finnhub, Alpha Vantage, FMP (Starter) | ~0–50 €/Mo | Revisionen, Sentiment, Transcripts, Insider |
| **Pro** | FMP Pro, Finnhub Premium, Polygon | ~50–200 €/Mo | bessere Supply-Chain, Tiefe |
| **Institutionell** | Bloomberg, FactSet, S&P CapitalIQ | €€€€ | echte SPLC-Supply-Chain (Retail nicht nötig) |

---

## 10. Programm-Bedienung
Siehe `README.md`. Kurz:
```bash
pip install -r requirements.txt
python main.py screen  --universe watchlist.txt --preset inflection
python main.py value   --ticker MU --preset cyclical
python main.py intel   --ticker NVDA
python main.py report  --ticker NVDA --preset inflection
```
