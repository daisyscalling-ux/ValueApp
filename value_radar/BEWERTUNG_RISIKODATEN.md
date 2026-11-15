# Bewertung mit den Daten des Risikoscores

Stand 12.11.2026. Ziel: Die geprüften Daten aus dem Risikoscore sollen in Composite, Fair Value, Quantum Score und 12M-Ziel einfließen.

## Ausgangslage (Messung 12.11.2026)

**Zwei Rechenwege.** Scanner, Suche und Kauf-Urteil kommen aus der Pipeline (`precompute.py` → `scoring.py`, `valuation.py`, Werte in `cf_universum.json`). Die Einzelanalyse rechnet live in der App (`evaluation.ts` → `scoring.ts`, `valuation.ts`). Bei identischen Eingängen (1.190 Titel aus `daten/fundamentals`) wichen sie deutlich ab:

| Größe | Median | P90 | Titel mit großer Abweichung |
|---|---:|---:|---:|
| Composite (App mit `scoresPlus`) | 2,2 Punkte | 4,7 | 104 über 5 Punkte |
| Fair Value | 2,4 % | 30,3 % | 267 über 10 % |
| Quantum | 3,0 Punkte | 9,3 | 343 über 5 Punkte |
| 12M-Ziel | 3,8 % | 12,7 % | 161 über 10 % |

Ursachen:
1. Playbook nach Rohsektor in Python (Befund PB1 in `AUDIT_BEFUNDE.md`, behoben).
2. Nur in der App: Unternehmensphasen (`lifecycle.ts`), `scoresPlus` (Bilanz, Momentum, Katalysator).
3. Nur in Python: Datenqualitätsstufe (`datenqualitaet`), Analysten-Trend und -Skepsis im Quantum.

Nicht gemessen: Unterschiede der Datenquellen beider Wege (Pipeline: `providers.get_fundamentals`; App: `/api/bundle`), weil die Live-Eingänge nicht gespeichert werden.

**Verfügbare Risikodaten** (1.340 Titel, Datenstand main 17fd7243):

| Daten | Abdeckung | mögliche Verwendung |
|---|---:|---|
| Geprüfte Peergruppe, ≥ 3 Peers je Kennzahl | 1.024–1.105 | Perzentile im Composite (heute feste Ersatzskalen, weil überall `peerFunds = null`), Peer-Multiples im Fair Value |
| Gemessene Kursrisiken (ES, Volatilität, größter Rückgang) | 1.323 | 12M-Spanne statt Beta × 18 %, Sicherheitsabschlag |
| Geprüfte Finanzkennzahlen je Profil | Unternehmen 1.125/1.126; Banken CET1 76, LCR 69, Kredite 75 von 88; Versicherer Solvenz 20 von 52 | Bilanz-Kategorie des Composite |
| Historie mit Herkunft, ≥ 5 Jahre | operativer Cashflow 1.048, Gewinn 1.245, freier Cashflow 753 | DCF mit normalisierter Cashflow-Umwandlung |
| Erwartungslücke (Reverse DCF bzw. Eigenkapitalrendite) | 1.319 | Signal für Bewertungsfallen im Quantum |
| Bestätigte Ereignisse | 0 | vorerst keine |

## Entscheidungen des Nutzers (12.11.2026)

1. **Ein Rechenweg: TypeScript.** Die App-Fassung wird die einzige. Die Pipeline führt sie per esbuild aus (wie beim Risikoscore) und schreibt die Scanner-Werte.
2. **Nur Eingangsdaten nutzen.** Die geprüften Daten fließen dort ein, wo sie fachlich hingehören. Der Gesamt-Risikoscore bleibt eine getrennte Anzeige und geht nicht in Quantum oder Fair Value ein (nicht kalibriert; Block „Bewertungsrisiko“ nutzt selbst den Fair Value).

## Reihenfolge

1. Befund PB1 beheben (erledigt, siehe oben).
2. Einheitlicher Rechenweg: Python-Teile, die nur dort existieren, nach TS übernehmen; Pipeline schreibt Scanner-Werte aus `evaluateStock`.
3. Risikodaten je Zielgröße, jeweils mit Messung, Tests und Probelauf.

## Erwartungslücke: nur Kontext (15.11.2026)

**Letzter Baustein des Plans vom 12.11.:** die Erwartungslücke aus dem Risikoscore. Sie ist das vom Kurs vorausgesetzte Cashflow-Wachstum (Reverse DCF) minus dem Umsatzwachstum des letzten Geschäftsjahres.

**Messung (786 Titel, Cashflow aus den Jahresabschlüssen der Ergänzungsdateien, gleiche Berichts- und Handelswährung):**
- Spearman zur Bewertung (Upside): −0,29, zum Quantum: −0,38. Die Lücke bringt also eigene Information.
- Verteilung: P10 −12,3, Median +4,0, P90 +17,8 Prozentpunkte. 115 Titel liegen über 15 Pp.
- Als Value-Trap-Signal (Upside > 25 % und Lücke > 15 Pp) träfe sie 17 Titel. 12 davon haben schon ein anderes Warnsignal, 11 sind japanische, kapitalintensive Firmen.

**Entscheidung des Nutzers:** nur anzeigen, `scoreContribution: 0`. Quantum, Composite, Fair Value und Urteil bleiben unverändert.

**Begründung:**
- Die Schwelle wäre unkalibriert.
- Hohe Investitionen drücken den freien Cashflow; kapitalintensive Firmen erschienen dann systematisch zu teuer (Verzerrung).

**Umsetzung:**
- `expectationGap` (scanner-evaluation.ts, Methode `reverse_dcf_minus_revenue_growth_v1`) schreibt `expectation_gap` in die Universumszeile: vorausgesetztes Wachstum, Umsatzwachstum und Lücke in Pp, oder einen Grund, warum die Lücke offen ist.
- Für Banken, Versicherer und Spezialfinanzierer steht die Lücke in der Risikokarte (Finanzmodell).
- Der Screener zeigt die Spalte „Erw.-Lücke“ mit der Erklärung im Tooltip.
- In der Einzelanalyse steht die Lücke bereits in der Risikokarte (Block „Bewertungsrisiko“).

**Grenze:** Die Messung nutzt operativen Cashflow minus Investitionen aus dem Jahresabschluss. Im Lauf zählt der FCFF aus ROIC, die Werte weichen deshalb ab.

Damit ist der Plan vom 12.11. abgeschlossen: 7 Bausteine fließen in die Bewertung ein, die Erwartungslücke ist bewusst nur Kontext.
