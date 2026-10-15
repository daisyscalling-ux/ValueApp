# Risikoscore: Datenblock vom 15.10.2026

Ziel dieses Blocks: fehlende Forschungsdaten beschaffen und gemeinsam pruefen. Keine Gewichtsoptimierung und keine Aenderung produktiver Risikoscores. Der Vergleich bleibt auf dem bisherigen Datenstichtag 12.10.2026 (exklusiv, letzter Referenzhandelstag 09.10.) fixiert.

## Unternehmenshistorien

Neun neue Rohreihen: ANSS, CTLT, CTRA, DAY, HOLX, IPG, JNPR, K, WBA. 11.307 Tabellenzeilen gesichert; zwei Zeilen ohne Handelsvolumen separat ausgeschlossen. Dazu die bereits gespeicherten EA- und AVB-Reihen. Insgesamt 14.223 verwendbare Beobachtungen in elf Reihen.

| Aktie | Beobachtungen | Erster Tag | Letzter Tag | Abgedeckte 63-Tage-Fenster |
|---|---:|---|---|---:|
| ANSS | 1256 | 2020-07-16 | 2025-07-16 | 1131 |
| CTLT | 1258 | 2019-12-18 | 2024-12-17 | 989 |
| CTRA | 1256 | 2021-05-06 | 2026-05-06 | 1193 |
| DAY | 1256 | 2021-02-03 | 2026-02-03 | 1034 |
| HOLX | 1256 | 2021-04-06 | 2026-04-06 | 1193 |
| IPG | 1256 | 2020-11-27 | 2025-11-26 | 1193 |
| JNPR | 1255 | 2020-07-02 | 2025-07-01 | 1121 |
| K | 1256 | 2020-12-10 | 2025-12-10 | 1193 |
| WBA | 1256 | 2020-08-27 | 2025-08-27 | 1161 |
| EA | 1255 | 2021-08-04 | 2026-08-04 | 1192 |
| AVB | 1663 | 2020-01-02 | 2026-08-14 | 1403 |

Quelle: frei sichtbare historische Tabellen von Stock Analysis, Anbieterlabel S&P Global Market Intelligence; fuer AVB bereits gesicherte Emittententabelle. Die Originaltabellen, Abrufdaten, Pruefsummen und Ausschlussgruende sind lokal archiviert. Keine automatisierte Anbieter-API behauptet.

Gegenueber dem unveraenderten Roharchiv steigen abgedeckte Dreimonatsfenster von 694.244 auf 707.047. Das sind 12.803 zusaetzliche Fenster einschliesslich EA/AVB; allein die neun neuen Reihen liefern 10.208. Von 31.898 zuvor unvollstaendigen Fenstern bleiben 19.095 offen. Alle 726.142 ausgereiften Fenster bleiben im Nenner. Die Fenster ueberlappen und sind keine unabhaengigen Stichproben.

Einmonatsfenster: +13.265; Sechsmonatsfenster: +12.110 gegenueber dem Roharchiv. Das fruehere explizite AVB-Uebernahmeszenario ist hier nicht eingerechnet.

Juniper 02.07.2025 und Catalent 18.12.2024: ohne Handelsvolumen ausgegebene Tabellenzeilen werden nicht als gehandelte Kurse verwendet. Die Catalent-SEC-Meldung bestaetigt Handelsaussetzung vor Oeffnung am 18.12.2024.

## Markt- und Branchenkontext

16 Reihen mit 47.081 Rohbeobachtungen geladen: SPY, QQQ, IWM; XLK, XLF, XLV, XLE, XLI, XLP, XLY, XLU, XLB, XLRE, XLC; VIX und TNX. Angefragt 12.10.2014 bis 12.10.2026 exklusiv. ETFs sind Branchennaeherungen, keine historische Sektor-Mitgliedschaft. VIX und TNX bleiben Niveauindikatoren ohne Investmentrendite.

