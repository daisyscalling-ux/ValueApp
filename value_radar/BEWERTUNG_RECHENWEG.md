# Ein Rechenweg für Scanner und Einzelanalyse

Stand 13.11.2026. Teil des Vorhabens „Bewertung mit den Daten des Risikoscores“ (`BEWERTUNG_RISIKODATEN.md`). Entscheidung des Nutzers vom 12.11.2026: Die App-Fassung in TypeScript wird der einzige Rechenweg. Am 13.11.2026 hat er entschieden, zuerst die Methode zu vereinheitlichen und danach die Daten.

## Was sich ändert

Der Cloudflare-Export (`export_cf.py`, Workflow precompute-3tage) holt die Daten wie bisher (`providers.get_fundamentals`). Die Bewertungsfelder in `cf_universum.json` kommen jetzt aber aus `scannerFields` → `evaluateStock`, also demselben Code wie die Einzelanalyse.

| Teil | Datei |
|---|---|
| App-Code, identische Kopie aus valueapp-cf | `risk_precompute/src/lib/`: `evaluation.ts`, `valuation.ts`, `scoring.ts`, `lifecycle.ts`, `scores.ts`, `scores_plus.ts`, `currency.ts`, `valuation-data.ts`, `scanner-evaluation.ts` |
| Node-Einstieg | `risk_precompute/scanner-evaluate.ts`, gebaut mit esbuild im Workflow |
| Übergabe und Rückschreiben | `ts_bewertung.py`; `precompute.score_ticker(..., mit_eingabe=True)` hängt die Eingangsdaten an (`_ts_input`, wird wieder entfernt) |

Ersetzte Felder: `composite`, `fair_value`, `upside`, `entry`, `quantum`, `kauf_urteil`, `momentum`, `quality`, `value`, `growth`, `catalyst`, `value_trap`, `vt_warnung`. Neue Felder: `scanner_method`, `playbook`, `lifecycle_phase`, `target_12m`, `fv_confidence`, `fv_reliable`, `valuation_issues`, `health`.

`value` war vorher immer leer: Python las die Kategorie „value“, sie heißt aber „valuation“. Jetzt steht dort der Bewertungsteilscore.

## Übernommene Python-Regeln (jetzt auch in der Einzelanalyse)

| Regel | Vorher | Jetzt |
|---|---|---|
| Analysten-Skepsis | nur Python: Quantum −4, wenn Konsensziel mehr als 20 % unter dem eigenen Fair Value liegt und der Upside über 25 % | in `evaluateStock`, für beide Wege |
| Fallende Kursziele | nur Python (eigene Historie) | Quantum −6, wenn die Pipeline `_analyst_trend` mitliefert; die Einzelanalyse hat diese Historie nicht |
| Angezeigter Upside | Python: bei gedeckeltem Fair Value das geprüfte Analystenziel | `displayUpside`, gleiche Regel |
| Kauf-Urteil | Python, mit Datenqualitätsstufe aus `valuation.datenqualitaet` | `kaufUrteil`: gleiche Schwellen (Upside ≥ 10, Qualität ≥ 55, Composite ≥ 55, keine Value-Trap); „belastbar“ heißt jetzt kein Rückfallwert, und Datenprüfung der App nicht gesperrt; gesperrt → „Daten prüfen“ mit Gründen in `valuation_issues` |

## Kennzeichnung und Ausfall

- Jede neu gerechnete Zeile trägt `scanner_method: ts-evaluate-v1`.
- Fällt der Node-Aufruf aus, bleiben die Python-Werte stehen und werden als `python-v1` gekennzeichnet.
- Zeilen aus früheren Läufen tragen kein Kennzeichen. Der Scanner zeigt an, wie viele Titel noch aus der früheren Rechnung stammen.

## Messung

Grundlage: 1.190 Titel mit identischen Eingängen aus `daten/fundamentals`, Abschluss- und Kurswährung gleich. Verglichen werden die bisherigen Scanner-Werte (Python, main) mit dem neuen Weg.

| Größe | Median | P90 |
|---|---:|---:|
| Composite | 2,3 Punkte | 4,8 |
| Fair Value | 2,4 % | 30,3 % |
| Upside | 2,0 Pp | 27,4 Pp |
| Quantum | 3,0 Punkte | 9,1 |

Kauf-Urteile 65 → 60, „beobachten“ 166 → 134, „meiden“ 959 → 996. Für alte Urteile ist das eine Näherung ohne Datenqualitätsstufe.

Die Phase ist bei 453 Titeln „unknown“, weil die Pipeline-Daten keine Phasenhistorie enthalten. Die Einzelanalyse hat sie aus dem ROIC-Bundle.

## Grenzen

- **Daten:** Die Datenquellen bleiben verschieden (Pipeline: `providers.py`; App: ROIC-Bundle über `/api/bundle`). Prüfungen der App, die die Rohantworten brauchen (Ersatzabschluss, Periodenabgleich, Währung), greifen im Scanner nur teilweise. Die Datenangleichung ist Schritt 2 und eine eigene Entscheidung (Abrufkosten).
- **Python-Teile außerhalb des Scanners:** Streamlit, E-Mail, Screener, Radar und Backtests rechnen weiter mit der Python-Fassung.
- **Kopien:** Die Kopien unter `risk_precompute/src/lib` müssen identisch mit valueapp-cf bleiben (Arbeitsstandard).

## Diagnose gesperrter Bewertungen (13.11.2026)

Sperrt die Datenprüfung der App eine Zeile („Daten prüfen“), schreibt der Export die Rohwerte und ihre Herkunft unter `valuation_check_inputs` mit: Kurs, Währung, Aktienzahl, Börsenwert, Enterprise Value, 52-Wochen-Band, EPS, Quelle, ROIC-Felder, Umrechnungsfaktor, Pence-Normalisierung. Diese Werte fließen in keine Rechnung.

Anlass: Am 13.11.2026 passte bei 52 Titeln der Börsenwert nicht zu Kurs × Aktienzahl (Faktor > 2). Das Universum enthielt die Aktienzahl nicht, die Ursache war ohne neuen Abruf nicht bestimmbar.

## Peers im Composite und im EV/EBITDA-Multiple (13.11.2026)

Erste Risikodaten in der Bewertung. Peers sind dieselbe Auswahl wie im Peer-Vergleich und im Risikoscore (`selectPeers`, bis zu 8 Titel aus `cf_universum.json`). Im Scanner wählt der App-Code sie aus dem kompletten Exportuniversum, frischen und übernommenen Zeilen.

| Regel | Wert | Begründung |
|---|---|---|
| Composite-Kennzahl gegen Peers | Perzentil, wenn mindestens 5 Peers einen gültigen Wert haben (`PEER_PERCENTILE_MIN`), sonst die bisherige feste Skala | Entscheidung des Nutzers. Bei 5 Werten verschiebt ein Peer das Perzentil höchstens um 20 Punkte. |
| Peer-Kennzahlen | EV/EBITDA, KBV, Forward-KGV, Eigenkapitalrendite, Bruttomarge, Umsatzwachstum, Nettoschulden/EBITDA | Diese Felder enthält die Universumszeile (Prozentfelder werden zu Anteilen). Die übrigen 6 Kennzahlen bleiben auf der Skala. |
| Negative Multiples von Peers | zählen nicht | Ein negatives KGV, KBV oder EV/EBITDA ist nicht vergleichbar. |
| EV/EBITDA-Ausgangsmultiple | Mittel aus Peer-Median und Sektortabelle bei mindestens 5 gültigen Peer-Multiples (0–60x), sonst nur Tabelle (`EV_EBITDA_PEER_SHARE = 0,5`) | Entscheidung des Nutzers. Der Peer-Median lag im Median 36 % über der Tabelle (15,5x gegen 12x; Rohstoffe +68 %, Energie +61 %). Das Mittel dämpft, dass ein teurer Markt sich selbst als fair bestätigt. Vorher genügte ein einziger Peer; Peers wurden aber nie übergeben. |
| Szenarien und Bewertungsrisiko | dieselben Peers (`_peer_funds`) | Sonst passt Base nicht zum Fair Value. |

**Kennzeichnung:**
- Scanner-Felder `peer_count`, `composite_peer_metrics` und `ev_ebitda_anchor`.
- Die Einzelanalyse zeigt an der Composite-Kachel, wie viele Kennzahlen gegen wie viele Peers bewertet wurden.
- Beim Fair Value nennt sie den EV/EBITDA-Anker samt Peer-Median und Tabellenwert.

**Messung:** 1.157 Titel mit identischen Eingängen und echtem Universum, ohne gegen mit Peers.
- Mindestens 5 Peers: 1.055 Titel.
- Mindestens eine Kennzahl gegen Peers: 1.053; alle sechs möglichen: 760.
- EV/EBITDA mit Peer-Anteil: 943.

| Größe | Median | P90 | Mittel |
|---|---:|---:|---:|
| Composite | 2 Pkt. | 5 | +0,6 |
| Fair Value | 0,6 % | 10,7 % | +3,2 % |
| Quantum | 1,0 Pkt. | 4,1 | +0,9 |

Kauf-Urteile 58 → 56, „beobachten“ 130 → 156, „meiden“ 969 → 945.

**Verzerrung:**
- Perzentile bewerten relativ zur Peergruppe. In einer teuren Branche wirkt ein Titel, der nur günstiger ist als seine Peers, gut. Das ist gewollt (Vergleich unter Gleichen), heißt aber nicht, dass der Titel absolut günstig ist.
- Der Fair Value steigt im Mittel um 3,2 %. Das kommt vom Peer-Anteil am EV/EBITDA-Multiple; ohne das Mittel aus Peer und Tabelle wären es 4,9 %.
- Die Peers sind nach Branche und Größe ausgewählt, nicht als direkte Wettbewerber geprüft.

