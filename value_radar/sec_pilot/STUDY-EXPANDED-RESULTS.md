# Erweiterte SEC-Studie: 40 vorgesehene Unternehmen

Stand: 10. Oktober 2026. Ergebnislauf: https://github.com/daisyscalling-ux/ValueApp/actions/runs/38079946899

## Ergebnis und Entscheidung

39 von 40 Unternehmen geladen, 4.368 Kursfenster; Beobachtungsstichtage 2016-12-30 bis 2026-06-30. Zwölf Jahre Kurshistorie angefragt, die ersten zwei Jahre dienen als Vorlauf. Alle 24 Vergleiche erfüllen die vorab festgelegten Mindestzahlen. Keine Anpassung der produktiven Risikogewichte: Die Ergebnisse sind gemischt und überwiegend klein.

| Zusatzmerkmal gegenüber Kursrisikoscore | 1 Monat | 3 Monate | 6 Monate |
|---|---:|---:|---:|
| Negativer FCF / Bilanzsumme | −0,34 % | −0,19 % | +2,06 % |
| Verbindlichkeiten / Bilanzsumme | +0,02 % | +0,48 % | +0,16 % |
| Nettoverschuldung / Bilanzsumme | +2,56 % | +0,38 % | −1,83 % |
| Verbindlichkeiten und FCF | −0,28 % | −0,08 % | +0,45 % |

Angegeben ist die relative Veränderung des mittleren quadratischen Fehlers im späteren Zeitraum; negativ bedeutet weniger Fehler. Dies sind keine Trefferquoten und keine Verlustwahrscheinlichkeiten. Nettoverschuldung verbessert den Sechsmonatsvergleich gegenüber reiner Volatilität um 4,06 %, beruht später aber nur auf neun Unternehmen und 41 Fenstern. Keine nachträgliche Auswahl dieses Merkmals als validierter Gewinner.

## Behobene Datenprobleme

- UnitedHealth: separat gemeldete rückzahlbare Minderheiten schließen die Bilanzüberleitung. Alle 38 Jahresdaten-Stichtage sind für die drei Finanzmerkmale nutzbar. Diese Minderheiten werden nicht als Finanzschulden hinzuaddiert.
- Merck: Jahresauswahl erkennt auch CFO aus fortgeführten Aktivitäten. Ein Gesamt-CFO wird nur mit explizit gemeldetem CFO aufgegebener Aktivitäten rekonstruiert. 36 Stichtage mit zuordenbaren Finanzdaten, davon 23 mit Nettoverschuldung und sieben mit FCF; fünf Kursfenster bleiben wegen nicht übergeleiteter Amendments ausgeschlossen.
- Verbindlichkeiten fehlen weiterhin bei manchen Firmen. Nur direkt gemeldete Summen oder vollständige kurzfristige plus langfristige Bestandteile sind erlaubt. Bilanzsumme minus Eigenkapital wird nicht pauschal verwendet.
- Ungeklärte Bilanzabweichungen sperren nur das Verbindlichkeitenmerkmal. Andere belegte Merkmale bleiben separat prüfbar.
- Exxon Mobil bleibt wegen leerer SEC-Tickerliste ausgeschlossen. Keine automatische Lockerung der Identitätsprüfung.

## Abdeckung

Über alle Firmen sind 982 Firmen-Stichtage mit Verbindlichkeiten, 966 mit FCF und 285 mit Nettoverschuldung verfügbar. Spätere Vergleiche: FCF 28 Unternehmen, Verbindlichkeiten 26, Kombination 18, Nettoverschuldung neun. Jeder Basis-/Zusatzvergleich nutzt exakt dieselben vollständigen Beobachtungen; Vergleiche verschiedener Merkmalsgruppen dürfen deshalb nicht unmittelbar als Rangliste gelesen werden.

15 Tests bestanden, GitHub-Datenlauf erfolgreich. ZIP-Prüfsumme und sämtliche archivierten SEC-Rohdateiprüfsummen lokal verifiziert. Rohdaten im Artefakt `sec-financial-study-38079946899-1`, 90 Tage Aufbewahrung; kompakter Bericht dauerhaft in `study-result-expanded-2026-10-10.json`.

## Grenzen und nächster belastbarer Schritt

Die aktuelle Auswahl von 40 überlebenden Unternehmen ist keine historische Indexzusammensetzung. Ausgeschiedene Firmen und deren vollständige Delisting-Renditen fehlen. Die Krisen 2020/2022 liegen im Trainingszeitraum und sind kein unabhängiger Krisentest. Die spätere Periode wurde schon beim ersten Versuch betrachtet; auch dieser Lauf ist explorativ. Die Erweiterung verändert zugleich Stichprobe, Historienlänge und Datenzuordnung, isoliert also keinen einzelnen Änderungseffekt. Jahresdaten ersetzen keine damaligen Quartalsinformationen. Gemeinsame Marktschocks, überlappende Fenster und mehrere Vergleiche erlauben keine Signifikanzbehauptung.

Als nächster methodischer Schritt wäre ein festgeschriebener zeitlich rollierender Test mit getrennt ausgewiesenen Krisenjahren und einer historischen Mitgliedschaftsliste einschließlich ausgeschiedener Werte erforderlich. Dafür müssen Herkunft, Börsenidentität und Delisting-Daten zuerst geklärt sein. Vorher keine Wahrscheinlichkeitskalibrierung oder automatische Gewichtsoptimierung.
