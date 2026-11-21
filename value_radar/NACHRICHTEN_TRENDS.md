# Trends aus Nachrichten

Stand 21.11.2026, Methode `news_trends_v1`. Code: `value_radar/nachrichten_trends/trends.py`, Workflow `news-trends.yml`, App-Tab „📈 Trends“.

## Anlass
Der Nutzer möchte aus Nachrichten ablesen, welche Aktien und Themen gerade auffällig oft genannt werden (z. B. KI-Boom, Blasen). Außerdem sollen Anregungen für Aktien entstehen, die noch nicht im Universum sind.

Entscheidung des Nutzers am 21.11.2026: zuerst regelbasiert ohne KI (Weg 1). Eine KI-Auswertung über die Claude API kommt höchstens als getrennter, gekennzeichneter Zusatz, wenn ein eigener API-Zugang besteht (Testmonat).

## Bestand (gemessen am 21.11.2026, Kopie von main)
| Quelle | Umfang | Grenze |
|---|---|---|
| `cf_company_news.json` (daily-risk) | 5.542 Schlagzeilen in 7 Tagen, 1.002 von 1.342 Titeln mit Treffern | höchstens 30 je Abruf; 52 Titel gekappt; 919 Titel über ROIC, 423 über den Google-Suchindex |
| `cf_news.json` (market-news, stündlich) | 362 Marktschlagzeilen (Bloomberg, WSJ, FT, MarketWatch, Motley Fool, Investing.com, Yahoo) | höchstens 80 je Quelle |
| Historie | keine | beide Dateien werden überschrieben |

Ohne Archiv gibt es keinen Vergleich. Deshalb ist der erste Baustein das Archiv.

## Regeln

| Regel | Umsetzung |
|---|---|
| Archiv | Eine gzip-Datei je Erfassungstag, `daten/nachrichten_archiv/JJJJ/MM/JJJJ-MM-TT.jsonl.gz`. Inhalt: Schlagzeile, Link, Verlag, Zeitpunkt, Notierung, Quelle, Erfassungszeit. Keine Artikeltexte. Es wird nie gelöscht oder überschrieben; ein zweiter Lauf am selben Tag ergänzt nur. |
| Doppelte | Gleiche Schlagzeile desselben Verlags zählt einmal (bei Unternehmensnachrichten je Aktie). Abgleich über die letzten 31 Tage. |
| Erfassungsprotokoll | `erfassung.json` je Tag: erfasste Quellen, gekappte Titel, Anzahl neuer Zeilen, Läufe. |
| Fenster | letzte 7 Tage (nach Veröffentlichung) |
| Grundwert | bis zu 56 Tage vor dem Fenster. Es zählt nur, was an diesen Tagen tatsächlich erfasst wurde, nicht die Rückschau des ersten Abrufs. |
| Mindestgrundwert | 21 erfasste Tage. Vorher bleibt das Verhältnis offen („Grundwert im Aufbau: x von 21 Tagen“). |
| Status | `steigend` ab 2-fachem Grundwert je Woche, `fallend` ab halbem, sonst `normal`. `neu` bei Grundwert 0. `wenig` unter 5 Nennungen. |
| Routine-Meldungen | Fondsbestände und Bestandsänderungen („Shares Sold by …“, „Takes Position in …“) werden getrennt gezählt. Sie zählen weder für Nennungen noch für Themen. |
| Quellenwechsel | Wechselt die Quelle einer Aktie zwischen Grundwert und Fenster (z. B. ROIC → Google), bleibt das Verhältnis offen. |
| Neue Feeds | Für Verhältnisse zählen nur Quellen, die an mindestens 90 % der Tage erfasst wurden. Ein neuer Feed ist sichtbar, hebt aber kein Thema künstlich an. |
| Themen | 14 feste Schlagwortgruppen in `THEMEN` (Englisch und Deutsch, nur Begriffe, keine Firmennamen). „AI“ und „KI“ werden nur in Großbuchstaben erkannt. |
| Kandidaten | „(BÖRSE:KÜRZEL)“ aus Schlagzeilen bei bekannter Börse, wenn das Kürzel nicht im Universum ist. Die Identität ist immer `ungeprueft`. |
| Mögliche Doppelungen | Stimmen die ersten zwei kennzeichnenden Wörter des Namens mit einem Universumstitel überein (z. B. ADR von BAT), wird der Kandidat mit `aehnlichImUniversum` gekennzeichnet und nach hinten sortiert. Ein ähnlicher Name ist kein Nachweis; deshalb wird nur gekennzeichnet, nicht verworfen. |
| Score | `scoreContribution: 0`. Kein Teil eines Scores, kein Kauf- oder Verkaufssignal. |

