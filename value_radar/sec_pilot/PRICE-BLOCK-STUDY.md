# Kursblock des Risikoscores: Pruefung gegen spaetere Verluste

Stand 09.11.2026. Forschungsauswertung; produktive Gewichte werden hier nicht geaendert.

## Daten und vorab festgelegte Regeln

Archiv: free-source-research-Lauf 42642438250 (S&P-500-Rekonstruktion aus Wikipedia seit 2014, Yahoo-Kurse, Identitaetspruefung einschliesslich HFC -> DINO und FRC -> FRCB). Skript: `price_block_study.py ARCHIV AUSGABE`.

- Stichtage: letzter Handelstag jedes Quartals ab 2016. Universum: damalige Indexmitglieder, auch spaeter ausgeschiedene.
- Merkmale nur aus Kursen bis zum Stichtag, hoechstens fuenf Kalenderjahre (wie ROIC in der App), mindestens 505 Kurse, keine Luecke ueber 14 Tage. Formeln und Skalen wie `historyStatistics` und `riskScore` der App.
- Einstieg zum Schlusskurs der naechsten Sitzung; groesster Verlust ab Einstieg in 21, 63 und 126 Sitzungen. Ereignis: mindestens 20 % Verlust.
- Entwicklungszeitraum: Stichtage und Fenster vor 2022-01-01 (mit Corona-Crash 2020). Testzeitraum: Stichtage ab 2022-01-01 (Zinsschock 2022, Bankenkrise 2023).
- Hauptmass: mittlere Rangkorrelation zwischen Merkmal und spaeterem Verlust je Stichtag. Gepoolte AUC wird mitgeschrieben, ist aber durch marktweite Schocks verzerrt.

19.759 Beobachtungen. Ausgeschlossen: 1.769 Mitglieds-Quartale ohne Kursreihe (vor allem spaeter uebernommene oder delistete Firmen, siehe `LOSS-CASES.md`) und 152 mit zu kurzer oder lueckenhafter Historie.

## Ergebnis des heutigen Kursblocks

Der Kursblock trennt riskante von weniger riskanten Aktien: Im Testzeitraum fallen Aktien aus dem riskantesten Fuenftel innerhalb von drei Monaten in 24,2 % der Faelle um mindestens 20 %, im sichersten Fuenftel in 4,2 %.

Er ist aber nicht besser als die einfache Jahresvolatilitaet. Die schlechteste 20-Tage-Phase ist in beiden Zeitraeumen der schwaechste Baustein; ihre Skala (5–35 %) ist bei 32 % aller Beobachtungen gesaettigt.

## Vorab festgelegte Varianten und Auswahl

Auswahlregel: hoechste mittlere Rangkorrelation im Entwicklungszeitraum, 63 Sitzungen. Der Testzeitraum dient nur zur Bestaetigung.

| Variante | Entwicklung 63 T. | Test 21 T. | Test 63 T. | Test 126 T. |
|---|---:|---:|---:|---:|
| A heute: 15 ES + 10 groesster Rueckgang + 5 schlechteste 20 Tage | 0,254 | 0,148 | 0,203 | 0,220 |
| B 15 ES + 10 groesster Rueckgang | 0,258 | 0,157 | 0,213 | 0,233 |
| C nur Volatilitaet (Skala 15–60 %) | 0,253 | 0,191 | 0,234 | 0,255 |
| **D 15 ES + 10 Volatilitaet + 5 groesster Rueckgang** | **0,263** | **0,177** | **0,231** | **0,252** |
| E 15 ES + 15 Volatilitaet | 0,257 | 0,183 | 0,235 | 0,255 |
| F wie A, 20-Tage-Skala 10–60 % | 0,254 | 0,146 | 0,200 | 0,216 |

Nach der Regel ausgewaehlt: **D**. Im Testzeitraum verbessert D die Rangkorrelation gegenueber A in allen drei Horizonten (63 Sitzungen: 0,231 statt 0,203). Das Verhaeltnis der Ereignisquoten zwischen riskantestem und sicherstem Fuenftel steigt von 5,7- auf 7,1-fach. C und E sind im Test minimal besser; sie nachtraeglich zu waehlen wuerde den Testzeitraum zur Auswahl verwenden.

Volatilitaetsskala: 0 Punkte bei 15 %, 100 Punkte bei 60 % Jahresvolatilitaet (etwa 10. und 95. Perzentil im Entwicklungszeitraum: 17 % und 58 %).

## Grenzen

- Kostenlose Anbieterreihen ohne archivierte Point-in-Time-Version; Identitaeten vorlaeufig.
- Fehlende Reihen ausgeschiedener Firmen (vor allem SIVB, SBNY und spaeter uebernommene Absteiger) fehlen weiterhin; das Ergebnis ist deshalb noch nicht frei von Survivorship Bias.
- Ueberlappende Fenster und gemeinsame Marktereignisse: keine unabhaengigen Beobachtungen, keine Signifikanztests.
- Nur der Kursblock ist pruefbar. Finanz-, Bewertungs- und Wettbewerbsbloecke brauchen Point-in-Time-Daten.

## Naechster Schritt

Uebernahme von Variante D in die App erfordert die Volatilitaet in `historyStatistics` (App und tägliche Vorberechnung), eine neue Validierungsversion und einen erneuten Lauf von `daily-risk`.