**Grenze:** Die Peer-Werte stammen aus dem Export (Pipeline-Daten), die eigenen Werte in der Einzelanalyse aus dem ROIC-Bundle. Die Einheiten sind gleich, die Quellen verschieden (siehe Abschnitt „Grenzen“).

## Messung des Datenwegs (13.11.2026)

Scanner und Einzelanalyse rechnen gleich, holen ihre Daten aber verschieden: die Pipeline über `providers.py`, die App über das ROIC-Bundle.

Workflow `bundle-compare` (nur manuell):
1. Er ruft für eine feste Stichprobe (Standard 50, sortiert nach SHA-256 der Notierung) dasselbe Rohdaten-Bundle ab wie die Einzelanalyse (`worker/bundle-fetch.ts`, Kopie aus valueapp-cf).
2. Er formt es mit `bundleLight` zum Fund und bewertet es mit `scannerFields`, mit denselben Peers, derselben Bilanzprüfung und derselben Verteilung.
3. Er vergleicht Eingänge (Kurs, 52-Wochen-Band, EPS, Kursziel, Wachstum, Eigenkapitalrendite, EV/EBITDA, Börsenwert) und Ergebnisse (Playbook, Composite, Fair Value, Upside, Quantum, 12M-Ziel, Bilanz, Kauf-Urteil) mit den Scanner-Zeilen.

Er schreibt nichts ins Repo; das Ergebnis liegt als Artefakt vor. Abrufe je Lauf bei 50 Titeln: 450 ROIC, 200 Finnhub, 50 FMP. Auf dieser Grundlage entscheidet der Nutzer, ob der Scanner dauerhaft das App-Bundle nutzt.

## Datenbasierte Zyklik in Scanner und Einzelanalyse (13.11.2026)

Befund aus `bundle-compare`: Der Scanner stufte 398 Titel zusätzlich als zyklisch ein, weil ihre Nettomarge über 10 Jahre stark schwankt (`zyklisch_aus_margen`, Variationskoeffizient > 0,40, ROIC-Historie; Flag `_ist_zyklisch`). Die Einzelanalyse kannte das Merkmal nicht. Zyklisch heißt: kein DCF, EV/EBITDA auf 8,5x gedeckelt, Sicherheitsabschlag + 3 Prozentpunkte.

Entscheidung des Nutzers: das Merkmal in beiden Wegen, aber nicht für Finanzwerte und defensive Sektoren.

| Regel | Wert |
|---|---|
| Daten | `cyclicality` je Universumszeile: Methode `margin_cv_v1`, Margenreihe, Variationskoeffizient, Jahre |
| Prüfung beim Lesen (`dataCyclical`, valuation.ts) | Variationskoeffizient aus der Margenreihe nachgerechnet (mindestens 4 Jahre, gespeicherter Wert höchstens 0,01 daneben), Schwelle > 0,40 |
| Ausnahmen | Finanzwerte (Margen ohne Aussage), Versorger, Basiskonsum, Gesundheit (wie die Branchenregel) |
| Altes Flag `_ist_zyklisch` | entscheidet nicht mehr und wird nicht weitergegeben |
| Einzelanalyse | liest `cyclicality` aus der eigenen Universumszeile (`/api/peers`, `universeRow`, nur bei gleicher Notierung oder ISIN) |

**Wirkung** (Universum vom 13.11.2026): Von 398 Titeln, die nur über das Merkmal zyklisch waren, bleiben 208 zyklisch, jetzt auch in der Einzelanalyse. 190 entfallen: Finanzwerte 96, Gesundheit 43, Versorger 31, Basiskonsum 20. Diese laufen im Finanz-Playbook bzw. „quality“.

**Verzerrung:** Das zyklische Playbook bewertet vorsichtiger. Der Wegfall bei Finanzwerten und defensiven Sektoren hebt deren Fair Values tendenziell an. Dort ist eine schwankende Nettomarge aber meist keine Konjunkturzyklik (Rückstellungen, Sondereffekte).

## Historie im DCF: mehrjährige Cash-Conversion (13.11.2026)

Der DCF normalisiert den freien Cashflow als Jahresüberschuss × Cash-Conversion (`fcfBasis`). Die Conversion wurde bisher nie gesetzt; der DCF rechnete deshalb immer mit dem gemeldeten FCF eines Jahres.

| Regel | Wert | Begründung |
|---|---|---|
| Formel | Σ (operativer Cashflow − Investitionen) / Σ Jahresüberschuss über 3–5 aufeinanderfolgende Geschäftsjahre (`sum_fcf_over_sum_net_income_v1`) | Entscheidung des Nutzers. Robust gegen einzelne Ausreißerjahre. |
| Quelle | geprüfte ROIC-Historie (`cf_roic_history.json`), dieselben Jahre wie im Finanzverlauf: Notierungsidentität, ROIC-Quelle, Abruf ≤ 45 Tage, keine doppelten Jahre | Herkunft und Identität wie im Risikoscore |
| Bedingungen | eine Währung; Abstand der Jahre 300–430 Tage; letztes Jahr ≤ 550 Tage; Gewinnsumme > 0 | sonst offen mit Grund |
| Obergrenze | 1,5, gekennzeichnet (`clamped`) | vorsichtig: höhere Werte meist durch Sondereffekte |
| Untergrenze | keine | Entscheidung des Nutzers. Eine Untergrenze von 0,3 hätte 90 investitionsstarke Unternehmen beschönigt. |
| Summe FCF ≤ 0 | DCF offen, kein Rückfall auf ein Einzeljahr | Ein einzelnes besseres Jahr würde dauerhaft negativen freien Cashflow verdecken. |
| Profile | alle (Entscheidung des Nutzers) | Das Finanz-Playbook nutzt den DCF nicht; bei Banken streut der Wert stark (Kundengelder im operativen Cashflow). |

**Ablauf:**
1. `export-history-backfill.ts` rechnet die Conversion (`cash-conversion.ts`, identisch mit valueapp-cf).
2. `financial_history.py` legt sie unter `balance.cashConversion` in die Risikoabdeckung.
3. App und Scanner prüfen beim Lesen erneut (`verifiedCashConversion`): Methode, Jahre, Abstände, Alter, Summen und Begrenzung werden nachgerechnet.

Der Scanner liest sie aus `cf_risk_coverage.json` (`ts_bewertung.risikodaten`) und exportiert `cash_conversion` und `cash_conversion_source`. Die Einzelanalyse lädt `/api/risk-coverage` höchstens 4 s lang und nennt die DCF-Basis oder den Grund, warum der DCF offen ist.

**Messung:**
- Probelauf der Risikokette: 924 von 1.340 Notierungen mit Conversion (Unternehmen 768, Banken 62, Versicherer 34, Spezialfinanzierer 60).
- Offen 416: weniger als 3 geprüfte Jahre 301, Gewinnsumme ≤ 0 50, letztes Jahr zu alt 45, Jahre nicht aufeinanderfolgend 13, keine Historie 7.
- Unternehmen: Median 1,00, P10 0,20, P90 2,00; bei 143 greift die Obergrenze, bei 55 bleibt der DCF offen.

Wirkung im Scanner (1.157 Vergleichstitel, mit Peers):
- Fair Value geändert bei 355 Titeln (nur wo der DCF im Methodenkern liegt): Median 9,2 %, P90 32,1 %, im Mittel über alle 0,0 %.
- Quantum geändert bei 326: Median 3,0 Punkte.
- Kauf-Urteile 56 → 58, „beobachten“ 156 → 145, „meiden“ 945 → 954.

**Verzerrung:** Keine systematische Richtung (Mittel 0,0 %). Die Conversion normalisiert nur das Verhältnis von Cashflow zu Gewinn, nicht den Gewinn selbst. In einem Gewinnhochjahr bleibt die DCF-Basis hoch.

## Bilanz-Kategorie aus den geprüften Finanzkennzahlen (13.11.2026)

Entscheidung des Nutzers: alle Profile, als Rang im Profil.

| Regel | Wert | Begründung |
|---|---|---|
| Rohwert | 100 − gewichtetes Mittel der Kennzahlen im Block „Finanzielle Verwundbarkeit“ des Risikoscores (`financial-health.ts` → `riskConstruct`) | gleiche Skalen, Profile, Profilkorrekturen und Prüfungen wie im Risikoscore; der Gesamt-Risikoscore fließt nicht ein |
| Kennzahlen je Profil | Unternehmen: Nettoschulden/EBITDA, FCFF-Marge. Banken: CET1-Puffer, LCR, Kreditqualität. Versicherer: Solvenzquote. Spezialfinanzierer: Nettofinanzschulden/EK, Eigenkapitalrendite | |
| Bilanz im Composite | Rang (Perzentil) des Rohwerts unter allen Titeln desselben Profils im Universum, ab 20 Titeln (`HEALTH_RANK_MIN`) | Die Risikoskalen markieren nur Auffälligkeiten (Rohwert-Median Unternehmen 82, Finanzwerte 90). Absolut übernommen hätten sie den Composite im Mittel um 4,9 Punkte gehoben (Kauf-Urteile 58 → 84). |
| Ohne geprüfte Kennzahl oder ohne Verteilung | bisherige Bilanzrechnung, gekennzeichnet (`health_source`: `kennzahlen` bzw. `kennzahlen_ohne_rang`) | nie die absolute Skala |

**Daten:**
- Unternehmen: `risk_financial` aus derselben ROIC-Enterprise-Value-Zeile wie in der App (`roic.risk_financial`, Spiegel von `financialRiskInput`, kein zusätzlicher Abruf).
- Finanzwerte: die Bilanzprüfung der Risikopipeline (`cf_risk_coverage.json`, `ts_bewertung.risikodaten`).

**Verteilung:**
- Scanner: zwei Durchgänge in `scanner-evaluate.ts`. Zuerst die Rohwerte aller frisch gerechneten Titel, ergänzt um übernommene Zeilen aus dem App-Rechenweg; dann der Rang.
- Export: `health_raw` und `health_profile`.
- App: dieselbe Verteilung aus dem Universum (`/api/health-distribution`).

