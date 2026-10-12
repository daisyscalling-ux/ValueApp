# Historische Haltefenster: 1, 3 und 6 Monate

## Feste Auswertungsregel

Jeder Handelstag der letzten sechs Kalenderjahre ist ein moeglicher Entscheidungsstichtag, sofern das Wertpapier an diesem Tag im rekonstruierten Indexbestand liegt. Einstieg zum Schlusskurs des naechsten Handelstags, anschliessend 21, 63 oder 126 Tagesrenditen. Dies sind Handelszeit-Naeherungen fuer Monate. Die Rendite am Einstiegstag selbst wird nicht mitgerechnet.

Ein Indexaustritt beendet das Fenster nicht. Daten nach dem Austritt werden ebenfalls geprueft. Ein fehlender Einstiegskurs oder eine fehlende/ungueltige Tagesrendite macht das Fenster unvollstaendig. Kursreihen mit gesperrter Identitaet werden nicht verwendet. Fehlende Kurse, Abwicklungen oder Nachfolgerpfade werden weder interpoliert noch mit null aufgefuellt.

Noch nicht abgeschlossene Fenster sind separat `pending_windows`, keine bereits festgestellten Datenluecken. Jede erwartete Kombination aus Wertpapier, Stichtag und Horizont bleibt gezaehlt. Es gilt:

- expected = pending + mature
- mature = covered + incomplete

`covered` bedeutet ausschliesslich lueckenlose technische Datenabdeckung. Es bestaetigt weder Kapitalmassnahmen noch Delisting-/Uebernahmeerloese oder historische Identitaeten. Kein kalibrierter Riskscore, keine Trefferwahrscheinlichkeit. Taegliche ueberlappende Fenster sind nicht unabhaengige Beobachtungen.

## Ergebnis am vorhandenen Archiv

Quelle: main-Lauf 38209892625, erstellt 12.10.2026, anschliessend mit den Identitaetskorrekturen aus PR #23 lokal ausgewertet. Entscheidungszeitraum 12.10.2020 bis 12.10.2026 exklusiv. Damit umfasst diese konkrete Sechsjahresauswahl nicht den Corona-Crash im Fruehjahr 2020 und belegt nicht die Abdeckung jeder Marktphase.

| Horizont | Abgeschlossen | Lueckenlos | Mit Luecken | Noch nicht abgeschlossen |
| --- | ---: | ---: | ---: | ---: |
| 21 Handelstage | 747.268 | 715.327 | 31.941 | 11.069 |
| 63 Handelstage | 726.142 | 694.244 | 31.898 | 32.195 |
| 126 Handelstage | 694.451 | 662.698 | 31.753 | 63.886 |

Je Horizont werden 758.337 erwartete Fenster beruecksichtigt.

| Fenster ueber einen Indexaustritt hinaus | Abgeschlossen | Lueckenlos |
| --- | ---: | ---: |
| 21 Handelstage | 2.299 | 1.305 |
| 63 Handelstage | 6.488 | 3.651 |
| 126 Handelstage | 12.160 | 6.754 |

Die geringere Abdeckung nach Austritten ist fuer die spaetere Risikostudie wesentlich. Nur vollstaendige Fenster auszuwerten wuerde die offenen Faelle systematisch ausblenden. Die Daten sind weiterhin nicht fuer eine unverzerrte Gesamtaussage zum historischen S&P 500 freigegeben.

## Automatisierung und Dateien

`window_coverage.py QUELLE AUSGABE` liest den bestehenden Rohexport mit identity-review und session-review aus einem Ordner oder ZIP. Kein erneuter Netzwerkabruf erforderlich. Der Workflow free-source-research fuehrt die Pruefung kuenftig nach der Handelstagepruefung aus und nimmt window-review in sein Artefakt auf.

- window_coverage.json: Summen, Methodik, Datenzeitpunkt und Fingerabdruck des Identitaetsregisters.
- fenster_je_wertpapier.csv: vollstaendige Zaehler je Wertpapier/Horizont, auch bei fehlenden Reihen.
- luecken_beispiele.csv: maximal drei Beispiele je Wertpapier/Horizont; ausdruecklich keine vollstaendige Liste aller Fenster.

52 lokale Tests erfolgreich. Neue Regressionstests pruefen Fortsetzung nach Austritt, fehlende Nachaustrittsdaten, Einstiegstag, unreife Fenster, Wiederaufnahme, doppelte und fehlende Beobachtungen. Produktionsbewertung bleibt unveraendert.

