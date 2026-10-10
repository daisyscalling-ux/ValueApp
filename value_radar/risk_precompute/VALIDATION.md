# Historische Prüfung des Risikoscores

## Was implementiert ist
Der tägliche Risikoexport erstellt zusätzlich cf_risk_validation.json. In der Einzelanalyse erscheint unter Risiko & Anfälligkeit ein aufklappbarer Bereich Historische Prüfung. Standard ist der Dreimonatsvergleich; ein und sechs Monate lassen sich auswählen.

Geprüft wird ausschließlich der historische Kursanteil des Modells (30 % Gewicht), für diese Auswertung auf 0–100 normiert. Finanzkennzahlen, Nachrichten, Markt- und Peer-Stress gehören nicht zu dieser historischen Prüfung. Die Risikogewichte werden nicht automatisch geändert.

## Festgelegtes Vorgehen
- Stichtage: letzter verfügbarer Handelstag jedes Quartals.
- Score: dieselbe bestehende riskScore-Funktion, ausschließlich mit Kursen bis zum Stichtag; mindestens 505 Handelstage.
- Angenommener Einstieg: Schlusskurs der nächsten Sitzung. Ergebnisfenster: danach 21, 63 oder 126 Handelstage.
- Ergebnisse: größter Rückgang vom Einstieg, größter Drawdown innerhalb des Fensters und Rendite am Fensterende. Das primäre Verlustereignis ist ein Rückgang von mindestens 20 % vom Einstieg.
- Scoregruppen: 0–24, 25–49, 50–74, 75–100. Angezeigt werden Häufigkeit und mittlerer Verlust, jeweils mit Beobachtungszahl.
- Zeitliche Trennung: 1. Januar 2025. Fenster, die den Trennstichtag überschreiten, werden ausgeschlossen. Der spätere Zeitraum ist keine garantiert unangetastete Teststichprobe.
- Vergleichsmaßstab: historische Jahresvolatilität aus den letzten 252 Tagesrenditen. Je Stichtagsmonat wird ab mindestens 20 Aktien die Rangkorrelation beider Risikomaße mit dem späteren größten Verlust berechnet; die Stichtagskorrelationen werden gleichgewichtet gemittelt.
- Ausschließlich vom Anbieter als primär und common gekennzeichnete Aktien; keine zusätzliche Zählung von ADRs oder Vorzugsaktien. Fehlende Klassifikationen bleiben ausgeschlossen.

## Einschränkungen
Das aktuelle Universum enthält keine vollständige historische Mitgliederliste und keine systematische Delisting-Abdeckung. Ergebnisse leiden damit unter Survivorship- und Auswahlverzerrung. Unterschiedliche Firmen und Zeitfenster sind nicht unabhängig. Sechsmonatsfenster überlappen; auch 63-Tage-Fenster können sich leicht überschneiden. Keine Signifikanztests, keine individuellen Verlustwahrscheinlichkeiten, keine Derivatesimulation und keine automatische Optimierung.

ROIC liefert hier knapp fünf Jahre. Nach der zweijährigen Mindesthistorie beginnen die auswertbaren Stichtage im aktuellen Datensatz erst Ende 2023. Insbesondere die Krisen 2020 und 2022 werden nicht als spätere Ergebnisphasen geprüft. Der verfügbare Rückblick wächst innerhalb dieser Untersuchung von zwei auf knapp fünf Jahre; dies ist kein konstant mit fünf Vorjahren berechneter Backtest. Anbieterreihen sind heute bereinigt und können nachträglich revidiert worden sein.

## Technischer Pilot vom 10. Oktober 2026
24 vorab ausgewählte aktuelle US-Unternehmen aus sechs Bereichen wurden über Yahoo geladen: MSFT, ORCL, ADBE, CRM, JPM, BAC, WFC, GS, XOM, CVX, COP, EOG, JNJ, MRK, PFE, UNH, CAT, DE, HON, GE, WMT, COST, KO und PEP. Alle 24 Historien konnten ausgewertet werden; 672 Aktien-/Zeitfenster über alle drei Horizonte. Dies ist eine kleine bewusst ausgewählte technische Pilotstichprobe, kein repräsentativer Nachweis.

Im späteren Dreimonatszeitraum umfasste sie 144 Fenster. Der mittlere größte Verlust ab Einstieg betrug in aufsteigenden Scoregruppen 3,9 %, 7,2 %, 10,9 % und 12,7 %. Die Gruppen umfassten nur 13, 73, 44 und 14 Fenster und sind nicht unabhängig. Mittlere Rangkorrelation: Kursscore 0,31, einfache Volatilität 0,28; im früheren Zeitraum dagegen 0,21 bzw. 0,28. Das zeigt keine robuste Überlegenheit des Scores und rechtfertigt keine Parameteränderung. Die gesamte Universumsauswertung steht nach dem nächsten GitHub-Lauf an.

## Betrieb
Der Job verwendet die ohnehin geladenen ROIC-Historien; es gibt keinen zusätzlichen vollständigen Scan. Beim ersten Validierungslauf müssen frische Aktien mit lediglich gespeicherten Zusammenfassungen erneut vollständig geladen werden. Detailbeobachtungen werden im GitHub-Actions-Cache gehalten. Ins Repository gelangt nur der zusammengefasste Bericht. Alte oder nicht mehr im aktuellen Universum vorhandene Cacheeinträge werden nicht unbegrenzt weitergezählt (maximal sieben Tage Abrufalter).

Nach Änderungen an dieser Methode oder den Score-Schwellen muss VALIDATION_VERSION einschließlich Cache-Key erhöht werden, damit keine unterschiedlich berechneten Ergebnisse vermischt werden.