**Messung** (1.157 Vergleichstitel; `risk_financial` hier genähert aus dem Jahresabschluss in `daten/fundamentals`, im Lauf aus ROIC):
- Rang bei 1.047 Titeln (Unternehmen 916, Banken 75, Spezialfinanzierer 56).
- Ohne Rang 16: Versicherer, weil im Profil nur 16 geprüfte Werte vorliegen. Bisherige Rechnung bei 94.
- Bilanz-Median 42 → 52 (P10 8 → 9, P90 55 → 90).
- Composite: Abweichung Median 2 Punkte, Mittel +1,3.
- Kauf-Urteile 58 → 72, „beobachten“ 145 → 150, „meiden“ 954 → 935.

**Verzerrung:** Die verbleibende Anhebung kommt daher, dass die alte Bilanz nach unten verzerrt war: Median 42, weil feste Ersatzskalen und ein fehlender Liquiditätsgrad 50 bzw. niedrige Werte ergaben. Der Rang ist per Konstruktion mittig. Er bewertet relativ zum Profil; ein schwach finanziertes Profil insgesamt erscheint dadurch nicht schlechter.

## Gleichlauf der App-Kopien (13.11.2026)

`risk_precompute/app-copies.json` listet die 36 Kopien aus valueapp-cf mit SHA-256 des App-Originals.

**Prüfung:**
- Pipeline: `app_copies.py` / `test_app_copies.py`, in daily-risk über die Testsuite und in precompute-3tage als eigener Schritt.
- App: `npm run check-copies` gegen dieselbe öffentliche Liste.

**Erlaubte Abweichung:** nur die Importpfade in `worker/risk-benchmark.ts` (`normalize`).

**Abgleich nach einer App-Änderung:** `python value_radar/risk_precompute/app_copies.py abgleichen <pfad-zu-valueapp-cf>`.

**Bestand 13.11.2026:**
- 36 Kopien identisch.
- `insurer-solvency.ts` (Wurzel) wich nur in einem Kommentar ab und ist jetzt identisch.
- Die App-Ordner `risk-export/` und `fundamental-export/` sind alte Schnappschüsse von Pipeline-Dateien und keine App-Kopien; sie stehen nicht in der Liste.

## Börsenwert = Kurs × Aktienzahl, Prüfung gegen den Jahresabschluss (13.11.2026)

**Anlass:** 51 Titel standen auf „Daten prüfen“. Ursache war jedes Mal der Börsenwert. Der ROIC-Wert stammt aus der Enterprise-Value-Zeile zum Berichtsstichtag. Bei starken Kursbewegungen ist er veraltet: Micron 130 Mrd. gegen 873 Mrd. USD. Bei nordischen Werten ist er in USD angegeben, die Notierung in NOK/SEK/DKK (Verhältnis um 0,1).

**Methode (Entscheidung des Nutzers):** Börsenwert = Kurs × Aktienzahl, markiert `market_cap_source: kurs_x_aktien`. Der Anbieterwert bleibt als `market_cap_provider` mit Stichtag und Währung erhalten. `normalizeMarketCap` und `valuationDataCheck` (valuation-data.ts) prüfen die Aktienzahl in dieser Reihenfolge:

| Stufe | Vergleich | Bedingung | Abweichung > Faktor 2 |
|---|---|---|---|
| 1 | Anbieter-Börsenwert | Stichtag ≤ 120 Tage (`MCAP_PROVIDER_MAX_AGE_DAYS`), gleiche Währung | sperrt |
| 2 | Aktienzahl im Jahresabschluss (`weighted_shares`) | Abschluss ≤ 550 Tage (`ANNUAL_SHARES_MAX_AGE_DAYS`), gleiche Währung (GBP = GBp) oder geprüfte Aktienbasis (`share_basis`, ADR-Verhältnis) | sperrt |
| 3 | älterer Anbieter-Börsenwert | kein Jahresabschluss | sperrt (nur Größenordnung, siehe Nachtrag 14.11.) |
| 4 | kein Vergleichswert | – | nur Warnung „Aktienzahl nicht gegengeprüft“ |

**Datenweg:**
- `ts_bewertung.ersatzdaten` liest `daten/fundamentals/<listing_symbol>.json`, dieselbe Datei wie die App.
- Die Datei gilt nur, wenn `symbol == listing_symbol`.
- Übergeben werden nur die Aktienzahl, Stichtag, Währungen und `share_basis`.
- Die App prüft Symbol (`_supplement_symbol`), Alter und Basis erneut. Ohne `_supplement_symbol` verwirft sie die Datei.
- `market_cap` und `market_cap_source` kommen aus dem App-Rechenweg in die Universumszeile.

**Messung (Stand: Universum 13.11.2026, 1.340 Titel):**
- 1.292 Titel haben eine Jahresaktienzahl, die prüfbar ist:
  - 1.141 in gleicher Währung,
  - 79 GBP/GBp,
  - 67 Stammaktien mit Basis,
  - 5 ADR mit geprüftem Verhältnis.
- Offen bleiben 48 Titel:
  - 30 ohne `weighted_shares`,
  - 17 ohne Datei,
  - 1 mit abweichender Berichtswährung ohne Basis (PDD).
- Von den 51 gesperrten Titeln hat bei 50 die ROIC-Aktienzahl dieselbe Größe wie der Jahresabschluss (Faktor 0,94–1,16). Sie werden frei, sobald ihr Anbieterwert älter als 120 Tage ist oder eine andere Währung hat. Das genaue Alter steht nur im Lauf; die Zahl folgt nach dem nächsten precompute.
- PDD bleibt gesperrt (Stufe 3: Anbieterwert Faktor 10, kein Jahresabschluss in USD).

**Nebenbefund Einzelanalyse:** Die App übernimmt bei frischen Ersatzdaten die Yahoo-Aktienzahl. Gegen den Jahresabschluss liegen 23 von 1.291 außerhalb Faktor 2:
- Mehrfach-Gattungen: GOOG 0,46, GOOGL 0,48, VOW3 0,41, HEN3 0,37, MAERSK_B 0,32, NWS 0,32, SCHP, LISP, UHR.
- ADR in Stammaktien gezählt: VOD 9,6, WPP 5,0.
- Offensichtliche Anbieterfehler: MCD, TSE:8015.

Bisher ging das still in den Börsenwert ein, weil der Börsenwert aus derselben Aktienzahl gerechnet wurde. Jetzt sperrt Stufe 2.

**Verzerrung und Grenzen:**
- Faktor 2 erkennt Fehler in der Größenordnung, nicht eine Gattung mit 60 % Anteil. Solche Börsenwerte bleiben bis 40 % zu niedrig, und das EV/EBITDA wirkt dann günstiger.
- `weighted_shares` ist der Jahresdurchschnitt verwässert. Rückkäufe oder Kapitalerhöhungen danach verschieben das Verhältnis, Faktor 2 lässt dafür Raum.
- Ein veralteter Anbieterwert sperrt nicht mehr, wenn der Jahresabschluss die Aktienzahl bestätigt. Das bevorzugt keine Firmengruppe: Es betrifft Titel mit starker Kursbewegung seit dem Stichtag in beide Richtungen (Verhältnis 0,05–4,5).

### Nachtrag nach dem Lauf (14.11.2026)

**Ergebnis precompute 14.11.:**
- „Daten prüfen“ 51 → 19.
- 50 Titel sind frei geworden, wie im Probelauf gemessen.
- 18 Titel sind neu gesperrt, PDD bleibt gesperrt.
- 1.339 von 1.340 Zeilen tragen `kurs_x_aktien`.
- Börsenwert neu/alt: Median 1,10; 109 Titel über ×1,5, 61 unter ×0,67.
- Urteile ohne Sperrwechsel: 6 Änderungen.

**Die 18 neuen Sperren:**

| Ursache | Titel | Bewertung |
|---|---|---|
| Aktienzahl einer Gattung statt aller Aktien | HEN3 0,37, VOW3 0,41, TKO 0,40, CVNA 3,17, TIT 3,55 | richtig gesperrt |
| Aktienzahl des Anbieters fraglich | DD 0,33, HON 0,49 | richtig gesperrt, Ursache offen |
| Fehler in der Jahresaktienzahl (Einheit) | MCD (716,4 statt 716 Mio.), TSE:8015 (Tausend), SYENS (×10) | gesperrt, Vergleichswert falsch; offen statt falsch |
| ADR-Einheit (eigener Fehler, siehe `fundamental_export/ADR_BASIS.md`) | VOD, WPP | behoben: Abschluss je ADR |
| Währungskennung | EXPN, GALD, NOVN, PAF, PRX, ZEG | behoben, siehe unten |

**Währungskennung:** `risk_financial.currency` ist die Berichtswährung der ROIC-Zeile, nicht sicher die Währung des Börsenwerts. Bei Experian oder Novartis steht USD, der Wert passt aber zur Notierung (Verhältnis 1,03–1,26). Stufe 3 prüft deshalb nur die Größenordnung (Faktor 2) und nennt die abweichende Kennung als Warnung. Nordic-Werte in USD (Verhältnis um 0,1) sperren ohne Jahresabschluss weiter.

**Grenze:** Liegt der Wechselkurs nahe 1 (USD, EUR, CHF), erkennt Faktor 2 eine falsche Währung nicht.

**Erwartung nach dieser Korrektur:** 19 − 8 = 11 Sperren (VOD und WPP nach dem nächsten fundamentals-daily-Lauf).

## Geprüfte Prognose-EPS (14.11.2026)

