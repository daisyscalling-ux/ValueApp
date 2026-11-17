# Bewertung: Änderungen aus der QA-Analyse vom 17.11.2026

Die QA-Analyse prüfte 100 Titel aus 18 Ländern und 22 Sektoren auf plausible Fair Values und 12M-Ziele. Klare Fehler (Sektor-Tabelle, Aktiensplits) stehen in `BEWERTUNG_RECHENWEG.md`; hier stehen die Methodenänderungen nach Entscheidung des Nutzers. Die App-Doku dazu steht in `BEWERTUNG-RISIKODATEN.md` (valueapp-cf).

## Punkt 3: Sondereffekte im Gewinn, Phasenregel im Finanzmodell

- **Sondereffekt-EPS (`epsBasis`, `valuation.ts`).** Liegt das berichtete EPS mehr als 1,4× über dem geprüften 12M-Konsens, rechnen begründetes KGV und das heutige KGV im 12M-Ziel mit dem Konsens. Betroffen sind 23 Titel im Universum vom 17.11. (Comcast: Fair Value vorher 2,4× Kurs). Kennzeichnung `eps_basis` in der Zeile (FELDER).
- **Phasenregel.** „Start-up / Hyperwachstum / Rückgang ⇒ vorläufig“ gilt nicht im Finanzmodell. Betroffen sind 30 Banken und Versicherer, z. B. KeyCorp mit „Umsatz“ +66 %.
- **Messung.** Die tatsächliche Wirkung auf Fair Value und Verlässlichkeit zeigt der nächste Precompute.
