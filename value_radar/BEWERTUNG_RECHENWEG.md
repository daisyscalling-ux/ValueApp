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
