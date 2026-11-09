# Tägliches Rohdaten-Archiv für die Kalibrierung

Stand 09.11.2026. Der Kursblock des Risikoscores ist mit historischen Kursen kalibriert (`value_radar/sec_pilot/PRICE-BLOCK-STUDY.md`). Die übrigen Blöcke (Finanzen, Umfeld, Bewertung, Wettbewerb, Branchenmodelle) lassen sich nur prüfen, wenn bekannt ist, welche Werte an einem Tag tatsächlich vorlagen. Heutige Anbieterdaten sind dafür ungeeignet, weil sie spätere Korrekturen und Veröffentlichungen enthalten.

## Was gespeichert wird

`feature_snapshot.py` schreibt im Lauf `daily-risk` die Datei `daten/risk_observations/features/JJJJ-MM-TT.json.gz`. Je Notierung des App-Universums:

| Bereich | Inhalt | Quelle |
|---|---|---|
| Kurs | Beobachtungen, letzter Kurs, Expected Shortfall, Volatilität, größter Rückgang, schlechteste 20 Tage, Abstand zum Jahreshoch | `cf_risk.json` |
| Markt | Proxy-ETF und dessen Abstand zum Jahreshoch | `cf_risk.json` |
| Branche | Vergleichsgruppe, Abstand und Median der Peers, breiterer Sektor | App-Pakete `risk_app/` |
| Abschluss | Periodenende, Veröffentlichungsdatum, Umsatz, Bruttogewinn, EBIT, EBITDA, Jahresergebnis, operativer Cashflow, Investitionen, Cash, Schulden, Bilanzsumme, Eigenkapital; Kurs, Aktienzahl und Beta zum Abrufzeitpunkt | `daten/fundamentals/` |
| Bewertung | Kurs, Fair Value, Upside, Umsatzwachstum, Brutto- und EBITDA-Marge, Multiples | `cf_universum.json` |
| Banken | CET1- und weitere Kapitalquoten, Fed-Anforderung, Konzern-LCR, auffällige Kredite mit Peer-Median | App-Pakete |
| Versicherer | Solvenzquoten der letzten Berichte | App-Pakete |
| Ereignisse | nur geprüfte, bestätigte Ereignisse | App-Pakete |

Es werden keine Scores gespeichert. Jede spätere Formelversion, auch Reverse DCF, Margentrend und Verschuldung, wird aus denselben Rohdaten nachgerechnet.

## Regeln

- Nur die erste Beobachtung je UTC-Tag wird geschrieben, spätere Läufe desselben Tages überschreiben sie nicht.
- Die Werte werden nie rückdatiert. Abschlüsse tragen ihr eigenes Periodenende und, wo bekannt, das Veröffentlichungsdatum.
- Die Prüfsummen der Eingangsdateien und der App-Pakete werden mitgespeichert. Ein manipuliertes Paket bricht die Erstellung ab, ein veraltetes ebenso (älter als 36 Stunden).
- Fehlende oder nicht endliche Werte bleiben weg, nie null oder geschätzt. Zahlen werden auf 6 signifikante Stellen gerundet.
- Ein Fehler beim Archivieren blockiert die Veröffentlichung der Risikodaten nicht (eigener Schritt mit `continue-on-error`).

Erster Probelauf mit dem Stand vom 09.11.2026: 1.332 Notierungen, davon 1.256 mit Kursstatistik, 1.281 mit Jahresabschluss (177 mit Veröffentlichungsdatum), 9 Banken und 2 Versicherer mit geprüftem Kapital. Etwa 350 KB pro Tag.

## Auswertung später

`load_snapshots(ordner)` liefert alle Tage in zeitlicher Reihenfolge. Spätere Verluste werden aus eigenen, ebenfalls datierten Kursbeobachtungen gemessen, nicht aus heutigen Reihen. Eine erste Prüfung der übrigen Blöcke ist nach etwa einem Jahr sinnvoll. Mit Quartalsstichtagen ergeben sich dann vier Querschnitte mit je rund 1.300 Aktien.

## Grenzen

- Nur 177 Abschlüsse haben ein bestätigtes Veröffentlichungsdatum. Für die übrigen gilt der Abrufzeitpunkt als frühester belegter Kenntnisstand.
- Anbieterwerte können später revidiert werden. Das Archiv hält den damals gelieferten Stand fest, belegt aber nicht dessen Richtigkeit.
- Größe: etwa 130 MB pro Jahr im Repository. Bei Bedarf in GitHub-Releases auslagern.