Die Konstanten stehen in `trends.py` und werden in `cf_trends.json` unter `konstanten` mitgeliefert.

Die App prüft beim Lesen erneut (`src/lib/trends.ts`):
- Schema, Methode und `scoreContribution` = 0;
- Datum und Alter (älter als 36 Stunden wird markiert);
- Zähler sind ganze Zahlen ≥ 0;
- das Verhältnis wird aus Nennungen und Grundwert nachgerechnet; Abweichungen werden verworfen;
- ein Status ist nur gültig, wenn ein Verhältnis dazu passt;
- Links nur mit http/https.

## Verzerrungen
- **Große Werte:** Unternehmensnachrichten sind auf 30 je Abruf gekappt, das trifft große Werte. Ihr Anstieg wird unterschätzt; sie tragen die Markierung „gekappt“. Das tägliche Archiv mildert das, weil jeder Tag neu abgefragt wird.
- **Kleine Werte:** Kleine Zahlen schwanken zufällig. Deshalb gibt es unter 5 Nennungen keinen Trendstatus.
- **Sprache und Region:** Die Quellen sind überwiegend englischsprachig. US-Werte und englische Begriffe sind stärker vertreten. Deutsche und japanische Titel erscheinen seltener, ohne dass dort weniger passiert.
- **Automatische Artikel:** Portale wie MarketBeat, defenseworld.net und 247wallst erzeugen viele Schablonen-Artikel. Bestandsmeldungen sind herausgefiltert, Vergleichs- und Kurszielmeldungen nicht. Sie erhöhen die Nennungen von Titeln, über die diese Portale gern schreiben.
- **Kandidaten:** Unternehmensnachrichten werden je Universumstitel abgefragt. Fremde Kürzel tauchen dort nur zufällig auf, etwa in Vergleichsartikeln oder Präsentationsmeldungen. Die Kandidatenliste ist deshalb klein und zufällig, keine Marktabdeckung.
- **Themen ohne Zusammenhang:** „Blase“ zählt auch bei „Ist das eine Blase? Nein.“ Die Liste zeigt deshalb immer Beispiel-Schlagzeilen.

## Probelauf (21.11.2026, Kopie von main)
- **Erster Lauf:** 5.887 Schlagzeilen archiviert (720 KB gzip); 5.404 davon im 7-Tage-Fenster. Der zweite Lauf am selben Tag fügt 0 hinzu, die Datei bleibt bytegleich.
- **Routine-Meldungen:** 310 von 5.542 Unternehmensschlagzeilen (5,6 %), davon 230 von defenseworld.net.
- **Aktien:** 962 mit Nennungen, 52 gekappt. Alle Verhältnisse sind offen (Grundwert 0 von 21 Tagen).
- **Themen** (Nennungen im Fenster):

| Thema | Nennungen |
|---|---:|
| KI | 379 |
| Abverkauf | 116 |
| Übernahmen | 95 |
| Halbleiter | 65 |
| Krypto | 34 |
| Öl/Gas | 30 |
| Zinsen | 24 |
| Rezession | 21 |
| Rüstung | 19 |
| Blase | 17 |
| Quantencomputer | 11 |
| Zölle | 7 |
| Kernkraft | 4 |
| Abnehmmittel | 4 |

- **Kandidaten:** 61 insgesamt.
  - 47 sind als mögliche Doppelung gekennzeichnet, fast alle ADR/OTC-Kürzel von Universumstiteln (BUD, BTI, DB, japanische ADRs).
  - 14 ohne Ähnlichkeit, darunter Kennametal, Houlihan Lokey, Tecnoglass und IRIDEX.
  - Bei 2 davon ist der Name aus der Schlagzeile unbrauchbar (Unilever-Seitentitel, Dassault-Präsentation).
- **Erste Verhältnisse:** frühestens am 19.12.2026 (21 erfasste Tage vor dem Fenster).
- **Archivgröße:** etwa 800 neue Schlagzeilen pro Tag ≈ 100 KB gzip, also rund 36 MB pro Jahr.

## Grenzen
- Nur Schlagzeilen, keine Artikeltexte. Eine inhaltliche Auswertung (Zusammenhang, Ironie, Einordnung) ist mit Regeln nicht möglich.
- Bis zum 19.12.2026 zeigt der Tab nur Zählungen ohne Vergleich.
- Die Kandidaten sind Anregungen zur eigenen Recherche. Vor einer Aufnahme ins Universum gilt die normale Identitätsprüfung (ISIN, Notierung, Währung).