| Reihe | Kalendertage mit verwendbarem Wert | Fehlende angefragte Referenztage | Ausserhalb Aktienkalender |
|---|---:|---:|---:|
| SPY | 3016 | 0 | 0 |
| QQQ | 3016 | 0 | 0 |
| IWM | 3016 | 0 | 0 |
| XLK | 3016 | 0 | 0 |
| XLF | 3016 | 0 | 0 |
| XLV | 3016 | 0 | 0 |
| XLE | 3016 | 0 | 0 |
| XLI | 3016 | 0 | 0 |
| XLP | 3016 | 0 | 0 |
| XLY | 3016 | 0 | 0 |
| XLU | 3016 | 0 | 0 |
| XLB | 3016 | 0 | 0 |
| XLRE | 2762 | 254 | 0 |
| XLC | 2089 | 927 | 0 |
| ^VIX | 3016 | 0 | 2 |
| ^TNX | 3015 | 1 | 0 |

Die meisten Reihen sind im angefragten Kalender vollstaendig. XLRE: 249 Tage vor Reihenbeginn plus fuenf Beobachtungen ohne positives Volumen; XLC: 927 Tage vor Reihenbeginn. TNX fehlt am 11.11.2016. Zwei VIX-Beobachtungen auf Aktienmarktfeiertagen bleiben im Roharchiv, werden aber nicht in die Referenzreihe aufgenommen. Keine Luecke wird vorwaerts aufgefuellt.

## Uebernahmebelege

Neun abgeschlossene Uebernahmen mit Primaerquellen und Bedingungen stehen in acquisition_recovery_evidence.json. Besonders wichtig: Die finalen Ansys-Konditionen lauten 0,3399 SNPS-Aktien plus 199,91 USD, nicht die urspruenglich angekuendigten 0,345 plus 197 USD. Hologic und Walgreens enthalten bedingte Zahlungsrechte; deren Maximalbetrag ist kein gesicherter Erloes.

## Reproduktion

`python batch_capture_review.py <window-input.zip> <output> <capture1.json> <capture2.json> ...`

`python collect_market_context.py --start 2014-10-12 --end 2026-10-12 --output <market-raw>`

`python review_market_context.py <market-raw> <window-input.zip> <market-review>`

Der neue manuelle GitHub-Workflow risk-data-recovery prueft den Code und kann die 16 Marktserien erneut laden. Die bereits lokal gesicherten Unternehmensdaten werden dadurch nicht erneut heruntergeladen. Kein neuer kompletter Universumslauf erforderlich. Rohdaten liegen im lokalen Datenpaket; im Repository werden Code, Quellenregister und dieser Bericht gespeichert.

Validierung: 43 gezielte Offline-Tests erfolgreich. Pruefung auf doppelte Termine, vertauschte Spalten, falsche Quelle, fehlendes Volumen, Renditebruecken ueber Luecken, veraenderte Nenner, Indexniveau/Rendite-Verwechslung und unveraenderte Uebernahmeberechnung.

## Noch offen

- Historien von Hess, Discover und Marathon Oil: die gepruefte Stock-Analysis-Archivseite liefert 404. Weitere Firmen bleiben in offene_datenluecken.csv priorisiert.
- Fruehe Abschnitte der fuenfjaehrigen Anbieterhistorien; einige Reihen beginnen nach Oktober 2020.
- Uebernahmeabwicklung: Zahlungstermine, bedingte Rechte, Mischtransaktionen und dokumentierte Nachfolgerbewertung. Belegte Ansprueche sind noch keine verifizierten Total Returns.
- Abspaltungen und weitere Kapitalmassnahmen sowie unabhaengige Identitaets- und Anpassungspruefung.
- Erweiterung zeitgerecht verfuegbarer SEC-Finanzdaten auf ausgeschiedene Unternehmen. Historische News/Katalysatoren sind noch kein vollstaendiger Datenbestand.
- Erst danach robuste Auswertung und Feintuning. Die gesammelten Daten allein validieren keinen Risikoscore.