**Anlass:**
- Bisher kam `eps_forward` im Scanner aus Yahoos `forwardEps` (gegen eine Trendfortschreibung geblendet). In der Einzelanalyse kam es aus Finnhub `epsForward` oder aus einer mechanischen Fortschreibung.
- Keiner dieser Werte hatte einen ausgewiesenen Horizont. `forwardEps` ist meist das **nächste** Geschäftsjahr (+1y). Bei japanischen Titeln ist es ein unklarer Wert (8053: 443 statt 149 laut Konsenstabelle).
- Die App hatte bei 43 von 49 verglichenen Titeln gar keine Prognose. Das war der Haupttreiber der Fair-Value-Lücke.

**Methode (Entscheidung des Nutzers):** 12-Monats-Mix aus laufendem (0y) und nächstem Geschäftsjahr (+1y), gewichtet nach der Restlaufzeit des laufenden Jahres. Bei Dezember-Abschluss sind das am 14.11. 13 % 0y und 87 % +1y. Gerechnet und geprüft wird nur in der App (`applyForwardEstimate`, fundamental-supplement.ts). Die Pipeline liefert die Rohdaten (`consensus_estimates`, export_fundamentals.py, Methode `consensus_0y_1y_v1`): Mittelwert, Spanne, Analystenzahl und Geschäftsjahresende je Jahr, Währung, Quelle und Abrufzeit.

| Regel | Konstante | sonst offen mit Grund |
|---|---|---|
| Datei gehört zur Notierung | – | „Keine Konsensschätzung für diese Notierung“ |
| Abruf ≤ 7 Tage | `ESTIMATE_MAX_AGE_DAYS` | „veraltet“ |
| ≥ 3 Analysten je Jahr | `FORWARD_MIN_ANALYSTS` | „Weniger als 3 Analysten“ |
| laufendes Jahr nicht abgelaufen | – | „Konsens noch nicht fortgeschrieben“ |
| Währung gleich, GBP/GBp oder EZB-Kurs ≤ 7 Tage; ADR mit Verhältnis ≠ 1 offen | – | Währungs- bzw. ADR-Grund |
| ≤ Faktor 2 zum berichteten EPS, beide > 0 | `FORWARD_MAX_FACTOR` | „bereinigte Gewinnbasis oder Sondereffekt“ |

**Weitere Änderungen:**
- Ungeprüfte Anbieterwerte und die mechanische Fortschreibung als Prognose entfallen in beiden Wegen.
- Das 12M-Kursziel behält seine gekennzeichnete Ersatzrechnung („Realisierter Gewinn x Wachstum (kein Konsens)“).
- Die Peers nutzen das Forward-KGV nur aus Zeilen mit `eps_forward_method: consensus_ntm_blend_v1`. Im ersten Lauf nach dem Merge hat keine Peer-Zeile diese Kennung; erst der zweite Lauf füllt das Forward-KGV der Peers.
- `eps_forward`, `eps_forward_method`, `eps_forward_source` und `eps_forward_status` gehen in die Universumszeile. Die Einzelanalyse zeigt den Grund unter „Forward-Gewinn offen“.

**Verzerrung:**
- Konsensschätzungen sind oft bereinigt (ohne Aktienvergütung, Sondereffekte). Die Grenze gegen das berichtete EPS verhindert, dass stark bereinigende Firmen im Forward-KGV zu billig wirken.
- Sie lässt aber auch echte Gewinnsprünge offen, etwa Wachstum über ×2 nach einem schwachen Jahr. Das trifft eher Wachstumswerte (ARM, ServiceNow) und Zykliker im Aufschwung (Micron: 12-Monats-Konsens etwa ×2,7 zum Vorjahr). Sie verlieren dann die Forward-Methoden, statt optimistisch bewertet zu werden.

**Messung (Stichprobe, 30 zufällige Titel des Universums, Abruf 14.11.):**
- 21 geprüft, 3 mit unter 3 Analysten (INVH, PLD, GPW:MIL), 6 über Faktor 2 (ASM, EDPR, ARM, ANET, NOW, NOD).
- Abweichung zum bisherigen Scannerwert (alle 21 geprüften):
  - Median −1 %;
  - große Fehler im alten Wert: VOE alt 1,43 / neu 4,37; TSE:8053 alt 285 / neu 146; TSE:8331 alt 116 / neu 196; DAL alt 10,13 / neu 7,04.
- Hochgerechnet auf das Universum: etwa 70 % mit geprüfter Prognose. Die genaue Zahl folgt nach fundamentals-daily und precompute.

**Nebenbefund (offen, nicht Teil dieser Änderung):** Nordische Zeilen mit USD-Bericht führen das ROIC-EPS in USD bei NOK/SEK-Kurs. OSL:NOD: EPS 0,085, KGV 2.124. Die neue Prüfung lässt die Prognose dort offen, das Trailing-KGV bleibt aber falsch. Umfang und Behebung sind ein eigenes Thema.

## Berichtswährung → Handelswährung mit EZB-Kurs (15.11.2026)

**Befund (Messung 15.11., 1.340 Titel):**
- Bei 75 Titeln weicht die Berichtswährung (Jahresabschluss der Ergänzungsdatei) von der Handelswährung ab. ADRs sind nicht mitgezählt; für sie gibt es eine eigene Prüfung.
- Bei 66 davon führt die Scanner-Zeile das EPS unumgerechnet in der Berichtswährung: Verhältnis Zeile/Abschluss 1,0 statt des Wechselkurses. 8 Titel sind nicht messbar, 1 ist unklar (ROCK_B).
- Ursache: `providers.py` rechnete nur über das Verhältnis zweier Kurse um, ohne Kennzeichnung und nur bei Faktor 0,2–5. ROIC notiert diese Titel meist in Handelswährung, deshalb ist das Kursverhältnis ≈ 1 und es wurde nichts umgerechnet.

Folge:
- 20 nordische Titel liegen um Faktor 7–11 daneben (Equinor, Mærsk, Vestas …).
- 53 Titel liegen um 5–30 % daneben; bei London-Titeln mit USD-Bericht ist der Fair Value etwa 32 % zu hoch.
- Darunter waren 14 Kaufurteile (Prudential, Wise, Fresnillo, Novartis, Temenos …).
- Die Einzelanalyse sperrte solche Titel („Berichtswährung und Handelswährung unterscheiden sich“), der Scanner prüfte das nicht.

**Methode (Entscheidung des Nutzers):** `convertReportCurrency` (valuation-data.ts) in beiden Wegen.
- Die Berichtswährung ist `risk_financial.currency`, also dieselbe ROIC-Zeile wie die Beträge.
- Umgerechnet wird mit dem EZB-Referenzkurs der Ergänzungsdatei (≤ 7 Tage, `REPORT_FX_MAX_AGE_DAYS`). Bei Pence-Notierung zusätzlich ×100.
- Umgerechnet werden alle Beträge und Je-Aktie-Werte. KGV, KBV und EV/EBITDA werden aus den umgerechneten Werten neu gebildet.
- Kennzeichnung: `report_fx` und der Hinweis „Abschluss in USD, umgerechnet in GBP zum EZB-Referenzkurs vom …“ unter den Datenhinweisen.
- Ohne gültigen Kurs bleibt die Bewertung gesperrt, mit Grund.
- Ein bereits umgerechneter Jahresblock der Ergänzungsdatei wird nicht noch einmal umgerechnet.
- Weicht in der Einzelanalyse die Währung des Gewinnberichts von der Finanzzeile ab, sperrt das („Berichtswährung uneinheitlich“).
- Die Pipeline rechnet nicht mehr um; das Kursverhältnis bleibt nur als Diagnose (`_roic_kursverhaeltnis`). Der Scanner prüft jetzt auf dem bewerteten Fund, also wie die App.

**Grenzen:**
- Der Kurs ist der des letzten EZB-Tages, nicht der des Berichtsstichtags. Für Bewertungen gegen den heutigen Kurs ist das richtig.
- Die historischen Reihen (Margen, Wachstum) sind einheitenlos und bleiben unberührt.
- Die Python-Bewertung (Streamlit, E-Mail) liest die Beträge jetzt unumgerechnet. Sie steht auf der Liste der noch umzustellenden Verbraucher.
- ~~48 Ergänzungsdateien haben einen EZB-Kurs vom 22.10.~~ Korrektur 15.11.: Die 80 Dateien mit altem Kurs gehören zu keinem Titel im Universum; es ist kein Titel betroffen.

**Erwartung:**
- Die 66 gemessenen Titel bekommen umgerechnete Werte.
- Fair Value bei London-USD-Berichtern etwa −24 % (Faktor 0,756), bei Nordics Größenordnung korrigiert.
- Ein Teil der 14 Kaufurteile fällt weg.
- Die genaue Wirkung zeigt der nächste precompute.

### Nachtrag nach dem Lauf (15.11.2026, 17:20 UTC)

**Ergebnis:**
- „Daten prüfen“ 11 → 13: neu gesperrt sind BGEO und TBCG. Ihr Abschluss ist in GEL, und dafür veröffentlicht die EZB keinen Referenzkurs; die Bewertung bleibt dauerhaft offen.
- Urteile: kauf 107 → 105, beobachten 265 → 254, meiden 957 → 968.
- Die 75 Titel mit abweichender Berichtswährung (ohne ADR): Fair Value im Median −7,9 %.
- Die London-USD-Berichter fallen um etwa 21 % (Faktor 0,756).
- Die Nordics steigen um Faktor 3–5, z. B. Equinor 148 → 709 NOK: Mit umgerechnetem EBITDA wirkt Öl im EV/EBITDA günstig.

| Gruppe | Anzahl |
|---|---|
| von 14 Kaufurteilen weiter kauf | 9 |
| davon jetzt beobachten (EXPN, FRES, TEMN) | 3 |
| davon jetzt meiden (NOVN, NSIS_B) | 2 |
| neu kauf (u. a. STO:EVO) | 2 |

- Auch ADRs sind betroffen, die nicht in der Liste standen. ASML (Abschluss EUR, Notierung USD): Fair Value +10 %. GSK: 48,7 → 61,7 USD, jetzt kauf; das EPS je ADR in GBP wird nun in USD umgerechnet.

