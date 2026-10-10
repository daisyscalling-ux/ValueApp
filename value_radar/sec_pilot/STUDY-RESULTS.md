# Ergebnis der erweiterten SEC-Studie

Stand: 10. Oktober 2026. Lauf: https://github.com/daisyscalling-ux/ValueApp/actions/runs/38079446760

## Entscheidung

Keine Anpassung der produktiven Risikogewichte aus dieser Untersuchung. Zusätzliche jährliche Finanzmerkmale verbessern den bestehenden Kursrisikoscore in keiner der neun auswertbaren Kombinationen aus Merkmalgruppe und Zeithorizont. Das ist ein Befund dieser kleinen Stichprobe, kein Beweis gegen die allgemeine Relevanz von Finanzkennzahlen.

## Daten und Prüfung

- 20 vorab für diesen technischen Versuch festgelegte aktuelle US-Unternehmen; 19 mit Kursen und SEC-Daten geladen, 532 überlappende Beobachtungsfenster über 1, 3 und 6 Monate.
- Exxon Mobil wurde wegen leerer SEC-Tickerliste von der strengen Identitätsprüfung ausgeschlossen; die Zuordnung wurde nicht stillschweigend freigegeben.
- UnitedHealth: Bilanzüberleitung widersprüchlich, alle 28 Finanzfenster ausgeschlossen. Merck: 11 Fenster wegen veralteter jährlicher Daten ausgeschlossen.
- 493 Fenster besitzen grundsätzlich zuordenbare Finanzdaten; einzelne Merkmale fehlen weiterhin. Je Vergleich werden nur vollständig verfügbare Merkmale genutzt, jeweils identisch für Basis- und erweitertes Modell.
- FCF-Vergleiche enthalten 13 Unternehmen; Verbindlichkeitenvergleiche 16 im früheren und 17 im späteren Zeitraum. Nettoverschuldung nur 4 bzw. 5: alle sechs betreffenden Vergleiche gesperrt.
- 12 Tests bestanden; GitHub-Pilot- und Studienprüfungen erfolgreich. ZIP-Prüfsumme und sämtliche SEC-Rohdateiprüfsummen lokal geprüft.

## Drei Monate: Ergebnis gegenüber dem bisherigen Kursrisikoscore

| Zusätzliches Merkmal | Veränderung des mittleren quadratischen Fehlers |
|---|---:|
| Negativer FCF / Bilanzsumme | +9,39 % (schlechter) |
| Verbindlichkeiten / Bilanzsumme | +2,64 % (schlechter) |
| Beide zusammen | +9,56 % (schlechter) |

Gegenüber reiner Volatilität fallen zwei von neun auswertbaren Vergleichen günstiger aus, beide über sechs Monate: Verbindlichkeiten allein und kombiniert mit FCF. Beim kombinierten Modell verschlechtert sich jedoch die Gesundheitsbranche. Keine Auswahl der Gewinner oder Optimierung der Gewichte anhand dieser Ergebnisse.

## Einordnung

Aktuelle überlebende Unternehmen, kleine Stichprobe, überlappende Zeitfenster und gemeinsame Marktschocks begrenzen die Aussage. Fünf Jahre Kurshistorie plus Vorlauf lassen keine echte Prüfung späterer Verluste während der Krisen 2020/2022 zu. Jahresdaten ersetzen keine vollständige Rekonstruktion damaliger Quartalsinformationen. Die SEC-Merkmale sind nicht identisch mit dem produktiven ROIC-Finanzscore. Der nächste sachliche Ausbau wäre eine bessere Standardtag-Abdeckung und eine breitere, separat festgelegte Stichprobe einschließlich ausscheidender Unternehmen; keine nachträgliche Gewichtssuche.

Die vollständigen Kennzahlen und archivierten Rohdaten liegen im Actions-Artefakt `sec-financial-study-38079446760-1` (90 Tage Aufbewahrung). `study-result-2026-10-10.json` hält den kompakten Ergebnisbericht dauerhaft im Repository fest.
