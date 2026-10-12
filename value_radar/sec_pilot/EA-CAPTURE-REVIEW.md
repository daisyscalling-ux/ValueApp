# Electronic Arts: fuenf Jahre aus frei sichtbarer Kurstabelle

Geprueft am 12.10.2026. Quelle: https://stockanalysis.com/stocks/ea/history/
Die Seite nennt S&P Global Market Intelligence als Datenquelle. Es wurde die oeffentliche Auswahl `5 Years`, `Daily`, `50 Rows` ueber alle 26 Seiten gelesen. Laengere Zeitraeume und die grosse Tabellenansicht fuehrten zur Abo-Seite und wurden nicht verwendet. Die alte Investorenseite https://ir.ea.com/ leitet inzwischen zur EA-Hauptseite um.

## Gesichertes Ergebnis

- 1.255 Tagesbeobachtungen vom 04.08.2021 bis 04.08.2026, in diesem Bereich keine fehlenden XNYS-Handelstage, keine doppelten Tage und keine ungueltigen Zahlen.
- 1.254 berechenbare Tagesrenditen. Am ersten erfassten Tag fehlt der Vortagskurs; dessen Rendite bleibt leer.
- Rohfassung: `ea-browser-capture.json`, SHA-256 `be4eace52bd34c9f9399c20d97c2114529773771e1fcf79c579c04afb8afa0a7`.
- Spalten `Close` und `Adj. Close` bleiben getrennt. Die auf der Website gerundete Prozentveraenderung wird nicht fuer Renditen benutzt. Renditen entstehen aus zwei aufeinanderfolgenden bereinigten Schlusskursen.
- Angezeigte Preise sind auf Cent gerundet. Dividenden- und Splitbereinigung des Anbieters ist damit nicht unabhaengig bestaetigt.

Der Vergleich mit dem vorhandenen Forschungsarchiv (Stichtag 09.10.2026) ergibt:

| Fenster | Ausgereift | Technisch abgedeckt | Weiter offen | Noch nicht ausgereift |
|---|---:|---:|---:|---:|
| 21 Handelstage | 1459 | 1234 | 225 | 0 |
| 63 Handelstage | 1442 | 1192 | 250 | 17 |
| 126 Handelstage | 1379 | 1129 | 250 | 80 |

Vorher waren wegen der einzelnen Yahoo-Beobachtung keine EA-Fenster abgedeckt. Von den 250 weiterhin offenen ausgereiften Dreimonatsfenstern benoetigen 203 einen Einstiegskurs vor dem Beginn der erfassten Reihe. Weitere 47 reichen ueber das Handelsende hinaus. Beide Gruppen bleiben in der Auswertung; kein Ausschluss verbessert kuenstlich die Abdeckung.

## Was offen bleibt

1. Fruehere Tageskurse ab dem Studienbeginn 12.10.2020 bis vor dem 04.08.2021 samt Renditeanschluss. Fuer Entscheidungen bis dahin reicht die fuenfjaehrige Reihe nicht.
2. Die Barabwicklung fuer Haltefenster ueber das Handelsende. Das [Closing 8-K](https://www.sec.gov/Archives/edgar/data/712515/000114036126031157/ef20079099_8k.htm) dokumentiert 210 USD je Aktie, Abschluss 04.08.2026 und Handelsstopp nach dem Schlusskurs dieses Tages. Ein Baranspruch ist kein spaeterer Boersenkurs. Zahlungsdatum und anschliessende Wiederanlage bzw. Kassenhaltung sind gesondert festzulegen und zu belegen oder als Annahme auszuweisen.
3. Unabhaengige Pruefung der Anbieterbereinigungen. Technische Vollstaendigkeit alleine gibt noch keine Produktionsfreigabe oder kalibrierte Risikoaussage.

## Reproduktion

```text
python review_capture.py ea-browser-capture.json window-input.zip ea-review
```

Der bestehende Offline-Reviewer erkennt jetzt auch die gesicherte sichtbare Tabelle anhand ihrer exakten Spalten und ihrer zum Symbol passenden Quelladresse. Er lehnt vertauschte Spalten, fehlende Zellen, unpassende Quell-Symbole und Nullvolumen ab. Das originale Quellenlabel `Adj. Close` wird im Bericht erhalten.

Die lokalen Rohdaten, normalisierten Kandidaten und der Pruefbericht werden separat gesichert. Dieser PR veroeffentlicht keine Kursdaten und fuehrt keinen Scraper oder automatischen Import ein. Roharchiv und produktive Scores bleiben unveraendert. Kein neuer kompletter Universumslauf notwendig.