**Lücke, mit dieser Änderung behoben:** Die angezeigten Kennzahlen der Zeile kamen weiter aus der Python-Seite und waren unumgerechnet (Equinor: EPS 1,94 USD bei KGV 209,6, KBV 25). Die Peers anderer Titel lesen diese Felder.
- Neu übernimmt die Zeile aus dem App-Rechenweg `eps_trailing`, `book_value_ps`, `pe`, `pb` und `ev_ebitda`, sobald umgerechnet wurde.
- Dazu kommen `report_fx` (Kennzeichnung) und `report_fx_status` (Grund, wenn offen).
- Wirkt ab dem nächsten precompute; die Peer-Kennzahlen stimmen danach für alle Titel.

## Aktiengattungen, Splits und Einheitenfehler bei der Aktienzahl (15.11.2026)

**Befund:** 7 der 11 Sperren aus dem Lauf vom 14.11. haben ihre Ursache in der Aktienzahl.

| Titel | Zeile | Jahresabschluss | Ursache |
|---|---|---|---|
| HEN3, VOW3, TKO | nur diese Gattung (151 / 206 / 78 Mio.) | alle Gattungen (414 / 501 / 194 Mio.) | mehrere Gattungen |
| CVNA | 711 Mio. | 224 Mio. (nur Klasse A) | 5:1-Split am 08.05.2026 |
| DD | 136 Mio. | 419 Mio. | 1:3-Zusammenlegung am 24.06.2026 |
| HON | 318 Mio. | 643 Mio. | nur Abspaltungsfaktoren (1,061; 0,9535), keine Erklärung |
| TIT | 7,55 Mrd. | 2,13 Mrd. (Yahoo, bereits bereinigt) | Zeile falsch |

Bei 3 weiteren Titeln stimmt die Aktie, aber der Vergleichswert hat einen Einheitenfehler der Quelle: MCD 716,4 (Mio. statt Stück), TSE:8015 (Tausend), SYENS (×10).

**Methode (Entscheidungen des Nutzers):**
1. **Alle Gattungen, gekennzeichnet.**
   - Liegt die Gesamtzahl aller Gattungen (Yahoo `impliedSharesOutstanding`) mehr als 15 % über der Zahl der notierten Gattung und passt sie zum Jahresabschluss (± 15 %, mit oder ohne Split-Bereinigung), gilt sie als Aktienzahl.
   - Der Börsenwert ist dann Kurs dieser Gattung × alle Aktien (`share_count_basis: alle_gattungen`). Der Hinweis nennt beide Zahlen.
   - Ein Anbieter-Börsenwert, der nur die Gattung abbildet, sperrt dann nicht.
2. **Split-Bereinigung.** Die Jahresaktienzahl wird um belegte Standard-Splits nach dem Stichtag bereinigt (1:20 bis 20:1, Export `splits`). Abspaltungsfaktoren zählen nicht. Die Prüfung gilt als bestanden, wenn die Zahl mit oder ohne Bereinigung passt, weil Yahoo Abschlüsse teils rückwirkend bereinigt.
3. **Einheitenfehler.** Weicht die Jahresaktienzahl um eine Zehnerpotenz ab (± 3 %, seit 16.11. ± 15 %, 10^1 bis 10^6), wird sie als Vergleich verworfen, mit Hinweis. Dann prüft der Börsenwert des Anbieters (Größenordnung).

**Verzerrung und Grenzen:**
- Kursunterschiede zwischen den Gattungen gehen nicht ein (VW Stamm/Vorzug etwa 5–15 %). Der Börsenwert ist eine Näherung zum Kurs der notierten Gattung.
- Bei Up-C-Strukturen (Carvana) zählen Abschluss und Zeile nur Klasse A. Es wird dann nicht umgestellt, das EPS bezieht sich auf das Klasse-A-Ergebnis.
- Honeywell, Telecom Italia und PDD bleiben gesperrt, mit Grund.

**Erwartung:**
- Nach fundamentals-daily (liefert `splits` und `implied_shares_out`) und precompute werden 8 Titel frei: HEN3, VOW3, TKO, CVNA, DD, MCD, 8015, SYENS.
- Gesperrt bleiben 5: HON, TIT, PDD, BGEO, TBCG.
- MCD, 8015 und SYENS werden schon ohne neue Exportdaten frei.

## Cash-Conversion: ROIC-Investitionen und Ersatz aus Yahoo (16.11.2026)

**Befund:** 414 Titel ohne Cash-Conversion, davon 301 mit „weniger als drei geprüfte Geschäftsjahre“ (200 US, 101 nicht-US). Ursache: In 20 % aller ROIC-Jahresabschlüsse fehlen die Investitionen, z. B. ADM 2021–2025, Micron, OMC.

**Fehler im eigenen Code:** `roic_risk_annual.py` verlangte ohne `cf_cap_expenditures` beide Bestandteile, also Sachanlagen- **und** Immaterialienkäufe. Fehlt die Zeile für immaterielle Werte, gingen die ganzen Investitionen verloren.

**Entscheidungen des Nutzers:**
1. **Sachanlagenkäufe allein reichen**, wenn die Zeile für immaterielle Werte fehlt. Kennzeichnung `derivation: ppe_only_intangibles_not_reported`. Positive Werte bleiben offen. Wirkt ab dem nächsten ROIC-Historienlauf.
2. **Ersatzquelle Yahoo**, wenn ROIC keine gültige Conversion liefert:
   - `export_fundamentals.yahoo_cash_history` schreibt bis zu 5 Geschäftsjahre mit operativem Cashflow, Investitionen und Jahresüberschuss desselben Datums in die Ergänzungsdatei (`cash_history`, Methode `yahoo_annual_cash_history_v1`).
   - Investitionen: gemeldete Summe, sonst Sachanlagen + Immaterielle, nie der Netto-Investitions-Cashflow.
   - Die App rechnet mit derselben Methode und denselben Prüfungen: 3–5 aufeinanderfolgende Jahre, eine Währung, ≤ 550 Tage, Deckel 1,5 (`cashConversionFromSupplement`, cash-conversion.ts).
   - ROIC hat Vorrang. Der Ersatz ist gekennzeichnet (`cash_conversion_origin: yahoo_annual_history`, Text „Yahoo-Jahresabschlüsse, Ersatz für fehlende ROIC-Historie“).

**Stichprobe** (30 von 301, Yahoo-Abruf 16.11.):
- 24 Titel mit mindestens 3 Jahren; hochgerechnet etwa 240 Titel.
- Ohne Investitionen auch bei Yahoo: REITs (BBOX, REG), Versicherer/Banken (CB, USB), TUB, TEF.

Die genaue Zahl zeigt der Lauf nach fundamentals-daily.

**Grenze:** Yahoo-Abschlüsse sind standardisiert und nicht zeitpunktgenau. Der Ersatz ist deshalb gekennzeichnet und überschreibt nie eine gültige ROIC-Conversion.

## Micron: Fair Value 1.119 → 622 in der Einzelanalyse (Prüfung 16.11.2026)

**Ursache:** Seit dem Deploy übernimmt die Einzelanalyse die Zyklik aus der Universumszeile. Micron gilt dort als zyklisch: Nettomargen +23 %, +3 %, −38 %, +28 %, Variationskoeffizient 6,2. Damit wechselt das Playbook von „inflection“ zu „cyclical“. Nachgerechnet mit dem App-Code auf dem SEC-Abschluss 2026 (EPS 74,33):

| Playbook | Fair Value |
|---|---|
| inflection | 1.119 |
| cyclical | 622 |

Die Prognose-EPS hat keinen Einfluss: Das Playbook „cyclical“ hat keine Forward-KGV-Methode.

**Bestandteile im Playbook „cyclical“:**
- EV/EBITDA mit höchstens 8,5× (Deckel für Zykliker).
- Ertragskraft (EPV, ohne Wachstum): 460.
- KBV (220) und Analystenziel (1.562) sind verworfen, weil sie mehr als Faktor 2 vom Median abweichen.

**Bewertung:** Im Sinne der Methode ist das plausibel. Bei Zyklikern im Hoch bremst sie bewusst; Gipfelgewinne sollen nicht billig wirken. Dagegen spricht der Konsens: Er erwartet für 2027 ein EPS von 176. Hält der Speicherzyklus an, ist 622 zu niedrig.

**Nebenbefund, offen:** Der Scanner rechnet für Micron noch mit dem ROIC-Geschäftsjahr 2025 (EPS 7,65, Fair Value 404,63). Den neueren Jahresblock der Ergänzungsdatei nutzt bisher nur die Einzelanalyse (`applySupplement`). In der ROIC-Risikohistorie liegen 28 von 392 Titeln ein Geschäftsjahr zurück (u. a. AAPL, V, QCOM, SBUX).

## Screener nutzt den Jahresblock wie die Einzelanalyse (16.11.2026)

**Befund:**
- Die Einzelanalyse ersetzt die ROIC-Jahreszahlen durch den Jahresabschluss der Ergänzungsdatei (`applySupplement`), sobald dieser gleich alt oder neuer ist. Der Screener nutzte immer ROIC.
- Bei 12 Titeln liegt ROIC ein Geschäftsjahr zurück: ACN, BEN, COST, CPRT, FDS, MU, ROK, SBUX, SMIN, SWKS, TDG, TEL. Beispiel Micron: Screener mit EPS 7,65 (Geschäftsjahr 2025), Einzelanalyse mit 74,33 (2026).

