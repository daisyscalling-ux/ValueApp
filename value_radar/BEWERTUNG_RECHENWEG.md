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
