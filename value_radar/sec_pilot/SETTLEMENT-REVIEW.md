# Uebernahmen: tatsaechliche Handelsgrenze und Forschungsrechnung

Stand: 12. Oktober 2026. Roharchiv und Produktionsscores bleiben unveraendert.

## Primaerquellen

- AvalonBay [Closing 8-K, Items 2.01 und 3.01](https://investors.avalonbay.com/sec-filings/all-sec-filings/content/0001104659-26-097833/tm2623381d1_8k.htm): Abschluss am 17.08.2026, 2,793 Vivmark-Aktien je AVB-Aktie; AVB vor Handelsbeginn am 17.08. eingestellt. Barausgleich fuer Bruchteile ist nicht verifiziert.
- [Vivmark/Equity Residential 8-K](https://www.sec.gov/Archives/edgar/data/906107/000119312526354068/d372623d8k.htm): Fortsetzung von Equity Residential; dessen EQR-Kuerzel gilt am 17.08., VMRK ab 18.08. Dies ist keine Umbenennung der AVB-Aktie.
- Electronic Arts [Closing 8-K, Items 2.01 und 3.01](https://www.sec.gov/Archives/edgar/data/712515/000114036126031157/ef20079099_8k.htm): 210 USD Baranspruch je Aktie, Abschluss 04.08.2026, Handelsende nach dem Schlusskurs am 04.08. Fuer EA fehlen weiterhin ausreichende historische Preise. Der Anspruch ersetzt diese nicht.

## AvalonBay: ausgefuehrter Vergleich

Der separat gespeicherte Investorentabellen-Abzug umfasst 1.663 bereinigte Kurse vom 02.01.2020 bis 14.08.2026. Ohne Abwicklungsrechnung sind 1.403 von 1.442 ausgereiften Dreimonatsfenstern technisch vollstaendig; 39 enden im offenen Uebergang.

Der unbereinigte letzte Schlusskurs von 184,06 USD wurde am 12.10.2026 aus der Investorentabelle mit Einstellung `Unadjusted` fuer den 14.08. abgelesen. Die danebenstehende Kursanzeige mit Datum 17.08. wird nicht als weiterer Handelstag benutzt. Yahoo liefert einen einzelnen AVB-Datensatz und kennzeichnet dort 2,793 als Split. Dieser Eintrag wird NICHT zusaetzlich auf die Umtauschrechnung angewendet.

Ein begrenzter Yahoo-Abruf fuer VMRK liefert 40 Beobachtungen vom 14.08. bis 09.10.2026 sowie USD/EQUITY/VMRK und Vivmark Residential als Metadaten. Die vor dem Kuerzelwechsel liegende Beobachtung wird durch die EQR-Nachfolgequelle eingeordnet. Der alte Archiv-Metadatenname fuer VMRK lautet dagegen AvalonBay; das ist keine Freigabe der alten Gesamtserie. Hier wird ausschliesslich der neue, datierte Abruf verwendet.

Das explizite Szenario haelt die Gegenleistung anteilig weiter. Am Uebergang gilt:

`W_t / W_vorher = 2,793 * unbereinigter_Nachfolgerkurs_t / unbereinigter_AVB_Schlusskurs`

Danach gelten die Verhaeltnisse der bereinigten Nachfolgerkurse. Die Dividende wird nicht ein zweites Mal addiert. W ist ein synthetischer Vermoegensindex, kein AVB-Börsenkurs. Die in der Investorentabelle auf Cent gerundete Uebergangsnotierung bringt eine kleine Rundungsunsicherheit mit.

Ergebnis mit Archivstichtag 09.10.2026:

| Fenster | Ausgereift | Im Szenario abgedeckt | Offen | Noch nicht ausgereift |
|---|---:|---:|---:|---:|
| 21 Handelstage | 1468 | 1466 | 2 | 0 |
| 63 Handelstage | 1442 | 1442 | 0 | 26 |
| 126 Handelstage | 1379 | 1379 | 0 | 89 |

Die zwei offenen kurzen Fenster verlangen einen Neueinstieg nach dem AVB-Handelsende. Sie bleiben im Nenner und werden als nicht handelbar markiert. Bereits gehaltene Positionen duerfen dagegen ueber das Handelsende hinauslaufen. Ein Indexaustritt beendet keinen Haltezeitraum. Noch nicht ausgereifte Fenster bleiben separat.

**Forschungsannahme:** anteilige Nachfolgeraktien und Wiederanlage gemaess Anbieterbereinigung, ohne Steuern und Kosten. Das bildet keinen konkreten Barausgleich von Bruchteilen nach. Anbieterbereinigungen, Auszahlungen und die Gesamtidentitaet sind damit nicht unabhaengig zertifiziert. Abdeckung ist kein Beleg fuer profitable Signale oder einen kalibrierten Riskscore.

## Ausfuehren mit lokal gesicherten Eingaben

```text
python settlement_review.py avb-browser-capture.json window-input.zip vmrk-successor-prices.csv vmrk-successor-probe.json avb-raw-anchor.json security_identity_evidence.json settlement-review
```

Ausgaben: `shareholder_wealth_scenario.csv` und `settlement_review.json`, einschliesslich SHA-256 aller Eingaben, Quellen, Grenzen, Vorher/Nachher-Zaehlung und `production_eligible=false`. Keine Netzwerkzugriffe und kein automatischer Import. Die Eingaben sind im lokalen Ergebnisarchiv gesichert; Kursdaten werden nicht mit diesem PR ins Repository veroeffentlicht. Ein neuer kompletter Universumslauf ist fuer diesen Vergleich nicht erforderlich.

Abgewiesen werden fehlende Uebergangskurse, doppelte oder fehlende Nachfolger-Handelstage, falsche Waehrung/Identitaet, bereinigte statt unbereinigte Uebergangsanker, ungeklaerte Aktiensplits und Bar-/Mischtransaktionen. EA ist deshalb nur als belegter Abwicklungsfall erfasst; keine kuenstliche Kursreihe wird angelegt.