**Entscheidung des Nutzers:** Der Screener ruft denselben Schritt auf.
- Die Pipeline gibt den ROIC-Gewinnstichtag (`income_period`, `income_currency`, aus `roic.bundle`/`bundle_light`) und die vollständige Ergänzungsdatei mit; nur `risk_annual` und `annual_diagnostics` bleiben weg.
- Die Prüfung ist dieselbe wie in der Einzelanalyse: Notierung, Abruf ≤ 7 Tage, Abschluss ≤ 460 Tage, Währung, ADR-Basis.
- Die Datenprüfung des Screeners prüft jetzt auch „Anbieter meldet ein neueres Geschäftsjahr“.

**Folge 1 – der Cashflow:**
- Nach dem Jahresblock gibt es keinen berichteten FCFF mehr; operativer Cashflow minus Investitionen ist kein FCFF.
- Der DCF rechnet mit Gewinn × geprüfter Cash-Conversion, wie in der Einzelanalyse. Ohne Conversion bleibt er offen.

**Folge 2 – der Reverse DCF (Entscheidung des Nutzers):** Er nutzt jetzt dieselbe Basis wie der DCF: Gewinn × geprüfte Cash-Conversion, sonst berichteter FCFF (`reverseDcfInput`, valuation.ts). Das gilt für die Erwartungslücke im Screener (`cashflow_basis`) und in der Risikokarte. Die Abdeckungsmessung (`risk_construct_coverage.py`) zählt entsprechend.

**Messung (Daten vom 16.11.):**

