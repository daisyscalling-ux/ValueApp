# Wiedergefundene AvalonBay-Kursreihe

Stand 12.10.2026. PR #25 ist auf main zusammengefuehrt.

## Tatsaechliche Datenbeschaffung

Gezielte Yahoo-Abfragen fuer das Kalenderjahr 2023 lieferten bei AVB und EA YFPricesMissingError, bei CTRA, HOLX und K YFTzMissingError. Das ist ein Ergebnis dieser Abfragen, kein Beweis, dass alle anderen Quellen unbrauchbar sind.

Die oeffentliche [AvalonBay-Investorenseite](https://investors.avalonbay.com/stock-data/historical-data) zeigte dagegen 1.663 Tagesbeobachtungen vom 02.01.2020 bis 14.08.2026. Einstellung: `Adjusted: Splits and Dividends`, Anbieter QuoteMedia, USD. Die Tabelle wurde im regulaeren Browser geladen und die zugrunde liegenden Sortierwerte der angezeigten Datum-/Schlusskurs-/Volumenspalten lokal gesichert, damit nicht nur die auf zwei Stellen gerundeten Anzeigewerte verwendet werden.

Capture-SHA256: c21abe8a4ae8e4bdedc6d7834464368c4680774aaf1984a1c7c0224c02974bd5.

Zwei direkte Abrufversuche bei QuoteMedia (allgemeiner API-Endpunkt sowie eingebundener Widget-Endpunkt) lieferten HTTP 403. Es wurden keine Browser-Zugangstokens kopiert und keine automatische API-Verfuegbarkeit behauptet. Der Importpruefer arbeitet offline mit bereits gespeicherten Tabellen. Die Rohdaten bleiben lokal; dieser PR veroeffentlicht keine Kursdatei und baut keine QuoteMedia-Zugangsdaten ein.

## Ergebnis

Alle 1.663 erwarteten Kalender-Handelstage innerhalb der gefundenen Reihe sind vorhanden. Keine doppelten Tage, keine ungueltigen Preise, keine Beobachtungen ohne Handelsvolumen. 1.662 aufeinanderfolgende Tagesrenditen berechenbar. Am ersten Tag fehlt naturgemaess der vorangehende Kurs im Capture; er wird nicht erfunden.

| AVB-Fenster | Ausgereift | Mit Kandidatenreihe technisch lueckenlos | Weiter offen | Noch nicht ausgereift |
| --- | ---: | ---: | ---: | ---: |
| 21 Sitzungen | 1.468 | 1.445 | 23 | 0 |
| 63 Sitzungen | 1.442 | 1.403 | 39 | 26 |
| 126 Sitzungen | 1.379 | 1.340 | 39 | 89 |

Baseline: kein lueckenloses AVB-Fenster. Die Daten vor 2020 sowie nach dem 14.08.2026 wurden nicht wiedergefunden. Die in der Seite separat angezeigte letzte Quote traegt den 17.08.2026; daraus wurde kein historischer Schlusskurs ergaenzt. Uebernahmekonditionen, letzter Handelstag und nachfolgender Abwicklungspfad bleiben separat zu belegen. Die nach Indexaustritt liegenden Fenster bleiben offen.

## Offline-Pruefung

`review_capture.py CAPTURE_JSON FORSCHUNGSARCHIV_ZIP AUSGABEORDNER`

Das Capture enthaelt symbol, source (oeffentliche HTTPS-URL), provider, currency, adjustment, captured_at und rows mit date, close, volume. Das Referenzarchiv benoetigt coverage.json, identity-review und session-review.

Der Pruefer akzeptiert nur explizit als split-/dividendenbereinigt bezeichnete USD-Reihen, prueft doppelte und kalenderfremde Tage sowie Preis-/Volumengueltigkeit und berechnet keine Rendite ueber fehlende Handelstage. Er lehnt im Referenzarchiv gesperrte Identitaeten ab. Die Quellenangabe und Providerdeklaration sind weiterhin keine unabhaengige Bestaetigung der historischen Aktienidentitaet oder aller Kapitalmassnahmen.

Ausgabe: candidate_prices.csv und capture_review.json mit Herkunft, Fingerabdruck, Kalenderpruefung und Vorher-/Nachher-Fenstervergleich. Keine Aenderung am Roharchiv, kein automatischer Import in die App, keine Produktionsfreigabe. 59 lokale Tests erfolgreich.

