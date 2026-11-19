# Bewertung: Änderungen aus der QA-Analyse vom 17.11.2026

Die QA-Analyse prüfte 100 Titel aus 18 Ländern und 22 Sektoren auf plausible Fair Values und 12M-Ziele. Klare Fehler (Sektor-Tabelle, Aktiensplits) stehen in `BEWERTUNG_RECHENWEG.md`; hier stehen die Methodenänderungen nach Entscheidung des Nutzers. Die App-Doku dazu steht in `BEWERTUNG-RISIKODATEN.md` (valueapp-cf).

## Punkt 3: Sondereffekte im Gewinn, Phasenregel im Finanzmodell

- **Sondereffekt-EPS (`epsBasis`, `valuation.ts`).** Liegt das berichtete EPS mehr als 1,4× über dem geprüften 12M-Konsens, rechnen begründetes KGV und das heutige KGV im 12M-Ziel mit dem Konsens. Betroffen sind 23 Titel im Universum vom 17.11. (Comcast: Fair Value vorher 2,4× Kurs). Kennzeichnung `eps_basis` in der Zeile (FELDER).
- **Phasenregel.** „Start-up / Hyperwachstum / Rückgang ⇒ vorläufig“ gilt nicht im Finanzmodell. Betroffen sind 30 Banken und Versicherer, z. B. KeyCorp mit „Umsatz“ +66 %.
- **Messung.** Die tatsächliche Wirkung auf Fair Value und Verlässlichkeit zeigt der nächste Precompute.

## Punkt 5: 12M-Ziel ein Drittel Richtung Fair Value

- Bei verlässlichem Fair Value ist das fundamentale Teilziel Kurs + (Fair Value − Kurs) / 3 (`KURSZIEL_FV_ANTEIL`), statt das heutige KGV zu halten. Analysten- und Momentum-Teil bleiben; ohne verlässlichen Fair Value gilt die KGV-Rechnung.
- Offline aus den Teilzielen der Diagnose nachgerechnet (1.176 Titel, 747 mit verlässlichem Fair Value): Median des 12M-Ziels +12,2 % → +6,0 %. Gegenläufig zum Fair Value: 382 → 215 Titel.

## Punkt 4: Zins je Währung aus amtlichen Quellen, relativer Boden

- `scripts/export_rates.py` (Workflow `rates-daily`, Montag bis Samstag 05:23 UTC) schreibt `daten/cf_rates.json` (`gov_10y_v1`): Rendite 10-jähriger Staatsanleihen mit Wert, Stichtag, Quelle, Quell-URL, sha256 und Abrufzeit. Fehlt eine Quelle oder ist der Wert älter als 7 Tage, steht die Währung mit Grund unter `issues`.
  - Quellen: US-Treasury (USD), EZB AAA-Kurve (EUR), Finanzministerium Japan (JPY), Bank of England IUDMNZC (GBP), Riksbank SEGVB10YC (SEK), Norges Bank GOVT_GENERIC_RATES 10Y (NOK).
  - Ohne aktuelle Tagesquelle: CHF (SNB-Reihe endet am 31.07.2025), DKK und PLN (bei der EZB nur Monatswerte).
- `ts_bewertung.anwenden` reicht die Datei als `_rates` an jeden Eingang; der App-Code (`riskFree`) prüft Methode, Alter und Wertebereich und setzt den Boden der Kapitalkosten auf Zins + 4 Prozentpunkte. Ohne gültigen Wert bleibt es bei 4,2 % und 8,5 %, gekennzeichnet (Zeile `risk_free`).
- Livetest 17.11.2026: USD 5,120 %, EUR 3,422 %, JPY 2,927 %, GBP 5,322 %, SEK 3,110 %, NOK 4,385 %.
- Wirkung (offline geschätzt): WACC-Median EUR 8,50 → 7,42 %, JPY 8,50 → 7,00 %, SEK 8,50 → 7,36 %, USD 8,80 → 9,72 %, GBP 8,50 → 9,32 %; CHF, DKK, PLN unverändert.
- Tests: `scripts/test_export_rates.py` (Parser je Quelle, Frische, Fehler), `test_ts_bewertung` (Weitergabe an jeden Eingang).
- **Reihenfolge nach dem Merge:** zuerst `rates-daily` starten, dann Precompute. Ohne Zinsdatei rechnet alles wie bisher mit dem gekennzeichneten Ersatz.

## Nachtrag Punkt 3 (19.11.2026): Sondereffekt auch in der DCF-Gewinnbasis

Die QA-Wiederholung vom 17.11. zeigte Comcast mit Fair Value +198 % („kauf“). Der DCF rechnete weiter mit Jahresüberschuss × Cash-Conversion, und der Jahresüberschuss enthielt den Sondereffekt. Nach Entscheidung des Nutzers kürzt `fcfBasis` (`valuation.ts`) den Jahresüberschuss im Verhältnis Konsens ÷ berichtetes EPS, sobald `epsBasis` den Konsens nutzt. Das gilt für DCF und Reverse DCF; betroffen sind dieselben 22 Titel. App-Kopie abgeglichen, Tests in valueapp-cf.

## Endwachstum des DCF je Titel (19.11.2026)

Comcast behielt nach der Sondereffekt-Regel einen Fair Value von +155 % („kauf“). Ursache war das einheitliche ewige Wachstum von 2,5 % im DCF, auch bei stagnierendem Umsatz. Nach Entscheidung des Nutzers gilt jetzt `terminalGrowth` (`valuation.ts`): das Umsatzwachstum p. a. über drei Geschäftsjahre aus `reihe_umsatz`, begrenzt auf 0 bis 2,5 %. Ohne gültige Reihe bleibt es bei 2,5 %, gekennzeichnet. Das gilt für DCF, Reverse DCF und die DCF-Zerlegung. Der Screener hat `reihe_umsatz` über die ROIC-Rohblöcke (`_roic_raw`). Kennzeichnung `terminal_growth` in der Zeile (FELDER). Näherung nach Vorjahreswachstum: rund 208 von 664 DCF-Titeln betroffen; Comcast DCF etwa 52 → 35 bei Kurs 25.