| Gruppe | Titel |
|---|---|
| Screener übernimmt den Jahresblock | 1.316 von 1.340 |
| davon mit ROIC-Conversion | 915 |
| davon ohne ROIC-Conversion (DCF über den Yahoo-Ersatz aus #208, sonst offen) | 401 |
| ohne Jahresblock | 15 |
| Datei älter als 7 Tage | 5 |
| ohne Datei | 3 |
| Währung ohne Basis | 1 |

Die Wirkung auf Fair Value und Urteil zeigt der nächste precompute. Erwartung: große Änderungen bei den 12 Titeln mit neuerem Geschäftsjahr, kleine bei den übrigen (Jahreswerte statt ROIC-TTM).

### Nachtrag nach dem Lauf (16.11.2026, 00:24 UTC)

**Ergebnis** (1.341 Titel, Manulife neu):

| Größe | vorher | nachher |
|---|---|---|
| Cash-Conversion | 926 | 1.171 (+245 aus Yahoo) |
| ohne Cash-Conversion | 414 | 170 |
| Erwartungslücke mit Wert | – | 848 (841 Basis Gewinn × Conversion) |
| Daten prüfen | 13 | 11 |
| kauf | 105 | 86 |
| meiden | 968 | 1.051 |
| Fair Value | | Median −1,8 %, 200 Titel über ±25 % |

- Micron: 404,63 → 621,87, jetzt gleich wie in der Einzelanalyse.
- Gesperrt neu (wie in der Einzelanalyse): Anbieter meldet ein neueres Geschäftsjahr ohne verfügbaren Abschluss (TSE:4751, TSE:9983, BDX, DHI, IGG, PTC).
- Frei geworden: u. a. HEN3, TIT.

**Fehler im eigenen Code (seit Einführung des Jahresblocks, wirkte schon in der Einzelanalyse):**
- `applySupplement` löschte den ganzen Kennzahlenblock und setzte nur die Felder neu, die der Abschluss liefert.
- SEC-Abschlüsse liefern kein Wachstum, Versicherer keine Bruttomarge und kein EBIT; diese Felder fielen ersatzlos weg.
- Beispiel Hartford: begründetes KGV 203 → 127, Fair Value 221 → 125. Betroffen waren vor allem Versicherer und Banken; von 38 verlorenen Kaufurteilen viele Finanzwerte (HIG, GL, PZU, AMP, ISP, PKO …).

**Korrektur:**
- Bei gleichem Geschäftsjahr (Stichtage ≤ 35 Tage auseinander) bleiben aus der ROIC-Zeile derselben Periode erhalten: Wachstum (Umsatz, Gewinn), Brutto- und operative Marge, ROIC, EV/EBITDA. Bei gleicher Währung zusätzlich berichteter FCFF, Nettoschulden, Cash, Schulden und EBITDA/EBIT (nur mit Nettoschulden).
- Kennzeichnung: `supplement_retained_fields` und Hinweis im Status.
- Der Abschluss hat immer Vorrang.
- Bei neuerem Geschäftsjahr bleibt nichts aus dem Vorjahr.
- KGV und KBV werden aus den übernommenen Werten neu gebildet.
- Hartford im Nachbau: 117,8 → 134,6. Ohne Jahresblock wären es 154,3; der Rest ist ein echter Datenunterschied (Eigenkapitalrendite 20,2 % statt 22 %).

**Anzeige:** Nach Jahresblock oder Umrechnung übernimmt die Zeile EPS, Buchwert je Aktie, KGV, KBV und EV/EBITDA aus dem Rechenweg. Dazu kommt die Kennzeichnung `annual_supplement_applied`, `supplement_annual_end`, `supplement_retained_fields`. Bisher zeigte die Zeile alte Werte (Micron EPS 7,65, Equinor KGV 209,6).

## Umsatzwachstum aus SEC-Abschlüssen (16.11.2026)

**Befund:** 68 von 386 SEC-Jahresabschlüssen hatten kein Umsatzwachstum (Yahoo: 14 von 1.326). Betroffen sind u. a. Micron und Hartford. Das Wachstum kam bisher nur, wenn ein Yahoo-Abschluss mit exakt gleichem Stichtag dazu passte. Seit dem Behalten der ROIC-Felder (#210) zählt das bei Titeln mit **neuerem** Geschäftsjahr: Ohne den Wert fehlt dort das Wachstum ganz.

**Regel:** `sec_revenue_growth` nimmt den Vorjahresumsatz aus **derselben** Einreichung (Vergleichszahlen des 10-K) und mit **demselben** XBRL-Tag. Jahresdauer 330–400 Tage, Vorjahresende 330–400 Tage vor dem Stichtag, beide Umsätze positiv. Kennzeichnung `field_sources.revenue_growth.derivation = same_filing_prior_year` mit Tag und Vorjahresende. Ein Vorjahr aus einer anderen Einreichung oder mit anderem Tag zählt nicht.

**Wirkung:** Ab dem nächsten fundamentals-daily für die 68 Titel.

## Prognose-EPS über Faktor 2 bei gleicher Gewinnbasis (16.11.2026)

**Entscheidung des Nutzers:** Neben „höchstens Faktor 2 zum berichteten EPS“ gilt der Konsens auch dann, wenn zwei Bedingungen erfüllt sind:
- Das Vorjahres-Ist der Analysten (`year_ago_eps`) liegt höchstens 25 % neben dem berichteten EPS (`FORWARD_BASIS_TOLERANCE`). Dann ist es dieselbe Gewinnbasis, nicht bereinigt.
- Der 12-Monats-Konsens ist höchstens das Dreifache dieses Ist-Werts (`FORWARD_MAX_GROWTH`).

Kennzeichnung `eps_forward_check: gleiche_basis_bis_3fach` und Hinweis im Quellentext.

**Messung (1.121 prüfbare Titel):** gültig 896 → 944 (+48), u. a. Micron (Ist 75,52 zu 74,33, Konsens ×2,4), Advantest, Furukawa Electric. Weiter offen sind:
- über ×3, z. B. Kioxia ×12,9 und Aker BP ×16,7;
- bereinigte Basis, z. B. ServiceNow.

**Verzerrung:** Einmalgewinne im Konsens (Sapporo ×2,9) gehen bis ×3 durch. Die Basis-Prüfung schließt nur bereinigte Gewinne aus, keine Einmaleffekte in der Prognose.

## Cash-Conversion „nicht benötigt“ (16.11.2026)

Von den 170 Titeln ohne Cash-Conversion laufen 123 im Finanz- oder Zykliker-Modell. Beide Modelle haben keinen DCF. Sie tragen jetzt `cash_conversion_origin: not_required` mit Grund („nicht benötigt: Finanzmodell ohne DCF“) statt eines fehlenden Werts.

Bewertungsrelevant offen bleiben 47 Titel:
- 13 Verlustfirmen (DCF bewusst offen);
- 16 Japaner ohne aktuelles Jahr bei Yahoo/ROIC (EDINET folgt als eigenes Paket);
- 10 Versorger, REITs und Beteiligungen ohne gemeldete Investitionen;
- 8 sonstige.

### Nachtrag nach dem Lauf (16.11.2026, 11:25 UTC; mit #210, #212, #213)

| Größe | vorher (00:24) | nachher |
|---|---|---|
| kauf | 86 | 103 |
| beobachten | 193 | 232 |
| meiden | 1.051 | 996 |
| Daten prüfen | 11 | 10 |
| Finanzwerte mit kauf | 21 | 32 |
| Fair Value | | Median ±0 %, 89 Titel über ±25 % |

- **Felder behalten:** Hartford 124,6 → 164,8 (kauf), PZU 65 → 83 (kauf), Ameriprise 434 → 605 (kauf). Jahresblock bei 1.312 Titeln, davon 1.301 mit beibehaltenen ROIC-Feldern desselben Geschäftsjahres.
- **Prognose-EPS:** 958 geprüft (909 innerhalb Faktor 2, 49 bei gleicher Gewinnbasis bis ×3). Micron: Prognose 182,9 jetzt geprüft; der Fair Value bleibt 621,87, weil das Zykliker-Modell keine Forward-Methode hat.
- **Anzeige:** Equinor KGV 22,0 statt 209,6, Micron EPS 74,33.
- **Toyota Tsusho** ist frei (Toleranz ± 15 %).
- **Cash-Conversion:** 926 ROIC, 245 Yahoo, 123 „nicht benötigt“, 47 offen.
- **Erwartungslücke** mit Wert: 1.010.

**Noch nicht wirksam:** das SEC-Umsatzwachstum aus #211. fundamentals-daily lief vor dem Merge (Hartford noch ohne Wachstum im Abschluss).

**Korrektur Anzeige:** Fehlt dem Jahresblock ein Wert (Costco: kein EPS im Yahoo-Abschluss), zeigte die Zeile weiter den alten ROIC-Wert des Vorjahres (EPS 18,24). Jetzt werden die Rechenwerte auch leer übernommen.

## Abgleich App gegen Screener nach dem Deploy (bundle-compare v2, 16.11.2026)

50 Titel, alle abgerufen, keine Fehler, keine leeren ROIC-Blöcke.

| Größe | 13.11. | 16.11. |
|---|---|---|
| Fair Value, Median der Abweichung | 17 % | 0,01 % (P90 10 %) |
| 12M-Ziel, Median der Abweichung | 9 % | 6,8 % |
| Playbook-Unterschiede | 11 | 0 |
| Prognose-EPS beidseitig gleich | – | 33 von 33 (P90 0,004 %) |
| Erwartungslücke, Median der Abweichung | – | 0,1 Pp |
| Cash-Conversion-Herkunft unterschiedlich | – | 0 |

**Restliche Abweichungen:**
- 6 Titel nur in der App gesperrt: L'Oréal, EssilorLuxottica, Randstad, Umicore, AB InBev, mBank. Ursache war die Handelswährung aus dem ROIC-Profil statt aus der Kurszeile; korrigiert in `roic.ts` (Kopie aus valueapp-cf).
- Unilever: Jahresblock nur in der App. F5: Prognose nur im Screener. Ursache jeweils noch offen.
- PTC ist in beiden Wegen gesperrt (neueres Geschäftsjahr).

## Bewertungskennzahlen gleich gerechnet; fehlende Kennzahlen offen statt 50 (17.11.2026)

**Befund (bundle-compare v4, 16.11.2026, 50 Titel).**
- Die Kategorie Bewertung wich im Median um 8,8 Punkte ab. Ursache war ein Fehler im eigenen Code: Die Einzelanalyse berechnete Forward-KGV, PEG und FCF-Rendite nie. Bei 38 von 38 Titeln standen dort keine Eingänge, und die Teilnoten zählten neutral mit 50.
- Der Screener nahm dafür Yahoo `forwardPE` und `pegRatio` sowie die ROIC-FCF-Rendite (Teilnoten im Median 30, 32 und 20 Punkte anders).

**Methode `value_inputs_v1` (`src/lib/value-inputs.ts`, Entscheidungen des Nutzers).** Beide Wege rufen dieselbe Funktion in `evaluateStock` auf. Fremdwerte aus Yahoo und ROIC werden überschrieben.

| Kennzahl | Rechnung | Offen (zählt nicht) | Schlechteste Note (0) |
|---|---|---|---|
| Forward-KGV | Kurs / geprüftes 12M-Prognose-EPS (`consensus_ntm_blend_v1`) | kein geprüfter Konsens (mit dessen Grund), Kurs fehlt | geprüfter Konsens erwartet keinen Gewinn |
| PEG | Forward-KGV / (Prognose-EPS ÷ berichtetes EPS − 1) in % | wie Forward-KGV; berichtetes EPS ≤ 0 | kein Gewinn erwartet; Prognose-EPS ≤ berichtetes EPS |
| FCF-Rendite | FCFF / (Börsenwert + Nettoschulden) | Abschlusswährung nicht umgerechnet; FCFF, Börsenwert oder Nettoschulden fehlen; Unternehmenswert ≤ 0 | – |

- **FCF-Rendite gegen den Unternehmenswert, nicht gegen den Börsenwert.** `free_cashflow` ist in beiden Wegen der Cashflow des Unternehmens vor Zinsen (ROIC `ttm_free_cash_flow_firm`). Geteilt durch den Börsenwert ließe er verschuldete Firmen systematisch billig erscheinen.
- **Schlechteste Note statt Lücke (Verzerrung).** Ohne diese Regel stünden Firmen mit erwartetem Verlust oder schrumpfendem Gewinn durch die fehlende Kennzahl besser da als Firmen mit hohem, aber positivem KGV. Bisher galt dasselbe über negative Yahoo-Werte. Dafür prüft `applyForwardEstimate` „Konsens erwartet keinen Gewinn“ jetzt vor dem berichteten EPS und setzt `eps_forward_no_profit`.
- **Fehlende Kennzahlen (alle Kategorien).** Sie zählen nicht mehr, statt neutral 50. Die Kategorie mittelt die vorhandenen Werte. Hat sie keinen, bleibt sie offen (`null`, `cat_neutral`) und fällt aus dem Composite; die Gewichte werden renormalisiert. Dasselbe gilt für Momentum ohne 52-Wochen-Spanne und Katalysator ohne Signal. `metric_open` nennt je Kennzahl den Grund.
- **Peers.** Sie lesen `value_inputs` ihrer Universumszeile nur mit Methode `value_inputs_v1`. Bis zum nächsten Precompute haben die Zeilen keine PEG- und FCF-Werte; diese Kennzahlen laufen dann auf der festen Skala (gekennzeichnet als `scale`).
- **Anzeige.** Die Einzelanalyse zeigt unter der Scoring-Matrix offene Kennzahlen und schlechteste Noten mit Grund; eine offene Kategorie erscheint als „offen“. Die Screener-Zeile trägt `value_inputs`, `eps_forward_no_profit` und in `score_diagnostics` Grund und Maßstab `open`.

**Messung am Universum vom 16.11.2026 (1.341 Titel), vor der Änderung.**
- Forward-KGV künftig gefüllt bei 963 Titeln, offen bei 377, schlechteste Note bei mindestens 1. Weitere Verlustfälle unter den 90 Titeln mit berichtetem EPS ≤ 0 zeigt erst der Precompute.
- PEG gefüllt bei 852, offen bei 377, schlechteste Note bei 112 (Prognose ≤ berichtetes EPS oder kein Gewinn).
- Bisher hatte der Screener Yahoo-Werte bei 1.103 (KGV) bzw. 1.006 (PEG) Titeln.
- FCF-Rendite: Der Bestand lässt sich aus den Universumszeilen nicht messen (FCFF und Nettoschulden stehen nicht darin). Messung im nächsten Precompute.

**Grenzen.**
- PEG nutzt das 12-Monats-Wachstum, nicht Yahoos 5-Jahres-Schätzung. Es ist kurzfristiger, dafür nachvollziehbar.
- Bei Banken und Versicherern ist FCFF wenig aussagekräftig; die Kennzahl bleibt wie bisher Teil der Bewertung.
- Das Composite kann sich im ganzen Universum verschieben, weil 50er-Platzhalter wegfallen. Die Wirkung misst der nächste Precompute mit Bundle-Compare. Ein Probelauf der vollen Kette ist offline nicht möglich, weil die Scanner-Eingänge nur im Precompute entstehen.

**Tests.** `tests/value-inputs.test.mjs` mit 9 Fällen (gefüllt, offen mit Grund, Verlust und kein Wachstum, FCF offen, Fremdwerte überschrieben, Konsens-Flag, Kategorien und Composite, Peers mit/ohne Methode, Screener-Zeile). `tests/peer-valuation.test.mjs` ist angepasst. `npm test` 272/272.

**Pipeline.** `ts_bewertung.FELDER` übernimmt `value_inputs` und `eps_forward_no_profit` in die Universumszeile, damit die Peers dieselben Kennzahlen lesen. `value-inputs.ts` steht in `app-copies.json` (41 Dateien, identisch).

## Bundle-Compare v5: Analystenvotum im App-Weg messen (17.11.2026)

**Befund v4.** Der Katalysator wich im Median um 15,8 Punkte ab. Das Teilsignal „Analystenvotum“ fehlte im App-Weg bei 38 von 38 Titeln, im Screener war es bei allen 38 vorhanden. Beide Wege fragen Finnhub `stock/recommendation` ab; im App-Weg (`worker/bundle-fetch.ts`) verschluckt `finnhub()` jeden Fehler als `null`.

**Neu in v5 (nur Messung, keine Rechenwirkung).** Je Titel schreibt der Vergleich unter `rows[].analyst` mit:
- die Finnhub-Antwort: abgefragtes Symbol, HTTP-Status, Zeilenzahl, Typ, Zeitlimit oder Abruffehler; nie den Schlüssel;
- die Analystenzahl in App und Screener;
- ob das Analystenvotum in die Katalysator-Note eingeht.

`outputSummary.analystProbe` zählt die Status über alle Titel, auch über gescheiterte. Bis zu 10 Beispiele leerer Antworten stehen mit Symbol dabei.

**Erwartete Ursachen, die der Lauf trennt.**
- Abrufgrenze: 429.
- Berechtigung: 401/403.
- Falsches Symbol: leere Antwort, etwa bei Nicht-US-Notierungen, wo der nackte Ticker übergeben wird.
- Fehler beim Lesen in `bundleLight`: Antwort gefüllt, Votum trotzdem leer.

**Prüfung.** Build mit esbuild; Lauf mit nachgebildeten Antworten (Finnhub 429) ergibt `status: {"429": 2}` für 2 Titel.

## Screener: FCF und EV/EBITDA nur von ROIC (17.11.2026)

**Befund (bundle-compare v5, 50 Titel).**
- Bei 10 Titeln fehlte im App-Weg der freie Cashflow, darunter IBM, Pfizer, Tesco, Baxter, Weyerhaeuser, Stellantis und Rocket Lab; im Screener war er vorhanden. Ebenso EV/EBITDA bei 5 Titeln.
- Ursache: `providers.py` beginnt mit den Yahoo-Werten und überschreibt sie mit ROIC. Fehlt ein Feld bei ROIC, bleibt still der Yahoo-Wert stehen (`freeCashflow` = Cashflow nach Zinsen, `enterpriseToEbitda`), ohne Kennzeichnung und teils in anderer Währung.
- Die App nimmt beide Felder nur von ROIC.

**Regel (Entscheidung des Nutzers).** `ts_bewertung.eingabe` verwirft `free_cashflow` und `ev_ebitda` (`NUR_ROIC`), wenn sie nicht in `_roic_felder` stehen. Die Kennzahl bleibt dann wie in der App offen (FCF-Rendite „Freier Cashflow fehlt“, EV/EBITDA „Keine Daten“). Verworfene Felder stehen in `_pruef_eingang.nur_roic_verworfen`.

**Wirkung.** Etwas weniger Abdeckung im Screener (in der Stichprobe 10 FCF- und 5 EV/EBITDA-Werte). Dafür rechnen beide Wege dieselbe Definition. Die volle Zahl zeigt der nächste Precompute.

**Tests.** `test_ts_bewertung`: verworfen ohne ROIC-Herkunft, behalten mit ROIC-Herkunft, ohne Herkunftsliste verworfen; das Jumbo-Beispiel trägt die ROIC-Herkunft. 15/15 mit gebautem Scanner.

## Screener: zweiter Durchgang mit fertigen Peer-Zeilen (17.11.2026)

**Befund (bundle-compare v5, 17.11.2026, 10:30 UTC, 50 Titel).**
- Katalysator, Quantum und Eingänge stimmen jetzt überein: Katalysator im Median 0, Quantum 0,8, Analystenvotum in beiden Wegen 50/50.
- Die Kategorie Bewertung wich weiter um 4,6 Punkte im Median ab. Ursache: Der Screener bewertete Forward-KGV, PEG und FCF-Rendite immer auf der festen Skala (`scale`), die App gegen Peers (`peers`); betroffen waren 25, 21 und 30 Titel.
- Der Grund liegt im Ablauf: `ts_bewertung.anwenden` übergibt dem App-Code die Zeilen des laufenden Precompute als Peer-Universum. Diese waren alle frisch gescannt (1.341 von 1.341) und tragen die App-Felder (`value_inputs`, geprüfter Konsens, umgerechnete Kennzahlen) erst nach der Bewertung. Die App liest dagegen das fertige Universum.
- Das wäre auch mit weiteren Läufen nicht verschwunden; meine Einschätzung vom 17.11. früh („Übergang“) war falsch.

**Regel.**
- `anwenden` rechnet zweimal. Der erste Durchgang füllt eine vorläufige Kopie der Zeilen mit denselben Übernahmeregeln wie die fertige Zeile (`_uebernehmen`: FELDER und umgerechnete Kennzahlen). Der zweite Durchgang rechnet mit diesen Peer-Zeilen und liefert das Ergebnis.
- Fällt der zweite Durchgang aus, gilt der erste (`durchgaenge: 1` in der Statistik). Übernommene Zeilen bleiben unverändert.
- Laufzeit: Die TS-Bewertung dauert nur wenige Minuten des 104-Minuten-Laufs, ein zweiter Durchgang fällt kaum ins Gewicht.

**Tests.** `test_ts_bewertung`: zweiter Durchgang sieht Peer-Zeilen mit App-Feldern und umgerechneten Kennzahlen; übernommene Zeilen unverändert; Ausfall des zweiten Durchgangs behält den ersten. 17/17 mit gebautem Scanner; alle Precompute-Testschritte OK.

**Messung.** Ein Probelauf ist offline nicht möglich, weil die Scanner-Eingänge nur im Precompute entstehen. Erwartung für den nächsten Bundle-Compare: Maßstab `peers` in beiden Wegen; Bewertung im Median nahe 0.

## 12M-Kursziel: ROIC-Rohblöcke für den Screener (17.11.2026)

**Befund.** Das 12M-Kursziel wich im Median um 5,4 % ab (p90 23 %, bundle-compare v5, 100 Titel). Der Screener bekam KGV-Band (`pe_hist_*`), EBITDA-Reihe, `pe_history`, `phase_history` und `capital_return_period` nie. Die App leitet sie in `bundleLight` aus ROIC-Mehrjahresblöcken ab. Python lieferte nur `hist_pe_median` (1.296 Titel), das das Kursziel nicht liest.

**Regel (Entscheidung des Nutzers).**
- `roic.rohbloecke(t)` holt `multiples` (annual, 5), `enterprise_value`, `income` (annual, 3) und `cashflow` (annual, 3), mit denselben Pfaden und Parametern wie `worker/bundle-fetch.ts`. Ein Test prüft beide Seiten.
- `precompute.score_ticker` hängt die Blöcke als `_roic_raw` (`roic_raw_blocks_v1`, mit ROIC-Symbol) an die TS-Eingabe.
- Der App-Code (`historyFromRoicRaw`) leitet daraus alles ab wie in der Einzelanalyse, nur bei gleicher Notierung; sonst bleibt es offen mit `roic_history_status` (neu in FELDER).

**Kosten.** Bis zu 3 zusätzliche ROIC-Abrufe je Titel; die EV-Reihe ist schon im Zwischenspeicher. Der Lauf scannte am 17.11. rund 9 Titel je Minute, die ROIC-Grenze liegt bei 240 Abrufen je Minute. Mehrlaufzeit erwartet im Bereich weniger Minuten; der nächste Lauf misst es.

**Tests.** `test_ts_bewertung`: Pfade und Parameter wie in der App, ohne Schlüssel `None`, FELDER. Alle Precompute-Testschritte OK. App-Kopien: 41 Dateien identisch.

## Screener: auch Margen, Renditen, KBV und Current Ratio nur von ROIC (17.11.2026)

**Befund (bundle-compare v5, 17.11.2026, 17:22 UTC, 50 Titel).** Die Qualität wich bei 7 Titeln um mehr als 5 Punkte ab. Alle sieben sind Banken oder Versicherer: KeyCorp 9,5 gegen 38,3, Danske, CaixaBank, mBank, BPER, Julius Bär und Talanx. ROIC liefert für Banken keine Brutto- und operative Marge. `providers.py` ließ dann still die Yahoo-Werte stehen (Bruttomarge 0 %, operative Marge 35–59 %). Die App hat dort keine Werte.

**Regel.** `NUR_ROIC` umfasst jetzt `free_cashflow`, `ev_ebitda`, `pb`, `roe`, `roa`, `gross_margin`, `operating_margin` und `current_ratio`. Alle liest die App aus denselben ROIC-Feldern (`bundleLight`). Ohne ROIC-Herkunft verwirft der Screener den Wert, und die Kennzahl zählt wie in der App nicht. Ausnahme: `net_debt_ebitda`, das die App selbst aus Nettoschulden und EBITDA rechnet.

**Tests.** `test_ts_bewertung`: Bankfall KeyCorp (Yahoo-Margen verworfen, ROIC-Renditen behalten, `net_debt_ebitda` unberührt). Alle Precompute-Testschritte OK.

## Sektor „Industrial services“ nicht mehr pauschal Energie (17.11.2026)

`sektor._SEKTOR_ALIAS` (und die App-Kopie in `valuation.ts`) machte alle 41 Titel von FactSet „Industrial services“ zu „Energy“. Damit liefen sie im Zyklik-Modell und mit Energie-Multiples; Waste Management bekam z. B. einen Fair Value von 0,32× Kurs. Neu gibt `normalisieren(sector, industry)` nur bei Energie-Branchen (oil…, gas, drilling, pipeline) „Energy“ zurück, sonst „Industrials“. Alle Aufrufer geben die Branche mit.

Messung am Universum vom 17.11.: 22 von 41 Titeln verlassen das Zyklik-Modell (20 → Qualität, 2 → Wachstumswende), 19 bleiben zyklisch (7 Energie, 12 über die Margenschwankung). Tests: `tests/test_sektor_industrial_services.py`, im Workflow `precompute-3tage`; das Muster ist mit der App identisch, per Test geprüft.

## 52-Wochen-Band: Aktiensplits herausgerechnet (17.11.2026)

**Befund (QA-Analyse 17.11.2026).** 10 Titel hatten den Kurs auf dem 52-Wochen-Tief und ein Hoch von über 3,5× Kurs: 7 in Japan (u. a. Mitsui Kinzoku 41×, Furukawa Electric 32×, Kioxia 13,6×), dazu Netflix (Hoch 1.157,50 bei Kurs 59,85 nach dem 10:1-Split), CSG und Swissquote. Ursache: Seit K52 (13.11.) entsteht das Band aus unbereinigten ROIC-Schlusskursen, damit Dividenden den Abstand zum Kurs nicht verfälschen. Splits wurden dabei aber auch nicht bereinigt. Das verfälschte Momentum, Momentum-Teilziel und 52-Wochen-Position.

**Regel.**
- `roic.kursband` liest dieselbe Reihe mit `close` und `adj_close`. Springt das Verhältnis `adj_close/close` zwischen zwei Handelstagen um mehr als 25 % (`SPLIT_SPRUNG`), gilt das als Split (Faktor = Verhältnissprung).
- Kurse vor dem Split werden durch den Faktor geteilt, auf die heutige Aktienbasis. Dividendenschritte (wenige Prozent) bleiben unbereinigt.
- Erkannte Splits stehen in der Zeile als `52w_split_adjusted` (`adj_close_ratio_step_v1`, Datum, Faktor).

**Grenzen.**
- Tage ohne `adj_close` gehen unbereinigt ein; ein Split in einer solchen Lücke wird nicht erkannt.
- Eine Sonderdividende über 25 % des Kurses würde als Split gewertet.
- Analystenziele nach einem Split sind nicht Teil dieser Änderung: Bei den japanischen Fällen liegt das Analystenziel teils 2–3× über dem Kurs. Das prüft der nächste Abgleich.

**Tests.** `tests/test_roic_52w.py`: 10:1-Split im Fenster, Dividenden kein Split, Zusammenlegung, fehlendes `adj_close`, Einlesen der jüngsten Tage. Die volle Zahl der betroffenen Titel zeigt der nächste Precompute (Feld `52w_split_adjusted`).
